"""Conservative candidate-property checks against a supplied DesignIR payload."""
from typing import Any
from backend.app.models.design_ir import DesignIR
from backend.app.models.property_models import (
    PropertyBatch, PropertyLifecycle, PropertyValidationIssue,
    PropertyValidationResult, PropertyValidationBatchResult
)

def validate_property_batch(design: DesignIR, batch: PropertyBatch) -> PropertyValidationBatchResult:
    if batch.design_top != design.top_module:
        raise ValueError(f"Batch design_top '{batch.design_top}' does not match DesignIR top_module '{design.top_module}'.")
    modules = {module.name: module for module in design.modules}
    results = []
    for prop in batch.properties:
        issues: list[PropertyValidationIssue] = []
        if prop.design_top != design.top_module:
            issues.append(PropertyValidationIssue(property_id=prop.property_id, code="TOP_MODULE_MISMATCH",
                message=f"Property design_top '{prop.design_top}' does not match '{design.top_module}'."))
        module = modules.get(prop.module)
        if module is None:
            issues.append(PropertyValidationIssue(property_id=prop.property_id, code="UNKNOWN_MODULE",
                message=f"Module '{prop.module}' is not present in the supplied DesignIR."))
        else:
            signal_map = {p.name: p.bit_width for p in module.ports}
            signal_map.update({n.name: n.bit_width for n in module.nets})
            for signal in prop.signals:
                if signal.name not in signal_map:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="UNKNOWN_SIGNAL",
                        message=f"Signal '{signal.name}' was not found in module '{prop.module}'."))
                elif signal.expected_width is not None and signal.expected_width != signal_map[signal.name]:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="SIGNAL_WIDTH_MISMATCH",
                        message=f"Signal '{signal.name}' has width {signal_map[signal.name]}, not expected width {signal.expected_width}."))
            if prop.clock:
                if prop.clock.signal not in signal_map:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="UNKNOWN_CLOCK",
                        message=f"Clock signal '{prop.clock.signal}' was not found in module '{prop.module}'."))
                else:
                    clock_port = next((p for p in module.ports if p.name == prop.clock.signal), None)
                    known_clock_bits = {str(bit) for candidate in module.clock_candidates for bit in candidate.get("bits", [])}
                    if clock_port and not any(str(bit) in known_clock_bits for bit in clock_port.bits):
                        issues.append(PropertyValidationIssue(property_id=prop.property_id, code="CLOCK_NOT_STRUCTURALLY_CONFIRMED",
                            message=f"'{prop.clock.signal}' exists, but no sequential or clock-enabled memory cell currently identifies it as a clock candidate.",
                            severity="warning"))
            if prop.reset:
                if prop.reset.signal not in signal_map:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="UNKNOWN_RESET",
                        message=f"Reset signal '{prop.reset.signal}' was not found in module '{prop.module}'."))
                elif not any(p.name == prop.reset.signal for p in module.ports):
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="RESET_ROLE_REVIEW",
                        message=f"'{prop.reset.signal}' exists but is not a top-level module port; confirm its reset role.",
                        severity="warning"))
        errors = [issue for issue in issues if issue.severity == "error"]
        lifecycle = PropertyLifecycle.DESIGN_VALID if not errors else PropertyLifecycle.REJECTED
        results.append(PropertyValidationResult(
            property_id=prop.property_id, schema_valid=True, design_valid=not errors,
            lifecycle=lifecycle, issues=issues))
    summary = {
        "total": len(results),
        "design_valid": sum(r.design_valid for r in results),
        "rejected": sum(not r.design_valid for r in results),
        "verification_not_run": len(results)
    }
    return PropertyValidationBatchResult(design_top=design.top_module, results=results, summary=summary)
