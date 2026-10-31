# Project Status

## Current checkpoint — Update 6

| Area | Status | Evidence / notes |
|---|---|---|
| Repository skeleton and environments | Verified | User previously verified local startup and tests |
| Windows-to-WSL Yosys path | Verified | Live counter/ALU/FSM/register-file/multi-module analysis |
| Counter and ALU RTL analysis | Verified | API returned ANALYZED |
| FSM/register-file/multi-module analysis | Verified | User supplied successful Build 5 API outputs |
| Design IR v1.1 summaries/connectivity | Verified | Build 5 tests and live uploads |
| Memory access extraction | Implemented; local test included | Clock-enabled memory write ports contribute clock candidates |
| Enum-based FSM candidates | Implemented; local test included | Candidate metadata only; no transition reconstruction |
| Candidate-property schema | Implemented | Pydantic models and validation lifecycle; 17 backend tests pass |
| Design-reference validation API | Implemented | `POST /api/properties/validate`; signal names and widths only |
| Assumption review controls | Implemented | Accepted/rejected assumptions require reviewer identity |
| LLM property generation | Not started | |
| SVA parsing/elaboration | Not started | |
| Formal proof execution through app | Not started | |
| Frontend workflow integration | Not started | |

## Update 6 scope

- Added IR v1.2 memory access records and clocked-memory clock candidates.
- Added conservative enum-derived FSM candidates; this does not reconstruct transitions.
- Added provider-independent candidate-property schema and lifecycle/status enums.
- Added assumption review metadata and reviewer requirement for accepted/rejected assumptions.
- Added `POST /api/properties/validate` for design-top, module, signal-name and width checks. Clock/reset review warnings are non-fatal.
- Added manual property fixtures for counter, ALU and traffic-light examples.
- Corrected README and project status documentation.

## Important validation boundary

`design_valid` means referenced module/signal names and declared widths match the supplied DesignIR. It does not mean the assertion expression is syntactically valid, semantically correct, non-vacuous, or proven. `verification_status` remains `not_run` until a formal backend executes the property.

See `UpdateDoc1` through `UpdateDoc6` for build handoffs.
