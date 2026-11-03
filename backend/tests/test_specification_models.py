import unittest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.app.main import app
from backend.app.models.specification_models import DesignSpecification, BehaviouralRequirement
from backend.app.models.design_ir import DesignIR, ModuleIR, PortIR, ModuleSummaryIR
from backend.app.services.llm.property_generator import PropertyGenerationService
from backend.app.services.llm.mock_provider import MockProvider

class SpecificationModelTests(unittest.TestCase):
    def make_spec(self, **overrides):
        values = dict(
            specification_id="counter-spec-v1", version="1.0", title="Counter requirements",
            design_top="counter", description="Counter behaviour defined independently of RTL.",
            requirements=[BehaviouralRequirement(requirement_id="REQ-01", statement="The 8-bit count value must remain within its unsigned representable range.")],
            approved_by=None, approval_status="draft"
        )
        values.update(overrides)
        spec = DesignSpecification(**values)
        if spec.approval_status == "approved":
            return spec.approve(spec.approved_by or "reviewer")
        return spec

    def test_specification_hash_is_stable(self):
        first = self.make_spec()
        second = self.make_spec()
        self.assertEqual(first.content_hash(), second.content_hash())

    def test_duplicate_requirement_ids_rejected(self):
        with self.assertRaises(ValidationError):
            self.make_spec(requirements=[
                BehaviouralRequirement(requirement_id="REQ-01", statement="The count must remain in range."),
                BehaviouralRequirement(requirement_id="REQ-01", statement="The count resets to zero.")
            ])

    def test_approved_spec_requires_reviewer(self):
        with self.assertRaises(ValidationError):
            self.make_spec(approved_by=None, approval_status="approved")

    def test_specification_validation_endpoint(self):
        client = TestClient(app)
        response = client.post("/api/specifications/validate", json=self.make_spec().model_dump(mode="json"))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["valid"])
        self.assertEqual(response.json()["requirement_count"], 1)
        self.assertEqual(len(response.json()["sha256"]), 64)

    def test_unapproved_specification_cannot_generate_properties(self):
        design = DesignIR(top_module="counter", source_files=["counter.sv"], modules=[ModuleIR(
            name="counter", ports=[PortIR(name="count", direction="output", bit_width=8, bits=list(range(8)))],
            summary=ModuleSummaryIR(port_count=1, output_port_count=1)
        )])
        spec = self.make_spec(approval_status="draft", approved_by=None)
        with self.assertRaisesRegex(ValueError, "must be reviewed and approved"):
            PropertyGenerationService(provider=MockProvider()).generate_candidate_properties(design, specification=spec)

    def test_rtl_only_generation_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "independent behavioural specification is required"):
            PropertyGenerationService(provider=MockProvider()).generate_candidate_properties({"top_module":"x","source_files":[],"modules":[]})

if __name__ == "__main__":
    unittest.main()
