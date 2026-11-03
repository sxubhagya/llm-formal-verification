# Build 9 Stabilisation Audit — 31 October 2026

## Scope and evidence

This hardening pass was performed against the user-supplied `llm-formal-verification-main.zip` snapshot. The public GitHub URL was supplied, but the GitHub page/raw-file fetch returned a cache miss and `git clone` could not resolve `github.com` from this execution environment. Therefore the remote branch/commit was not independently fetched; this package is based on the supplied ZIP, not a verified latest remote commit.

Backend checks:
- `python -m compileall -q backend`: passed.
- `python -m unittest discover -s backend/tests -v`: 46 tests passed.
- FastAPI `/api/health`: HTTP 200.
- FastAPI `/health`: HTTP 200.
- FastAPI `/openapi.json`: HTTP 200.
- Mock SBY execution: UNKNOWN, marked simulated; never PASS.
- Missing SBY/Yosys/solver: INVALID; never PASS.
- Unsafe source path, path traversal, expression injection, and unsupported temporal SVA: rejected.

Frontend check:
- `npm ci --offline` could not complete because package `yallist@3.1.1` was not present in the local npm cache and registry access was unavailable. The frontend production build was therefore not independently verified in this pass.

Real formal check:
- No live Yosys/SBY/solver run was executed in this packaging environment. Real WSL/SBY/Z3 proof behaviour remains to be tested on the user's Windows/Ubuntu WSL machine.

## Fixes implemented

1. Mock formal execution cannot return PASS.
2. Missing formal tools cannot return PASS.
3. Provider-specific API credentials are selected by provider.
4. Gemini API key is sent through `x-goog-api-key` request header rather than URL query parameters.
5. Gemini system instruction uses the provider's dedicated system-instruction field.
6. Empty or non-normal provider completions are rejected.
7. `httpx` is explicitly declared in backend requirements.
8. Only accepted assumptions with reviewer identity are inserted into checker code.
9. Each property is synthesised and executed independently.
10. Invalid properties are excluded from formal execution.
11. Temporal SVA, implication operators, temporal system functions, comments, directives, statement injection, and unsupported syntax are rejected rather than translated with incorrect semantics.
12. Property expression identifiers must exist in the design and be declared in that property's signal list.
13. Formal task/module identifiers and relative source filenames are validated; absolute/traversal/unsafe filenames are rejected.
14. Formal source bundle, property count, and source-file count are bounded.
15. WSL execution uses argument-list invocation and a WSL working-directory option rather than interpolated `bash -c` text.
16. SBY result parser requires explicit terminal markers; a non-zero process exit cannot be interpreted as PASS.
17. Vacuity is always `NOT_CHECKED`; no assertion PASS is treated as a cover witness.
18. Cover-only mode is rejected until separate cover synthesis and witness parsing exist.
19. Proof results include `proof_scope`, distinguishing bounded BMC from inductive proof.
20. Property IDs are unique within a batch.
21. Frontend API-key entry and transmission were removed.
22. Frontend no longer fabricates a fallback DesignIR when analysis fails.
23. Frontend uses the freshly returned analysis IR for generation, rather than stale React state.
24. Frontend displays actual structural validation counts and reviewer identity requirements.
25. Health route supports both `/health` and `/api/health`.
26. CORS is restricted to local Vite origins and credentialed wildcard CORS is disabled.
27. Prompt version 1.1 treats source/context as untrusted data and requests only the currently supported Boolean-expression subset.

## Deliberately restricted functionality

The current checker supports only same-sample Boolean expressions in the `boolean_expression` language. It does not compile temporal SVA, `|->`, `|=>`, `disable iff`, `$past`, `$stable`, `$rose`, `$fell`, or asynchronous reset-edge monitors. These are rejected or explicitly unsupported. This is a conservative safety boundary, not a claim that temporal properties are implemented.

## Remaining work before calling Build 9 fully validated

- Run real WSL `sby`, Yosys, and selected solver checks on the user's machine.
- Verify one known-valid property returns a real PASS and one deliberately false property returns a real FAIL with VCD.
- Verify the Windows-to-WSL working-directory invocation on the user's actual WSL installation.
- Run `npm.cmd ci` and `npm.cmd run build` on the user's Windows machine.
- Implement a proper expression AST/compiler before re-enabling temporal SVA.
- Implement independent cover tasks and witness parsing before enabling vacuity status.
- Bind RTL source content to DesignIR using a source manifest/hash.
- Add formal-job concurrency, CPU/memory limits, and artifact retention/cleanup.
- Add dependency-scoped bit-level COI extraction.
- Add VCD parsing and counterexample reconstruction in Build 10.

## Release classification

This is a **hardened Build 9 candidate**, not yet a fully cross-platform real-solver-verified release. The backend logic and regression suite are verified in this environment; frontend production build and live formal toolchain are not.
