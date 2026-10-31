"""High-level RTL analysis service."""
from pathlib import Path
import json, tempfile
from backend.app.models.design_ir import DesignIR
from backend.app.services.hdl.ir_builder import build_design_ir
from backend.app.services.hdl.yosys_runner import YosysRunner

class HDLAnalysisService:
    def __init__(self, runner: YosysRunner | None = None): self.runner = runner or YosysRunner()
    def analyze(self, source_files: list[Path], top_module: str) -> tuple[DesignIR, str]:
        with tempfile.TemporaryDirectory(prefix="rtl_analysis_") as temp_dir:
            json_path = Path(temp_dir) / "design.json"
            log = self.runner.run(source_files, top_module, json_path)
            raw = json.loads(json_path.read_text(encoding="utf-8"))
            ir = build_design_ir(raw, [str(p) for p in source_files], top_module)
            return ir, log
