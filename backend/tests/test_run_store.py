import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from backend.app.services.formal.run_store import FormalRunStore
from backend.app.models.property_models import VerificationStatus
from backend.app.models.specification_models import DesignSpecification, BehaviouralRequirement


class RunStoreTests(unittest.TestCase):
    def test_save_list_and_retrieve_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FormalRunStore(tmp)
            request = SimpleNamespace(
                verilog_sources={"alu.v": "module alu; endmodule"},
                top_module="alu",
                design_ir=SimpleNamespace(top_module="alu", model_dump=lambda **kwargs: {"top_module": "alu"}),
                proof_mode="prove",
                solver="z3",
                depth=20,
                property_batch=SimpleNamespace(batch_id="b1", properties=[SimpleNamespace(property_id="p1")], model_dump=lambda **kwargs: {"batch_id": "b1", "properties": [{"property_id": "p1"}]}),
                specification=None,
            )
            response = SimpleNamespace(overall_status=VerificationStatus.PASS, model_dump=lambda **kwargs: {"overall_status": "pass", "results": []})
            metadata = store.save(request, response)
            self.assertEqual(metadata["overall_status"], "pass")
            self.assertEqual(len(store.list_runs()), 1)
            record = store.get_run(metadata["run_id"])
            self.assertEqual(record["design_top"], "alu")
            self.assertTrue((Path(tmp) / metadata["run_id"] / "rtl" / "alu.v").is_file())


    def test_save_preserves_independent_specification_and_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FormalRunStore(tmp)
            spec = DesignSpecification(
                specification_id="alu-spec-v1", title="ALU requirements", design_top="alu",
                requirements=[BehaviouralRequirement(requirement_id="REQ-01", statement="The ALU output equals the specified operation result.")],
            ).approve("reviewer")
            request = SimpleNamespace(
                verilog_sources={"alu.v": "module alu; endmodule"}, top_module="alu",
                design_ir=SimpleNamespace(top_module="alu", model_dump=lambda **kwargs: {"top_module": "alu"}),
                proof_mode="prove", solver="z3", depth=20, specification=spec,
                property_batch=SimpleNamespace(batch_id="b1", properties=[SimpleNamespace(property_id="p1")], model_dump=lambda **kwargs: {"batch_id": "b1", "properties": [{"property_id": "p1"}]})
            )
            response = SimpleNamespace(overall_status=VerificationStatus.PASS, model_dump=lambda **kwargs: {"overall_status": "pass", "results": []})
            metadata = store.save(request, response)
            record = store.get_run(metadata["run_id"])
            self.assertEqual(record["behavioural_specification"]["specification_id"], "alu-spec-v1")
            self.assertEqual(record["specification_sha256"], spec.content_hash())

    def test_save_persists_generation_audit_and_reset_environment_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FormalRunStore(tmp)
            audit = {
                "prompt_version": "2.3",
                "system_prompt": "system snapshot",
                "user_prompts": ["user snapshot"],
                "raw_responses": ["raw candidate JSON"],
                "source_design_sha256": "abc",
            }
            reset_contract = {
                "signal": "rst_n", "polarity": "active_low",
                "reviewed_by": "reviewer", "rationale": "Reset is asserted before release."
            }
            request = SimpleNamespace(
                verilog_sources={"fifo.sv": "module fifo; endmodule"},
                top_module="fifo",
                design_ir=SimpleNamespace(top_module="fifo", model_dump=lambda **kwargs: {"top_module": "fifo"}),
                proof_mode="prove", solver="z3", depth=20,
                property_batch=SimpleNamespace(batch_id="b1", properties=[SimpleNamespace(property_id="p1")], model_dump=lambda **kwargs: {"batch_id": "b1", "properties": [{"property_id": "p1"}]}),
                specification=None,
                generation_audit=audit,
                initial_reset_contract=reset_contract,
            )
            response = SimpleNamespace(overall_status=VerificationStatus.PASS, model_dump=lambda **kwargs: {"overall_status": "pass", "results": []})
            metadata = store.save(request, response)
            record = store.get_run(metadata["run_id"])
            self.assertEqual(record["generation_audit"], audit)
            self.assertEqual(record["initial_reset_contract"], reset_contract)

    def test_rejects_path_like_run_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = FormalRunStore(tmp)
            self.assertIsNone(store.get_run("../secrets"))


if __name__ == "__main__":
    unittest.main()
