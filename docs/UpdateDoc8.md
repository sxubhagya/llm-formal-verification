# UpdateDoc8 — Formal Checker and SymbiYosys Integration

**Build status:** Formal integration code was inherited from the partner's Build 8 implementation and hardened in the stabilised Build 9 package. Real solver execution still requires local WSL verification.

## Objective
Translate candidate properties into formal checker modules, execute them through SymbiYosys (SBY), and report proof outcomes without confusing simulated, bounded, cover, or unbounded results.

## Inherited implementation
- Procedural checker synthesiser.
- SBY configuration and execution runner.
- BMC/prove/cover mode models and solver selection.
- Formal verification service and `POST /api/formal/verify`.
- Five RISC-oriented RTL benchmark designs.

## Stabilisation changes
1. **No fabricated PASS:** explicit mock execution now returns `UNKNOWN` with a mock marker. Missing SBY/Yosys/selected solver returns `INVALID`; it never returns PASS.
2. **Assumption gate:** only assumptions marked `accepted` and carrying `reviewed_by` are injected. Proposed/rejected assumptions are excluded and produce warnings.
3. **Conservative expression subset:** checker synthesis accepts only `boolean_expression`, checks tokens/identifiers against design signals and the property's declared signal list, and rejects temporal SVA operators, `$past`, `$stable`, comments, directives, statements, and unsafe injected text.
4. **Per-property execution:** each property is synthesised and run in its own SBY task. A batch-level result is no longer copied to every property.
5. **Invalid-property isolation:** structurally invalid or unsupported properties are reported INVALID and are not included in a solver run.
6. **No false vacuity claim:** vacuity remains `not_checked`. Assertion PASS is not treated as proof that an antecedent cover was reached.
7. **Cover mode disabled:** cover-only execution is rejected until separate cover task generation and witness parsing exist. Cover success is not an assertion PASS.
8. **Proof scope:** results expose `proof_scope` (`inductive`, `bounded`, or `cover_reachability`). BMC PASS is explicitly bounded to the requested depth.
9. **Execution input hardening:** task/module identifiers and relative source filenames are validated; absolute paths, traversal, shell/config metacharacters, NULs, and oversized source bundles are rejected.
10. **WSL invocation:** SBY is invoked using an argument list and WSL working-directory option rather than interpolated `bash -c` command text.
11. **Result parsing:** explicit SBY terminal markers are required; non-zero process exit cannot be treated as PASS.
12. **Source/resource limits:** formal request limits are applied to source count, source bundle size, and property count.

## Important supported-language limitation
The checker is intentionally limited to same-sample Boolean expressions. It does **not** currently preserve or compile temporal SVA semantics, implication operators (`|->`, `|=>`), `disable iff`, `$past`, `$stable`, or asynchronous reset-edge assertions. Such expressions are rejected instead of being approximated. This is a deliberate fail-closed restriction, not a completed temporal compiler.

## Testing
The combined backend suite passed 46 tests. New regression tests cover:
- Mock execution cannot PASS.
- Missing tools cannot PASS.
- Path traversal and unsafe source filenames are rejected.
- Expression injection and temporal SVA are rejected.
- Only accepted/reviewer-attributed assumptions are injected.
- Provider credentials are not cross-wired.

No real SBY/Yosys/Z3 run was available in the packaging environment. Live proof behaviour remains unverified until the user runs the WSL regression suite.
