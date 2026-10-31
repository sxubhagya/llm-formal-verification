# UpdateDoc6 — Candidate Property Schema and RTL Analysis QoL

## Purpose

Introduce a canonical property representation that will form the contract between future LLM generation, validation and formal execution. Include the previously identified memory-clock and FSM-candidate improvements.

## Changes

### 1. Design IR v1.2
- Added memory access records for Yosys `$memrd*` and `$memwr*` cells.
- Captures operation, address/data/enable/clock connections and whether the memory port is clock-enabled.
- Clock-enabled memory writes contribute to clock candidates.
- Added conservative enum-derived FSM candidates using Yosys enum-like net attributes. This does not reconstruct transitions or reachable states.

### 2. Candidate-property schema
Added `backend/app/models/property_models.py`:
- Property categories: safety, liveness, invariant, temporal and combinational.
- Expression languages: SVA, Boolean expression, PSL and other.
- Signal references with roles and optional expected widths.
- Clock and reset contexts.
- Assumptions with rationale, source and review status.
- Provenance, lifecycle and verification status.
- Property batches and validation result models.

Accepted/rejected assumptions require a reviewer identity. This is a workflow guard, not a claim that the assumption is correct.

### 3. Design-reference validation API
Added `POST /api/properties/validate`.

It validates batch/top-module consistency, module existence, referenced signal names and optional widths. It can warn about clock signals that are not structurally recognised and reset roles requiring review.

This is not assertion-language parsing or formal proof. The result leaves `verification_status` as `not_run`.

### 4. Example fixtures
Added manual property batches for:
- Counter increment behaviour
- ALU addition operation
- Traffic-light one-hot output invariant

These are illustrative schema fixtures. They are not asserted to be syntactically valid SVA or formally proven by the current system.

### 5. Documentation
- Updated README to Update 6 and current implementation boundaries.
- Updated project status.
- Added `docs/PROPERTY_SCHEMA.md`.

## How to apply

1. Stop the backend server with `Ctrl+C`.
2. Extract `LLM_Formal_Verification_Project_Update6.zip` into the existing `Program Folder`.
3. Choose **Replace the files in the destination**.
4. Keep `.venv` and `frontend/node_modules`; the ZIP excludes them.
5. Run the test command provided with this handoff.

## Acceptance checks

- All 17 backend unit tests pass in the build environment. The new route was also smoke-tested through FastAPI TestClient (HTTP 200).
- Existing RTL analysis remains operational.
- New memory/FSM IR tests pass.
- Property model validation tests pass.
- The property validation API appears in Swagger at `/docs`.

## Next step

Build 7: add the provider-independent LLM integration layer and prompt/context construction using the Design IR and candidate-property schema.
