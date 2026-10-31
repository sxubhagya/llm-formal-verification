"""Coordinate candidate property generation, response parsing, and design validation."""
from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from typing import Any
from pydantic import ValidationError

from backend.app.models.design_ir import DesignIR
from backend.app.models.property_models import (
    PropertyBatch, CandidateProperty, PropertyProvenance,
    AssumptionReviewStatus, PropertyGenerationResponse
)
from backend.app.services.llm.provider import LLMProvider, get_llm_provider
from backend.app.services.llm.context_builder import build_design_context
from backend.app.services.llm.prompt_builder import build_generation_prompts, PROMPT_VERSION
from backend.app.services.property_validation import validate_property_batch


def _extract_json_text(raw_text: str) -> str:
    """Extract raw JSON text from potentially markdown-fenced LLM output."""
    trimmed = raw_text.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", trimmed, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return trimmed


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
        source_code: str | None = None
    ) -> PropertyGenerationResponse:
        """End-to-end pipeline: Context -> Prompt -> LLM -> Parse -> Validate."""
        if isinstance(design, dict):
            design = DesignIR.model_validate(design)

        target = target_module or design.top_module
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
            model_name=model_name
        )

        llm_response = self.provider.generate(prompt=user_prompt, system_prompt=system_prompt)
        raw_content = llm_response.content

        # Parse JSON
        json_str = _extract_json_text(raw_content)
        try:
            parsed_data = json.loads(json_str)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM output could not be parsed as valid JSON: {exc}. Raw snippet: {raw_content[:200]}") from exc

        if not isinstance(parsed_data, dict):
            raise ValueError("Expected LLM JSON output to be a dictionary matching PropertyBatch.")

        # Ensure batch_id and design_top consistency
        if "batch_id" not in parsed_data:
            parsed_data["batch_id"] = f"{target}_generated_batch"
        if "design_top" not in parsed_data or parsed_data["design_top"] != design.top_module:
            parsed_data["design_top"] = design.top_module

        # Ensure assumptions and provenance follow policy
        timestamp_str = datetime.now(timezone.utc).isoformat()
        total_tokens = llm_response.usage.get("total_tokens") if llm_response.usage else None

        props = parsed_data.get("properties", [])
        if not isinstance(props, list) or len(props) == 0:
            raise ValueError("LLM generated empty or invalid 'properties' list.")

        for prop in props:
            if isinstance(prop, dict):
                prop["design_top"] = design.top_module
                if "module" not in prop or not prop["module"]:
                    prop["module"] = target
                # Enforce assumptions must be proposed
                for asm in prop.get("assumptions", []):
                    if isinstance(asm, dict):
                        asm["status"] = "proposed"
                        asm["source"] = "llm"
                # Update provenance
                prov = prop.get("provenance") or {}
                prov["generator"] = "llm"
                prov["model_name"] = model_name
                prov["prompt_version"] = PROMPT_VERSION
                prov["timestamp"] = timestamp_str
                prov["tokens_used"] = total_tokens
                prop["provenance"] = prov

        try:
            batch = PropertyBatch.model_validate(parsed_data)
        except ValidationError as exc:
            raise ValueError(f"LLM output failed CandidateProperty schema validation: {exc}") from exc

        # Run structural validation against DesignIR
        validation_result = validate_property_batch(design=design, batch=batch)

        provenance = PropertyProvenance(
            generator="llm",
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            timestamp=timestamp_str,
            tokens_used=total_tokens,
            generation_notes=f"Generated {len(batch.properties)} candidate properties for module '{target}'."
        )

        warnings: list[str] = []
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
            warnings=warnings
        )
