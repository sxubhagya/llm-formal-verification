"""Fail-closed checker synthesis for Boolean expressions and a bounded SVA subset.

Build 11 supports clocked implication properties (|-> and |=>), plus $past,
$stable, $rose and $fell over simple expressions. It intentionally does not
claim full IEEE 1800 SVA support. Reset disabling is sampled synchronously at
the declared clock edge; asynchronous abort semantics are rejected.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field

from backend.app.models.design_ir import DesignIR, ModuleIR
from backend.app.models.property_models import PropertyBatch, AssumptionReviewStatus, AssertionLanguage
from backend.app.models.formal_models import InitialResetContract


@dataclass
class SynthesizedPropertyMeta:
    property_id: str
    name: str
    assertion_label: str
    cover_label: str | None = None
    is_implication: bool = False
    antecedent: str | None = None
    consequent: str | None = None


@dataclass
class SynthesizedCheckerResult:
    wrapper_module_name: str
    wrapper_source_code: str
    top_module: str
    properties: list[SynthesizedPropertyMeta] = field(default_factory=list)
    has_clock: bool = True
    clock_signal: str = "clk"
    reset_signal: str | None = None
    reset_polarity: str = "active_low"
    warnings: list[str] = field(default_factory=list)


_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_TOKEN = re.compile(
    r"\s*(?:(\d+'[sS]?[bBoOdDhH][0-9a-fA-F_xXzZ?]+)|(\d+)|"
    r"([A-Za-z_][A-Za-z0-9_$]*)|"
    r"(===|!==|==|!=|<=|>=|&&|\|\||<<|>>|\+|-|\*|/|%|&|\||\^|~|!|<|>|\?|:|\(|\)|\[|\]|\.))"
)
_ALLOWED_OPS = {"===", "!==", "==", "!=", "<=", ">=", "&&", "||", "<<", ">>", "+", "-", "*", "/", "%", "&", "|", "^", "~", "!", "<", ">", "?", ":", "(", ")", "[", "]", "."}
_TEMPORAL_FN = re.compile(r"\$(past|stable|rose|fell)\(([^()]+)\)")




def _decode_bit_parameter(value: object) -> int | None:
    """Decode Yosys JSON one-bit/binary-string parameter encodings."""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if value in (0, 1) else None
    raw = str(value).strip().replace("_", "")
    if raw in {"0", "1"}:
        return int(raw)
    match = re.fullmatch(r"[0-9]+'[sS]?[bB]([01]+)", raw)
    if match:
        number = int(match.group(1), 2)
        return number if number in (0, 1) else None
    if re.fullmatch(r"[01]+", raw):
        number = int(raw, 2)
        return number if number in (0, 1) else None
    return None

class CheckerSynthesizer:
    """Compile safe same-sample Boolean properties and a restricted clocked SVA subset."""

    def __init__(self, check_vacuity: bool = False):
        self.check_vacuity = check_vacuity

    def _validate_expr(self, expression: str, known_signals: set[str], declared_signals: set[str] | None = None) -> str:
        expr = expression.strip()
        if not expr or len(expr) > 2000:
            raise ValueError("Property expression is empty or exceeds 2000 characters.")
        if any(x in expr for x in ("|->", "|=>", "->", "`", ";", "//", "/*", "*/")):
            raise ValueError("Temporal operators belong at the property level; statements, comments and directives are unsupported.")
        pos, identifiers, tokens = 0, set(), []
        while pos < len(expr):
            match = _TOKEN.match(expr, pos)
            if not match:
                raise ValueError(f"Unsupported token in property expression near: {expr[pos:pos+24]!r}")
            literal, number, ident, op = match.groups()
            token = literal or number or ident or op
            tokens.append(token)
            if ident:
                identifiers.add(ident)
            if op and op not in _ALLOWED_OPS:
                raise ValueError(f"Unsupported operator {op!r}.")
            pos = match.end()
        unknown = sorted(identifiers - known_signals)
        if unknown:
            raise ValueError("Expression references unknown signals/identifiers: " + ", ".join(unknown))
        if declared_signals is not None:
            undeclared = sorted(identifiers - declared_signals)
            if undeclared:
                raise ValueError("Expression uses signals not declared in the property's signals list: " + ", ".join(undeclared))
        stack, pairs = [], {")": "(", "]": "["}
        for token in tokens:
            if token in "([": stack.append(token)
            elif token in ")]":
                if not stack or stack.pop() != pairs[token]:
                    raise ValueError("Unbalanced parentheses or bit-select brackets in expression.")
        if stack:
            raise ValueError("Unbalanced parentheses or bit-select brackets in expression.")
        return expr

    @staticmethod
    def _validate_port_selects(expression: str, ports: dict[str, Any]) -> None:
        """Validate constant bit/part-selects against the original port indices."""
        select_pattern = re.compile(r"([A-Za-z_][A-Za-z0-9_$]*)\s*\[([^\]]+)\]")
        for match in select_pattern.finditer(expression):
            name, selection = match.group(1), match.group(2).strip()
            port = ports.get(name)
            if port is None:
                continue
            if ":" in selection:
                parts = [part.strip() for part in selection.split(":")]
                if len(parts) != 2 or not all(re.fullmatch(r"-?\d+", part) for part in parts):
                    raise ValueError(f"Dynamic or unsupported part-select on port '{name}' is rejected.")
                indices = [int(part) for part in parts]
            else:
                if not re.fullmatch(r"-?\d+", selection):
                    raise ValueError(f"Dynamic bit-select on port '{name}' is not supported by the current checker.")
                indices = [int(selection)]
            low = port.offset
            high = port.offset + port.bit_width - 1
            if any(index < low or index > high for index in indices):
                raise ValueError(
                    f"Select {name}[{selection}] is outside the declared port index range [{low}:{high}]."
                )

    @staticmethod
    def _safe_identifier(value: str, what: str) -> str:
        if not _IDENT.fullmatch(value):
            raise ValueError(f"Invalid {what} identifier: {value!r}")
        return value

    @staticmethod
    def _split_implication(expression: str) -> tuple[str | None, str | None, str | None]:
        depth, found = 0, []
        i = 0
        while i < len(expression):
            if expression[i] == "(": depth += 1
            elif expression[i] == ")": depth -= 1
            elif depth == 0 and expression.startswith("|->", i):
                found.append((i, "|->")); i += 2
            elif depth == 0 and expression.startswith("|=>", i):
                found.append((i, "|=>")); i += 2
            i += 1
        if not found:
            return None, None, None
        if len(found) != 1:
            raise ValueError("Exactly one top-level |-> or |=> implication is supported per property.")
        index, operator = found[0]
        antecedent, consequent = expression[:index].strip(), expression[index + 3:].strip()
        if not antecedent or not consequent:
            raise ValueError("Both antecedent and consequent are required for an implication property.")
        return antecedent, consequent, operator

    def _prepare_temporal_operand(self, expression: str, known: set[str], declared: set[str], declared_widths: dict[str, int | None]) -> tuple[str, int, bool]:
        """Validate an operand and lower a small set of temporal sampling functions."""
        max_past, has_temporal = 0, False
        replacements: list[tuple[str, str]] = []
        working = expression
        while True:
            match = _TEMPORAL_FN.search(working)
            if not match:
                # A dollar inside a legal escaped/simple identifier is not a
                # system function (e.g. data$valid). Reject only a system-task
                # token beginning with '$' at an identifier boundary.
                if re.search(r"(?<![A-Za-z0-9_$])\$[A-Za-z_]", working):
                    raise ValueError("Only $past(expr), $stable(expr), $rose(expr), and $fell(expr) are supported; nested or other system functions are rejected.")
                break
            fn, argument = match.group(1), match.group(2).strip()
            if "__TEMPORAL_SLOT_" in argument:
                raise ValueError("Nested temporal sampling functions are unsupported.")
            depth = 1
            # Optional depth is accepted only for $past(expr, N).
            if fn == "past":
                parts = [p.strip() for p in argument.rsplit(",", 1)]
                if len(parts) == 2 and parts[1].isdigit():
                    depth = int(parts[1])
                    argument = parts[0]
                if not 1 <= depth <= 10:
                    raise ValueError("$past depth must be between 1 and 10.")
            elif "," in argument:
                raise ValueError(f"${fn} accepts exactly one expression argument.")
            self._validate_expr(argument, known, declared_signals=declared)
            if fn in {"rose", "fell"}:
                if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_$]*", argument) or declared_widths.get(argument) != 1:
                    raise ValueError(f"${fn} is currently restricted to a declared 1-bit signal.")
            max_past = max(max_past, depth if fn == "past" else 1)
            has_temporal = True
            placeholder = f"__TEMPORAL_SLOT_{len(replacements)}__"
            if fn == "past": lowered = f"$past({argument}, {depth})" if depth > 1 else f"$past({argument})"
            elif fn == "stable": lowered = f"(({argument}) == $past({argument}))"
            elif fn == "rose": lowered = f"(({argument}) && !$past({argument}))"
            else: lowered = f"(!({argument}) && $past({argument}))"
            replacements.append((placeholder, lowered))
            working = working[:match.start()] + placeholder + working[match.end():]
        self._validate_expr(working, known | {p for p, _ in replacements}, declared_signals=declared | {p for p, _ in replacements})
        for placeholder, lowered in replacements:
            working = re.sub(r"(?<![A-Za-z0-9_$])" + re.escape(placeholder) + r"(?![A-Za-z0-9_$])", lambda _m, value=lowered: value, working)
        return working, max_past, has_temporal

    def synthesize(
        self, design_ir: DesignIR, property_batch: PropertyBatch,
        target_module_name: str | None = None,
        initial_reset_contract: InitialResetContract | None = None,
        internal_probe_ports: dict[str, str] | None = None,
    ) -> SynthesizedCheckerResult:
        top = self._safe_identifier(target_module_name or property_batch.design_top or design_ir.top_module, "module")
        module: ModuleIR | None = next((m for m in design_ir.modules if m.name == top), None)
        if module is None:
            raise ValueError(f"Target module {top!r} not found in DesignIR.")
        if len(property_batch.properties) != 1:
            raise ValueError("CheckerSynthesizer accepts exactly one property per run.")
        prop = property_batch.properties[0]
        if prop.module != top or prop.design_top != design_ir.top_module:
            raise ValueError("Property module/design_top does not match the selected design.")

        port_objects = {p.name: p for p in module.ports}
        net_objects = {n.name: n for n in module.nets if n.name not in port_objects}
        known = set(port_objects) | set(net_objects)
        declared = {s.name for s in prop.signals}
        actual_objects = {**net_objects, **port_objects}
        declared_widths = {s.name: actual_objects[s.name].bit_width for s in prop.signals if s.name in actual_objects}
        for signal in prop.signals:
            actual = actual_objects.get(signal.name)
            if actual is None:
                raise ValueError(f"Signal '{signal.name}' is not present in the selected module's elaborated ports or named nets.")
            if actual.is_signed:
                raise ValueError(f"Signed signal '{signal.name}' is unsupported by the current expression checker.")
            if signal.name in port_objects and actual.direction not in {"input", "output"}:
                raise ValueError(f"Port '{signal.name}' direction '{actual.direction}' is unsupported.")
            if signal.expected_width is not None and actual.bit_width != signal.expected_width:
                raise ValueError(
                    f"Signal '{signal.name}' expected width {signal.expected_width} does not match "
                    f"the elaborated width {actual.bit_width}."
                )
        self._validate_port_selects(prop.expression, {**port_objects, **net_objects})
        clock = prop.clock.signal if prop.clock else None
        inferred_clock = False
        has_sequential_state = bool(module.registers or any(access.clocked for access in module.memory_accesses))
        if not clock and has_sequential_state:
            # A Boolean expression on a sequential design is a sampled invariant,
            # not a combinational assertion. Infer only when structural analysis
            # identifies exactly one named clock input; otherwise fail closed.
            candidates = {
                str(candidate.get("signal") or candidate.get("name"))
                for candidate in module.clock_candidates
                if candidate.get("signal") or candidate.get("name")
            }
            if len(candidates) == 1:
                clock = next(iter(candidates))
                inferred_clock = True
            elif len(candidates) > 1:
                raise ValueError(
                    "Property has no clock context and the design has multiple clock candidates; "
                    "select a clock explicitly."
                )
            else:
                raise ValueError(
                    "Sequential design has no uniquely identified clock. Add an explicit property clock."
                )
        has_clock = bool(clock)
        inferred_edge = "posedge"
        if inferred_clock:
            polarities = {
                _decode_bit_parameter(register.parameters.get("CLK_POLARITY"))
                for register in module.registers
                if register.clock_bits
            }
            if len(polarities) != 1 or None in polarities:
                raise ValueError(
                    "The clock edge cannot be inferred unambiguously from the sequential cells. "
                    "Specify the clock edge explicitly in the property metadata."
                )
            inferred_edge = "posedge" if next(iter(polarities)) == 1 else "negedge"
        clock_edge = prop.clock.edge if prop.clock else inferred_edge
        if has_clock:
            self._safe_identifier(clock, "clock signal")
            clock_port = next((p for p in module.ports if p.name == clock and p.direction == "input" and p.bit_width == 1), None)
            if clock_port is None:
                raise ValueError(f"Property clock {clock!r} is not a 1-bit input port of the selected module.")
            if has_sequential_state:
                matching_candidates = [
                    candidate for candidate in module.clock_candidates
                    if (candidate.get("signal") or candidate.get("name")) == clock
                    and [str(bit) for bit in candidate.get("bits", [])] == [str(bit) for bit in clock_port.bits]
                ]
                if not matching_candidates:
                    raise ValueError(
                        f"Clock '{clock}' is not structurally connected to the sequential state in the selected module."
                    )
                candidate_bits = [str(bit) for bit in clock_port.bits]
                polarities = {
                    _decode_bit_parameter(register.parameters.get("CLK_POLARITY"))
                    for register in module.registers
                    if [str(bit) for bit in register.clock_bits] == candidate_bits
                }
                polarities.update({
                    _decode_bit_parameter(access.parameters.get("CLK_POLARITY"))
                    for access in module.memory_accesses
                    if access.clocked and [str(bit) for bit in access.clock_bits] == candidate_bits
                })
                if len(polarities) != 1 or None in polarities:
                    raise ValueError(
                        f"Active edge for clock '{clock}' is not established unambiguously by Yosys metadata; explicit metadata alone cannot override missing structural evidence."
                    )
                structural_edge = "posedge" if next(iter(polarities)) == 1 else "negedge"
                if clock_edge != structural_edge:
                    raise ValueError(
                        f"Clock edge mismatch for '{clock}': property requests {clock_edge}, but Yosys sequential-cell metadata indicates {structural_edge}."
                    )

        reset_signal = prop.reset.signal if prop.reset else (
            initial_reset_contract.signal if initial_reset_contract else None
        )
        reset_active = None
        if reset_signal:
            reset_port = next((p for p in module.ports if p.name == reset_signal), None)
            if reset_port is None or reset_port.direction != "input" or reset_port.bit_width != 1:
                raise ValueError(f"Reset signal {reset_signal!r} must be a 1-bit top-level input port.")
            reset_bits = [str(bit) for bit in reset_port.bits]
            matching_resets = [
                candidate for candidate in module.reset_candidates
                if [str(bit) for bit in candidate.get("bits", [])] == reset_bits
                and candidate.get("kind") in {"asynchronous", "synchronous"}
            ]
            if not matching_resets:
                raise ValueError(
                    f"Reset '{reset_signal}' is not structurally connected to a supported reset pin in the selected design."
                )
            reset_kinds = {candidate.get("kind") for candidate in matching_resets}
            if len(reset_kinds) != 1:
                raise ValueError(f"Reset timing for '{reset_signal}' is ambiguous across sequential elements.")
            structural_async = next(iter(reset_kinds)) == "asynchronous"
            if prop.reset is not None and prop.reset.asynchronous is not None and prop.reset.asynchronous != structural_async:
                raise ValueError(
                    f"Reset timing mismatch for '{reset_signal}': property metadata says "
                    f"{'asynchronous' if prop.reset.asynchronous else 'synchronous'}, but Yosys metadata says "
                    f"{'asynchronous' if structural_async else 'synchronous'}."
                )
            polarity_key = "ARST_POLARITY" if structural_async else "SRST_POLARITY"
            reset_polarities = {
                _decode_bit_parameter(register.parameters.get(polarity_key))
                for register in module.registers
                if [str(bit) for bit in register.reset_bits] == reset_bits
            }
            if len(reset_polarities) != 1 or None in reset_polarities:
                raise ValueError(
                    f"Reset polarity for '{reset_signal}' is not established unambiguously by Yosys metadata."
                )
            structural_polarity = "active_high" if next(iter(reset_polarities)) == 1 else "active_low"
            requested_polarity = prop.reset.polarity if prop.reset else initial_reset_contract.polarity
            if requested_polarity != structural_polarity:
                raise ValueError(
                    f"Reset polarity mismatch for '{reset_signal}': metadata says {requested_polarity}, "
                    f"but Yosys metadata indicates {structural_polarity}."
                )

        initial_reset_active = None
        if initial_reset_contract is not None:
            if not has_clock:
                raise ValueError("An initial reset contract requires a structurally identified clock.")
            if reset_signal != initial_reset_contract.signal:
                raise ValueError("Initial reset contract must refer to the reset signal structurally validated for this property.")
            initial_reset_active = (
                f"!{initial_reset_contract.signal}"
                if initial_reset_contract.polarity == "active_low"
                else initial_reset_contract.signal
            )

        if prop.assertion_language == AssertionLanguage.BOOLEAN:
            expression = self._validate_expr(prop.expression, known, declared_signals=declared)
            antecedent = consequent = None
            operator = None
            max_past = 0
        elif prop.assertion_language == AssertionLanguage.SVA:
            raw = prop.expression.strip()
            # Accept standard SVA disable iff only as a leading clause, and lower it
            # to a sampled reset guard using the separately reviewed ResetContext.
            disable = re.match(r"^disable\s+iff\s*\((.*?)\)\s*(.*)$", raw, re.DOTALL)
            if disable:
                disable_expr, raw = disable.group(1).strip(), disable.group(2).strip()
                if not reset_signal:
                    raise ValueError("disable iff requires an explicit reset context in the property metadata.")
                if prop.reset.asynchronous is not False:
                    raise ValueError("Build 14 requires reset.asynchronous=false for sampled disable-iff semantics. Asynchronous or unspecified reset timing is rejected rather than approximated.")
                if not prop.reset.active_during_disable:
                    raise ValueError("The checker only supports the standard active-during-disable reset interpretation.")
                expected_disable = f"!{reset_signal}" if prop.reset.polarity == "active_low" else reset_signal
                if re.sub(r"\s+", "", disable_expr) != re.sub(r"\s+", "", expected_disable):
                    raise ValueError("disable iff expression must match the declared reset signal and polarity exactly.")
                reset_active = expected_disable
            antecedent_raw, consequent_raw, operator = self._split_implication(raw)
            if operator:
                antecedent, past_a, temporal_a = self._prepare_temporal_operand(antecedent_raw, known, declared, declared_widths)
                consequent, past_c, temporal_c = self._prepare_temporal_operand(consequent_raw, known, declared, declared_widths)
                max_past = max(past_a + (1 if operator == "|=>" else 0), past_c, 1 if operator == "|=>" else 0)
            else:
                expression, max_past, _ = self._prepare_temporal_operand(raw, known, declared, declared_widths)
                antecedent = consequent = None
            if not has_clock:
                raise ValueError("Clocked SVA properties require an explicit clock context.")
        else:
            raise ValueError("Build 11 supports boolean_expression and the documented restricted SystemVerilog Assertion subset only.")

        wrapper = self._safe_identifier(f"formal_{top}_{re.sub(r'[^A-Za-z0-9_]', '_', prop.property_id)}", "wrapper")
        port_decls, port_conns = [], []
        internal_probe_ports = internal_probe_ports or {}
        for port in module.ports:
            self._safe_identifier(port.name, "port")
            if port.bit_width > 1 or port.offset != 0 or port.upto:
                left = port.offset if port.upto else port.offset + port.bit_width - 1
                right = port.offset + port.bit_width - 1 if port.upto else port.offset
                width = f"[{left}:{right}] "
            else:
                width = ""
            if port.direction not in {"input", "output"}:
                raise ValueError(
                    f"Port '{port.name}' has direction '{port.direction}', which this checker wrapper cannot model safely."
                )
            direction = "input" if port.direction == "input" else "output"
            port_decls.append(f"    {direction} wire {width}{port.name}")
            port_conns.append(f"        .{port.name}({port.name})")

        assumptions, warnings = [], []
        if inferred_clock:
            warnings.append(
                f"No clock was supplied for property {prop.property_id}; sampled it on the unique structurally inferred clock '{clock}'."
            )
        for asm in prop.assumptions:
            if asm.status != AssumptionReviewStatus.ACCEPTED:
                warnings.append(f"Assumption {asm.assumption_id} was not accepted and was excluded from the formal environment.")
                continue
            if not asm.reviewed_by:
                raise ValueError(f"Accepted assumption {asm.assumption_id} lacks reviewer identity.")
            self._validate_port_selects(asm.statement, port_objects)
            assumptions.append(self._validate_expr(asm.statement, known, declared_signals=None))

        label = "assert_property_0"
        lines = ["`default_nettype none", f"module {wrapper} (", ",\n".join(port_decls), ");"]
        # Internal references must arrive through explicit Yosys-netlist probe
        # output ports. Hierarchical references (dut.signal) are deliberately
        # not used: Yosys 0.33 can parse them while producing a disconnected alias.
        for signal in prop.signals:
            if signal.name in net_objects:
                probe_name = internal_probe_ports.get(signal.name)
                if not probe_name:
                    raise ValueError(
                        f"Internal signal '{signal.name}' has no Yosys-generated probe port. "
                        "The original RTL must be instrumented before checker synthesis."
                    )
                self._safe_identifier(signal.name, "internal net")
                self._safe_identifier(probe_name, "internal probe port")
                net = net_objects[signal.name]
                if net.bit_width > 1 or net.offset != 0 or net.upto:
                    left = net.offset if net.upto else net.offset + net.bit_width - 1
                    right = net.offset + net.bit_width - 1 if net.upto else net.offset
                    width = f"[{left}:{right}] "
                else:
                    width = ""
                lines.append(f"    wire {width}{signal.name};")
                port_conns.append(f"        .{probe_name}({signal.name})")
        lines.extend([f"    {top} dut (", ",\n".join(port_conns), "    );"])
        lines.append("`ifdef FORMAL")
        if has_clock:
            lines.append(f"    reg [3:0] formal_past_count = 0;")
            if initial_reset_active:
                lines.append("    reg formal_initial_reset_seen = 1'b0;")
            lines.append(f"    always @({clock_edge} {clock}) begin")
            if initial_reset_active:
                lines.append(f"        if (!formal_initial_reset_seen) begin assume ({initial_reset_active}); formal_initial_reset_seen <= 1'b1; end")
            if reset_active:
                lines.append(f"        if ({reset_active}) formal_past_count <= 0;")
                lines.append("        else if (formal_past_count < 11) formal_past_count <= formal_past_count + 1'b1;")
                lines.append(f"        if (!({reset_active})) begin")
            else:
                lines.append("        if (formal_past_count < 11) formal_past_count <= formal_past_count + 1'b1;")
                lines.append("        begin")
            for assumption in assumptions:
                lines.append(f"            assume ({assumption});")
            if prop.assertion_language == AssertionLanguage.BOOLEAN:
                guard = "formal_initial_reset_seen" if initial_reset_active else "1'b1"
                lines.append(f"            if ({guard}) {label}: assert ({expression});")
            elif operator == "|->":
                guard = f"formal_past_count >= {max_past}" if max_past else "1'b1"
                if initial_reset_active:
                    guard = "formal_initial_reset_seen && (" + guard + ")"
                lines.append(f"            if ({guard} && ({antecedent})) {label}: assert ({consequent});")
            elif operator == "|=>":
                guard_terms = [f"formal_past_count >= {max_past}", f"$past({antecedent})"]
                if initial_reset_active:
                    guard_terms.insert(0, "formal_initial_reset_seen")
                if reset_active:
                    guard_terms.append(f"!$past({reset_active})")
                lines.append(f"            if ({' && '.join(guard_terms)}) {label}: assert ({consequent});")
            else:
                guard = f"formal_past_count >= {max_past}" if max_past else "1'b1"
                if initial_reset_active:
                    guard = "formal_initial_reset_seen && (" + guard + ")"
                lines.append(f"            if ({guard}) {label}: assert ({expression});")
            lines.extend(["        end", "    end"])
        else:
            lines.append("    always @(*) begin")
            for assumption in assumptions:
                lines.append(f"        assume ({assumption});")
            lines.append(f"        {label}: assert ({expression});")
            lines.append("    end")
        lines.extend(["`endif", "endmodule", "`default_nettype wire", ""])
        if prop.assertion_language == AssertionLanguage.SVA:
            warnings.append("Build 11 supports a restricted SVA subset: one clocked implication (|-> or |=>), or a sampled Boolean expression, with $past/$stable/$rose/$fell over simple operands.")
            warnings.append("disable iff is lowered to a sampled reset guard. Asynchronous abort semantics, ## delays, repetition, throughout, until, intersect, multi-clock properties and full IEEE 1800 SVA are not supported.")
        else:
            warnings.append("Same-sample Boolean property; temporal operators are not inferred.")
        return SynthesizedCheckerResult(
            wrapper_module_name=wrapper,
            wrapper_source_code="\n".join(lines),
            top_module=top,
            properties=[SynthesizedPropertyMeta(prop.property_id, prop.name, label, is_implication=bool(operator), antecedent=antecedent, consequent=consequent)],
            has_clock=has_clock,
            clock_signal=clock or "",
            reset_signal=reset_signal,
            reset_polarity=prop.reset.polarity if prop.reset else (initial_reset_contract.polarity if initial_reset_contract else "active_low"),
            warnings=warnings,
        )
