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
            # Internal nets are accepted only when the elaborated DesignIR
            # contains an exact named net in the selected module. The checker
            # synthesizer creates an explicit hierarchical probe alias
            # (dut.<net>) and validates width/signedness before use.
            port_map = {p.name: p for p in module.ports}
            net_map = {n.name: n for n in module.nets if n.name not in port_map}
            for signal in prop.signals:
                port = port_map.get(signal.name)
                net = net_map.get(signal.name)
                actual = port or net
                if actual is None:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="UNKNOWN_SIGNAL",
                        message=f"Signal '{signal.name}' was not found as a port or named net in module '{prop.module}'."))
                    continue
                if port is not None and port.direction not in {"input", "output"}:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="UNSUPPORTED_PORT_DIRECTION",
                        message=f"Port '{signal.name}' has direction '{port.direction}', which the formal wrapper does not support."))
                if actual.is_signed:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="SIGNED_SIGNAL_UNSUPPORTED",
                        message=f"Signal '{signal.name}' is signed. Signed expression semantics are not yet supported; this property is rejected rather than coerced to unsigned."))
                if signal.expected_width is not None and signal.expected_width != actual.bit_width:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="SIGNAL_WIDTH_MISMATCH",
                        message=f"Signal '{signal.name}' has width {actual.bit_width}, not expected width {signal.expected_width}."))
            if prop.clock:
                clock_port = port_map.get(prop.clock.signal)
                if clock_port is None:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="UNKNOWN_OR_INTERNAL_CLOCK",
                        message=f"Clock '{prop.clock.signal}' must be a top-level input port of '{prop.module}'."))
                elif clock_port.direction != "input" or clock_port.bit_width != 1:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="INVALID_CLOCK_PORT",
                        message=f"Clock '{prop.clock.signal}' must be a 1-bit input port."))
                else:
                    has_matching_clock = any(
                        (candidate.get("signal") or candidate.get("name")) == prop.clock.signal
                        and [str(bit) for bit in candidate.get("bits", [])] == [str(bit) for bit in clock_port.bits]
                        for candidate in module.clock_candidates
                    )
                    if not has_matching_clock:
                        has_sequential_state = bool(module.registers or any(access.clocked for access in module.memory_accesses))
                        issues.append(PropertyValidationIssue(property_id=prop.property_id, code="CLOCK_NOT_STRUCTURALLY_CONFIRMED",
                            message=f"'{prop.clock.signal}' exists, but no sequential or clock-enabled memory cell currently identifies it as a clock candidate.",
                            severity="error" if has_sequential_state else "warning"))
            if prop.reset:
                reset_port = port_map.get(prop.reset.signal)
                if reset_port is None or reset_port.direction != "input":
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="INVALID_RESET_PORT",
                        message=f"Reset '{prop.reset.signal}' must be a top-level input port."))
                elif reset_port.bit_width != 1:
                    issues.append(PropertyValidationIssue(property_id=prop.property_id, code="INVALID_RESET_WIDTH",
                        message=f"Reset '{prop.reset.signal}' must be 1 bit."))
                else:
                    reset_bits = [str(bit) for bit in reset_port.bits]
                    reset_candidates = [
                        candidate for candidate in module.reset_candidates
                        if [str(bit) for bit in candidate.get("bits", [])] == reset_bits
                        and candidate.get("kind") in {"asynchronous", "synchronous"}
                    ]
                    if not reset_candidates:
                        issues.append(PropertyValidationIssue(property_id=prop.property_id, code="RESET_NOT_STRUCTURALLY_CONFIRMED",
                            message=f"'{prop.reset.signal}' is not identified on a supported sequential reset pin."))
                    elif prop.reset.asynchronous is not None:
                        kinds = {candidate.get("kind") for candidate in reset_candidates}
                        if len(kinds) != 1 or (next(iter(kinds)) == "asynchronous") != prop.reset.asynchronous:
                            issues.append(PropertyValidationIssue(property_id=prop.property_id, code="RESET_TIMING_MISMATCH",
                                message=f"Reset timing metadata for '{prop.reset.signal}' conflicts with the elaborated sequential-cell reset kind."))
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
