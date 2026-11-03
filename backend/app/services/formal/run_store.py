"""Local, auditable storage for completed formal-verification experiments."""
from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class FormalRunStore:
    """Persist verification inputs, outcomes and evidence as per-run JSON artifacts.

    The store is intentionally local and filesystem-backed for the research prototype.
    It never stores API keys or process environment variables.
    """

    def __init__(self, root: str | Path | None = None):
        configured = root or os.getenv("FORMAL_RUNS_DIR")
        self.root = Path(configured) if configured else Path(__file__).resolve().parents[4] / "formal" / "runs"
        self.root.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _jsonable(value: Any) -> Any:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {str(k): FormalRunStore._jsonable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [FormalRunStore._jsonable(v) for v in value]
        if hasattr(value, "value"):
            return value.value
        return value

    def save(self, request: Any, response: Any) -> dict[str, Any]:
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "_" + secrets.token_hex(4)
        sources = dict(request.verilog_sources)
        source_hashes = {
            name: hashlib.sha256(content.encode("utf-8")).hexdigest()
            for name, content in sorted(sources.items())
        }
        target = self.root / run_id
        staging = self.root / (".tmp_" + run_id)
        staging.mkdir(parents=True, exist_ok=False)
        try:
            trace_dir = staging / "traces"
            trace_dir.mkdir()
            trace_artifacts: dict[str, str] = {}
            trace_urls: dict[str, str] = {}
            for result in getattr(response, "results", []):
                trace_path = getattr(result, "counterexample_vcd", None)
                if trace_path and Path(trace_path).is_file():
                    filename = hashlib.sha256(result.property_id.encode("utf-8")).hexdigest()[:16] + ".vcd"
                    shutil.copy2(trace_path, trace_dir / filename)
                    trace_artifacts[result.property_id] = filename
                    trace_urls[result.property_id] = f"/api/formal/runs/{run_id}/traces/{filename}"
            verification_data = self._jsonable(response)
            for result_data in verification_data.get("results", []):
                if result_data.get("property_id") in trace_urls:
                    result_data["counterexample_vcd"] = trace_urls[result_data["property_id"]]
            record = {
                "schema_version": "1.2",
                "run_id": run_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "design_top": request.top_module or request.design_ir.top_module,
                "proof_mode": self._jsonable(request.proof_mode),
                "solver": self._jsonable(request.solver),
                "depth": request.depth,
                "source_sha256": source_hashes,
                "verilog_sources": sources,
                "trace_artifacts": trace_artifacts,
                "behavioural_specification": self._jsonable(request.specification) if getattr(request, "specification", None) is not None else None,
                "initial_reset_contract": self._jsonable(getattr(request, "initial_reset_contract", None)),
                "generation_audit": self._jsonable(getattr(request, "generation_audit", None)),
                "specification_sha256": request.specification.content_hash() if getattr(request, "specification", None) is not None else None,
                "design_ir": self._jsonable(request.design_ir),
                "property_batch": self._jsonable(request.property_batch),
                "verification": verification_data,
                "notes": "Local research artifact. PASS applies only to the recorded RTL, independent behavioural specification, properties, assumptions and proof configuration. A formal PASS does not validate the completeness or correctness of the specification itself.",
            }
            run_json_tmp = staging / "run.json.tmp"
            run_json_tmp.write_text(json.dumps(record, indent=2), encoding="utf-8")
            os.replace(run_json_tmp, staging / "run.json")
            rtl_dir = staging / "rtl"
            rtl_dir.mkdir()
            for name, content in sources.items():
                # Source names were validated by SBYRunner before this point.
                destination = rtl_dir / name
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_text(content, encoding="utf-8")
            # A completed run becomes visible in history only after every artifact
            # has been written successfully.
            os.replace(staging, target)
            # Publish durable trace URLs to the in-memory response only after
            # the complete run directory has become visible.
            for result in getattr(response, "results", []):
                if result.property_id in trace_urls:
                    result.counterexample_vcd = trace_urls[result.property_id]
            return {
                "run_id": run_id,
                "created_at": record["created_at"],
                "overall_status": response.overall_status.value,
                "property_count": len(request.property_batch.properties),
                "source_sha256": source_hashes,
            }
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for path in sorted(self.root.iterdir(), reverse=True):
            if not path.is_dir() or not re.fullmatch(r"\d{8}T\d{6}_[0-9a-f]{8}", path.name):
                continue
            file = path / "run.json"
            if not file.is_file():
                continue
            try:
                record = json.loads(file.read_text(encoding="utf-8"))
                verification = record.get("verification", {})
                items.append({
                    "run_id": record["run_id"],
                    "created_at": record["created_at"],
                    "design_top": record["design_top"],
                    "overall_status": verification.get("overall_status"),
                    "property_count": len(record.get("property_batch", {}).get("properties", [])),
                    "proof_mode": record.get("proof_mode"),
                    "solver": record.get("solver"),
                })
            except (OSError, ValueError, KeyError):
                continue
            if len(items) >= max(1, min(limit, 200)):
                break
        return items

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        if not re.fullmatch(r"\d{8}T\d{6}_[0-9a-f]{8}", run_id or ""):
            return None
        path = self.root / run_id / "run.json"
        if not path.is_file():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
