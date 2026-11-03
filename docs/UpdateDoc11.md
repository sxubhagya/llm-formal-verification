# UpdateDoc11 — Temporal Formal Verification

**Build:** 11.0 alpha  
**Base:** Build 10.2  
**Date:** 1 November 2026

## Objective

Extend the formal-property pipeline from same-sample Boolean assertions to a conservative, explicitly clocked subset of SystemVerilog Assertions (SVA), enabling properties that relate values across clock cycles.

## Implemented

1. **Restricted SVA checker synthesis**
   - Supports one top-level `|->` (overlapped implication) or `|=>` (non-overlapped implication) per property.
   - Supports sampled Boolean SVA properties with an explicit clock context.
   - Supports `$past(expr)` and `$past(expr, N)` for depths 1–10.
   - Supports `$stable(expr)`, `$rose(signal)`, and `$fell(signal)`; `$rose`/`$fell` are restricted to declared 1-bit signals.
   - Uses a formal past-valid counter to avoid asserting temporal expressions before enough sampled history exists.
   - Requires a property-specific 1-bit input clock and respects `posedge`/`negedge` selection.

2. **Reset handling (conservative)**
   - Supports leading `disable iff (...)` only when it exactly matches explicit reset metadata.
   - Reset metadata must explicitly declare `asynchronous=false`; reset timing that is asynchronous or unspecified is rejected.
   - Disable semantics are lowered to a sampled reset guard at the declared clock edge.
   - A previous-cycle reset guard is added for non-overlapped implications to avoid carrying pending obligations across a sampled reset.

3. **Fail-closed SVA subset**
   - Rejects unsupported temporal syntax instead of approximating it.
   - Not supported: full IEEE 1800 SVA, `##` delays, repetition, nested/compound temporal sequences, `throughout`, `until`, `intersect`, multi-clock properties, asynchronous `disable iff` abort semantics, and arbitrary system functions.
   - One property is still synthesized and executed independently per SBY task.

4. **LLM prompt update**
   - Prompt version raised to 1.2.
   - LLM is instructed to emit `systemverilog_assertion` only for the restricted subset and to provide explicit clock metadata.
   - LLM is instructed not to invent synchronous reset semantics for asynchronous or unknown reset timing.

5. **Sequential example**
   - Added `rtl/examples/counter_sync/counter_sync.sv` with a synchronous active-low reset counter.
   - Added `formal/examples/property_schema/counter_sync_temporal_property_batch.json` with next-cycle increment and hold properties.

6. **Regression tests**
   - Added synthesis tests for `|->` and `|=>`.
   - Added tests for rejection of asynchronous and unspecified reset timing.
   - Existing Boolean, provider, run-store, validation, runner and hardening tests retained.

## Verification evidence

- Backend automated suite: **62 tests passed**.
- `python -m compileall -q backend`: passed.
- Temporal example property JSON validates against the canonical Pydantic schema.
- Generated checker source inspected for both next-cycle increment and hold properties.
- **Not yet verified:** actual Yosys/SBY/Z3 execution of the generated temporal checker. The packaging environment does not contain Yosys/SBY/solver binaries. This must be tested in the user's Ubuntu WSL environment before treating Build 11 as formally validated.
- Frontend code was not changed in this increment; frontend production build is therefore not a new Build 11 validation item.

## Important semantics and limitations

- `|->` checks the consequent on the same sampled clock edge as the antecedent.
- `|=>` checks the consequent on the next sampled clock edge after the antecedent.
- `$past` history is guarded so the property is not evaluated until the required sampled history exists.
- `disable iff` is implemented as a synchronous sampled guard, not as the full asynchronous abort semantics of IEEE SVA.
- The current compiler is a restricted translator, not a complete SVA parser. It should not be described as full SVA support.
- Multi-clock domains and asynchronous reset assertions remain unsupported.
- Vacuity remains `NOT_CHECKED`; cover mode remains disabled.
- Formal PASS applies only to the generated assertion, exact RTL, assumptions and proof configuration, not to overall design correctness.

## Next user-side validation

1. Install Build 11 without overwriting `.env`, `.venv`, or `frontend/node_modules`.
2. Run the backend test suite; expect 62 tests to pass.
3. Analyze `rtl/examples/counter_sync/counter_sync.sv` using the app.
4. Submit the two temporal properties from the JSON fixture to `/api/formal/verify` (or the workbench if SVA property editing/generation is available).
5. Confirm both properties return genuine SBY/Z3 PASS results with inductive proof scope.
6. Mutate the RTL increment to decrement and confirm the increment property FAILs with a counterexample. Restore the RTL afterward.

Do not mark Build 11 formally complete until the real WSL formal run and mutation test succeed.

## Build 11.0.1 — Clock/reset candidate display correction

### Issue reported during local integration
The frontend DesignIR summary displayed `Clock: None` and `Reset: None` for the `counter_sync` benchmark, even though the elaborated module contained a sequential register and the temporal generation flow had access to clock/reset context.

### Root cause
The IR builder represented clock/reset candidates using bit-level evidence (`bits`, `source_cells`, `source_kind`, and reset `kind`) but did not attach the corresponding top-level input port name. The frontend summary reads the candidate `name` field, so it displayed `None`. This was a presentation/data-enrichment mismatch, not proof that the RTL lacked a clock or reset.

### Correction
- IR builder now maps each clock/reset candidate bit-vector to an exactly matching top-level input port.
- Candidate records retain their original bit-level evidence and additionally expose `name` and `signal` when a unique matching port is found.
- Added a regression fixture for a Yosys `$sdffe` cell with `CLK` and synchronous `SRST` pins. It checks that `clk` and `rst_n` resolve correctly and that reset kind remains synchronous.
- No temporal proof semantics or checker lowering were changed in this correction.

### Validation
- Backend suite: 63/63 tests passed in the packaging environment.
- The regression test uses a representative Yosys `$sdffe` JSON structure. A fresh local Yosys elaboration and real SBY/Z3 temporal run on the user's WSL installation are still required; packaging tests do not substitute for that integration check.

### Installation
This is a complete replacement project ZIP. Preserve the user's `.env`, `.venv`, and `frontend/node_modules` when replacing the project, as they are excluded from the ZIP.
