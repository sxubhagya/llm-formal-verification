"""Coordinate candidate property generation, response parsing, and design validation."""
from __future__ import annotations
import json
import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from pydantic import ValidationError

from backend.app.models.design_ir import DesignIR
from backend.app.models.specification_models import DesignSpecification
from backend.app.models.property_models import (
    PropertyBatch, CandidateProperty, PropertyProvenance,
    AssumptionReviewStatus, PropertyGenerationResponse
)
from backend.app.services.llm.provider import LLMProvider, get_llm_provider
from backend.app.services.llm.mock_provider import MockProvider
from backend.app.services.llm.context_builder import build_design_context
from backend.app.services.llm.prompt_builder import build_generation_prompts, PROMPT_VERSION
from backend.app.services.property_validation import validate_property_batch


def _extract_json_text(raw_text: str) -> str:
    """Extract raw JSON text from potentially markdown-fenced LLM output."""
    trimmed = raw_text.strip()
    blocks = re.findall(r"```(?:json)?\s*([\s\S]*?)\s*```", trimmed, re.IGNORECASE)
    for block in blocks:
        candidate = block.strip()
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return candidate
        except json.JSONDecodeError:
            continue
    return trimmed


def _canonicalize_clock_reset_fields(parsed_data: dict[str, Any]) -> list[str]:
    """Accept the common LLM alias `name` for clock/reset `signal`.

    The canonical public schema remains `signal`. If both aliases are present
    with different values, reject the output rather than guessing.
    """
    corrections: list[str] = []
    properties = parsed_data.get("properties", [])
    if not isinstance(properties, list):
        return corrections
    for index, prop in enumerate(properties):
        if not isinstance(prop, dict):
            continue
        for context_name in ("clock", "reset"):
            context = prop.get(context_name)
            if not isinstance(context, dict) or "name" not in context:
                continue
            alias_value = context.get("name")
            signal_value = context.get("signal")
            if signal_value is not None and signal_value != alias_value:
                raise ValueError(
                    f"Property {prop.get('property_id', index + 1)} has conflicting "
                    f"{context_name}.name and {context_name}.signal values."
                )
            if signal_value is None:
                context["signal"] = alias_value
            context.pop("name", None)
            corrections.append(
                f"Property {prop.get('property_id', index + 1)}: normalized "
                f"{context_name}.name to canonical {context_name}.signal."
            )
    return corrections



def _canonicalize_property_categories(parsed_data: dict[str, Any]) -> list[str]:
    """Map provider-specific 'functional' labels to the canonical taxonomy.

    This only normalizes metadata. It never changes an assertion expression.
    """
    corrections: list[str] = []
    properties = parsed_data.get("properties", [])
    if not isinstance(properties, list):
        return corrections
    temporal_tokens = ("|->", "|=>", "$past(", "$stable(", "$rose(", "$fell(")
    for index, prop in enumerate(properties):
        if not isinstance(prop, dict):
            continue
        category = prop.get("category")
        if not isinstance(category, str) or category.strip().lower() != "functional":
            continue
        expression = str(prop.get("expression", ""))
        language = str(prop.get("assertion_language", ""))
        has_clock = isinstance(prop.get("clock"), dict)
        if language == "systemverilog_assertion" and any(token in expression for token in temporal_tokens):
            normalized = "temporal"
        elif has_clock:
            normalized = "invariant"
        else:
            normalized = "combinational"
        prop["category"] = normalized
        corrections.append(
            f"Property {prop.get('property_id', index + 1)}: normalized provider category 'functional' to '{normalized}'; assertion expression unchanged."
        )
    return corrections

class PropertyGenerationService:
    """Orchestrates candidate formal property generation and validation."""

    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or get_llm_provider()

    def generate_candidate_properties(
        self,
        design: DesignIR | dict[str, Any],
        target_module: str | None = None,
        max_properties: int = 5,
        focus_areas: list[str] | None = None,
        source_code: str | None = None,
        specification: DesignSpecification | dict[str, Any] | None = None
    ) -> PropertyGenerationResponse:
        """End-to-end pipeline: Context -> Prompt -> LLM -> Parse -> Validate."""
        if isinstance(design, dict):
            design = DesignIR.model_validate(design)

        if specification is None:
            raise ValueError("An independent behavioural specification is required. RTL-only property generation is disabled to prevent circular verification.")
        if isinstance(specification, dict):
            specification = DesignSpecification.model_validate(specification)
        if specification.approval_status != "approved":
            raise ValueError("The behavioural specification must be reviewed and approved before property generation.")
        if specification.design_top != design.top_module:
            raise ValueError("Specification design_top does not match the analysed RTL design.")
        target = target_module or design.top_module
        if target != design.top_module:
            raise ValueError("Property generation currently targets the analysed top module only. Select the top module rather than a nested module.")
        if not 1 <= max_properties <= 20:
            raise ValueError("max_properties must be between 1 and 20; this is a safety ceiling, not a target property count.")
        context = build_design_context(
            design=design,
            target_module=target,
            source_code=source_code,
            focus_areas=focus_areas
        )

        model_name = getattr(self.provider, "model_name", "llm")
        system_prompt, user_prompt = build_generation_prompts(
            context=context,
            max_properties=max_properties,
            model_name=model_name,
            specification_text="\n".join([f"Specification: {specification.title}", f"Description: {specification.description}", *[f"{r.requirement_id} [{r.source.value}]: {r.statement}" for r in specification.requirements]])
        )

        llm_response = self.provider.generate(prompt=user_prompt, system_prompt=system_prompt)
        raw_responses = [llm_response.content]
        usage_parts = [dict(llm_response.usage or {})]

        normalization_warnings: list[str] = []
        def parse_response(content: str) -> dict[str, Any]:
            try:
                value = json.loads(_extract_json_text(content))
            except json.JSONDecodeError as exc:
                raise ValueError(f"LLM output could not be parsed as valid JSON: {exc}. Raw snippet: {content[:200]}") from exc
            if not isinstance(value, dict):
                raise ValueError("Expected LLM JSON output to be a dictionary matching PropertyBatch.")
            normalization_warnings.extend(_canonicalize_clock_reset_fields(value))
            normalization_warnings.extend(_canonicalize_property_categories(value))
            return value

        parsed_data = parse_response(llm_response.content)
        if not isinstance(parsed_data.get("properties"), list):
            raise ValueError("LLM output must contain a properties array.")

        # The LLM chooses the number of properties. No follow-up request is
        # issued merely to fill a quota; the configured maximum is only a
        # defensive ceiling. This avoids padding and keeps one generation
        # interaction auditable and reproducible.
        raw_responses = [llm_response.content]
        usage_parts = [dict(llm_response.usage or {})]

        raw_content = "\n\n".join(raw_responses)
        llm_response.usage = {
            key: sum(int(part.get(key, 0) or 0) for part in usage_parts)
            for key in ("prompt_tokens", "completion_tokens", "total_tokens")
        }
        schema_warnings = normalization_warnings

        # Reject contradictory model metadata instead of silently rewriting it.
        if "batch_id" not in parsed_data or not isinstance(parsed_data["batch_id"], str) or not parsed_data["batch_id"].strip():
            parsed_data["batch_id"] = f"{target}_generated_batch"
        if parsed_data.get("design_top") != design.top_module:
            raise ValueError("LLM returned a design_top that does not match the analysed design.")

        # Ensure assumptions and provenance follow policy
        timestamp_str = datetime.now(timezone.utc).isoformat()
        total_tokens = llm_response.usage.get("total_tokens") if llm_response.usage else None

        props = parsed_data.get("properties", [])
        if not isinstance(props, list) or len(props) == 0:
            raise ValueError("LLM generated empty or invalid 'properties' list.")

        if len(props) > max_properties:
            raise ValueError(f"LLM returned {len(props)} properties, exceeding requested maximum {max_properties}.")
        property_ids = [p.get("property_id") for p in props if isinstance(p, dict)]
        if len(property_ids) != len(props) or len(set(property_ids)) != len(property_ids):
            raise ValueError("LLM output contains missing or duplicate property_id values.")

        valid_requirement_ids = {r.requirement_id for r in specification.requirements}
        for prop in props:
            if isinstance(prop, dict):
                if prop.get("design_top") != design.top_module:
                    raise ValueError(f"Property {prop.get('property_id')} has a mismatched design_top.")
                if prop.get("module") != target:
                    raise ValueError(f"Property {prop.get('property_id')} targets module {prop.get('module')!r}, not {target!r}.")
                requirement_ids = prop.get("requirement_ids")
                if not isinstance(requirement_ids, list) or not requirement_ids or not all(isinstance(item, str) and item.strip() for item in requirement_ids):
                    raise ValueError(f"Property {prop.get('property_id')} must reference at least one non-empty string specification requirement_id.")
                unknown_ids = set(requirement_ids) - valid_requirement_ids
                if unknown_ids:
                    raise ValueError(f"Property {prop.get('property_id')} references unknown requirement IDs: {sorted(unknown_ids)}")
                # Enforce assumptions must be proposed
                assumptions = prop.get("assumptions")
                if assumptions is None:
                    assumptions = []
                    prop["assumptions"] = assumptions
                if not isinstance(assumptions, list):
                    raise ValueError(f"Property {prop.get('property_id')} assumptions must be a list or null.")
                for asm in assumptions:
                    if isinstance(asm, dict):
                        asm["status"] = "proposed"
                        asm["source"] = "llm"
                # Update provenance
                prov = prop.get("provenance") or {}
                prov["generator"] = "llm"
                prov["model_name"] = model_name
                prov["prompt_version"] = PROMPT_VERSION
                prov["source_design_hash"] = hashlib.sha256((source_code or "").encode("utf-8")).hexdigest() if source_code is not None else None
                prov["source_specification_hash"] = specification.content_hash()
                prov["timestamp"] = timestamp_str
                prov["tokens_used"] = total_tokens
                prop["provenance"] = prov

        try:
            batch = PropertyBatch.model_validate(parsed_data)
        except ValidationError as exc:
            raise ValueError(f"LLM output failed CandidateProperty schema validation: {exc}") from exc

        # Run structural validation against DesignIR
        validation_result = validate_property_batch(design=design, batch=batch)

        for prop in batch.properties:
            prop.provenance.generation_notes = f"Specification SHA-256: {specification.content_hash()}; requirement IDs: {', '.join(prop.requirement_ids)}"

        provenance = PropertyProvenance(
            generator="llm",
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            source_design_hash=hashlib.sha256((source_code or "").encode("utf-8")).hexdigest() if source_code is not None else None,
            source_specification_hash=specification.content_hash(),
            timestamp=timestamp_str,
            tokens_used=total_tokens,
            generation_notes=f"Generated {len(batch.properties)} specification-guided candidate properties for module '{target}'. Specification hash: {specification.content_hash()}."
        )

        warnings: list[str] = list(schema_warnings)
        warnings.append("Properties were generated from the independent behavioural specification. RTL was used only for structural/signal context; formal results apply to this exact specification and RTL snapshot.")
        covered_requirement_ids = {rid for candidate in batch.properties for rid in candidate.requirement_ids}
        uncovered_requirement_ids = sorted(valid_requirement_ids - covered_requirement_ids)
        if uncovered_requirement_ids:
            warnings.append(
                "Specification coverage is incomplete: no generated property references "
                + ", ".join(uncovered_requirement_ids)
                + ". Requirement-ID mapping is traceability metadata, not proof of semantic coverage."
            )
        if validation_result.summary.get("rejected", 0) > 0:
            warnings.append(
                f"{validation_result.summary['rejected']} of {validation_result.summary['total']} generated properties failed structural design validation."
            )

        return PropertyGenerationResponse(
            batch=batch,
            validation=validation_result,
            provenance=provenance,
            raw_response=raw_content,
            usage=llm_response.usage,
            warnings=warnings,
            generation_audit={
                "schema_version": "1.0",
                "provider": getattr(self.provider, "provider_name", type(self.provider).__name__),
                "model": model_name,
                "prompt_version": PROMPT_VERSION,
                "created_at": timestamp_str,
                "system_prompt": system_prompt,
                "user_prompts": [user_prompt],
                "raw_responses": raw_responses,
                "source_design_sha256": hashlib.sha256((source_code or "").encode("utf-8")).hexdigest() if source_code is not None else None,
                "source_specification_sha256": specification.content_hash(),
                "system_prompt_sha256": hashlib.sha256(system_prompt.encode("utf-8")).hexdigest(),
                "user_prompt_sha256": hashlib.sha256(user_prompt.encode("utf-8")).hexdigest(),
            }
        )
