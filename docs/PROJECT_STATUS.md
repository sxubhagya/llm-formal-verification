# Project Status

## Current checkpoint — Update 7

| Area | Status | Evidence / notes |
|---|---|---|
| Repository skeleton and environments | Verified | User previously verified local startup; macOS Python 3.10 verified |
| Windows-to-WSL Yosys path | Verified | Live counter/ALU/FSM/register-file/multi-module analysis |
| Counter and ALU RTL analysis | Verified | API returned ANALYZED |
| FSM/register-file/multi-module analysis | Verified | User supplied successful Build 5 API outputs |
| Design IR v1.2 summaries/connectivity | Verified | Memory access records and enum-derived FSM candidate extraction |
| Candidate-property schema | Implemented | Pydantic models, assumptions guard, provenance |
| Design-reference validation API | Implemented | `POST /api/properties/validate`; signal names and widths |
| Provider abstraction layer | Implemented | `LLMProvider` interface; Gemini, OpenAI, and deterministic Mock |
| Design context preparation | Implemented | Extracts ports, registers, clocks, resets, memories, FSMs, source snippets |
| Prompt construction | Implemented | Untrusted generator role, zero proof claims, explicit assumption rationale |
| Structured property output parsing | Implemented | Markdown fence stripping, schema validation, assumption guard |
| LLM candidate generation API | Implemented | `POST /api/properties/generate`; 28 backend tests pass |
| Formal proof execution through app | Not started (Build 8) | Formal runner / SBY integration planned for Build 8 |
| SVA parsing/elaboration | In design | Clocked procedural monitor checker synthesizer planned for Build 8 |
| Frontend workflow integration | Not started (Build 9) | React/Vite workbench placeholder |

## Update 7 scope

- Added provider-independent LLM service (`LLMProvider`, `LLMResponse`, factory).
- Implemented `GeminiProvider` (REST via httpx with token/cost tracking and error mapping), `OpenAIProvider`, and `MockProvider`.
- Implemented `build_design_context()` extracting elaborated ports, DFF registers, clock/reset inference, memory instances, FSM candidates, and source snippets.
- Implemented `build_generation_prompts()` enforcing untrusted role, zero proof claims, and mandatory assumption rationale.
- Implemented `PropertyGenerationService` orchestrating context -> prompt -> provider -> JSON extraction -> Pydantic parsing -> design reference validation.
- Added `POST /api/properties/generate` endpoint returning generated properties and automatic design validation results.
- Added 11 new automated unit tests in `backend/tests/test_llm_pipeline.py` (total 28 automated tests passing).
- Added IEEE Std 1016-2009 / ISO/IEC/IEEE 29148 system design document in `docs/latex/`.

## Important validation boundary

`design_valid` means referenced module/signal names and declared widths match the supplied DesignIR. It does not mean the assertion expression is syntactically valid, semantically correct, non-vacuous, or proven. `verification_status` strictly remains `not_run` until a formal backend executes the property in Build 8.

See `UpdateDoc1` through `UpdateDoc7` for build handoffs.
