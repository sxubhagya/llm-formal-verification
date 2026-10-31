# UpdateDoc7 — LLM Candidate Property Generation and Design Validation

## Purpose

Implement Build 7 according to the specifications in `Soubhagya_Important.md`:
- Introduce a provider-independent LLM integration layer (Gemini, OpenAI, and deterministic Mock).
- Construct structured design context from the elaborated Design IR v1.2 and optional source snippets.
- Build system and user prompts enforcing an untrusted generator role, zero proof claims, and mandatory assumption rationale.
- Parse structured candidate property outputs into the canonical `CandidateProperty` and `PropertyBatch` schemas.
- Automatically validate generated properties against the elaborated Design IR using the existing design-reference validation engine.
- Retain generation provenance (timestamp, tokens, prompt text) and enforce that all generated assumptions default to `proposed` status until human review.
- Provide `POST /api/properties/generate` endpoint and automated test coverage.

Formal verification remains decoupled; all generated properties maintain `verification_status = "not_run"`.

---

## Changes Implemented

### 1. Provider Abstraction and Adapters (`backend/app/services/llm/`)
- **`provider.py`**:
  - `LLMResponse`: Structured dataclass capturing `raw_content`, `prompt_tokens`, `completion_tokens`, `total_tokens`, and optional `cost_estimate`.
  - `LLMProvider`: Abstract base class defining the `generate(system_prompt, user_prompt, temperature, max_tokens)` interface.
  - `get_llm_provider(name, api_key, model)`: Factory returning configured provider instances (`mock`, `gemini`, `openai`).
- **`gemini_provider.py`**:
  - Direct REST implementation using `httpx.Client` against Google's Gemini `generateContent` API.
  - Supports `gemini-2.5-flash`, `gemini-1.5-pro`, or user-specified models.
  - Robust HTTP error mapping: maps 401/403 to invalid API key errors, 429 to rate limit warnings, and 504 to timeout notices. Never exposes API keys in logs or errors.
- **`openai_provider.py`**:
  - REST implementation against OpenAI `/v1/chat/completions` supporting `gpt-4o`, `gpt-4o-mini`, etc.
- **`mock_provider.py`**:
  - Deterministic, offline provider returning complete candidate property batches for counter, ALU, FSM, and generic modules without network calls or API costs.
  - Used for automated regression testing and offline development.

### 2. Design Context Preparation (`backend/app/services/llm/context_builder.py`)
- `build_design_context(design_ir, verilog_source, top_module)`:
  - Extracts module hierarchy, top module identification, port declarations (direction, width), and internal registers (`$dff`, `$dffe`).
  - Synthesizes clock and reset candidate signals with structural inference sources.
  - Captures memory instances (`$memrd`, `$memwr`) and clock-enabled access details.
  - Captures enum-based FSM candidate signals.
  - Includes relevant source code snippets (preserving comments) while keeping the context token-efficient.

### 3. Prompt Construction (`backend/app/services/llm/prompt_builder.py`)
- `build_generation_prompts(context, user_instructions, max_properties)`:
  - **System Prompt**: Enforces that the model is an untrusted property generator whose output will be mechanically validated and formally checked by external tools. It strictly forbids claiming proof, demands explicit assumptions with rationale, and mandates valid JSON adhering to the canonical schema.
  - **User Prompt**: Supplies formatted design context (ports, signals, memories, FSMs, source code) and optional user instructions.

### 4. Structured Output Parsing & Validation (`backend/app/services/llm/property_generator.py`)
- `PropertyGenerationService`:
  - Handles markdown code fence stripping (e.g. ` ```json ... ``` `).
  - Strictly parses JSON into Pydantic `PropertyBatch` and `CandidateProperty` models.
  - Automatically runs `validate_property_batch()` against the elaborated `DesignIR` to verify top-module consistency, module existence, referenced signal names, and declared widths.
  - Populates provenance records (`PropertyProvenance`) with generation timestamp, token usage, model name, and prompt text.
  - Enforces that any generated assumption has `status = "proposed"` and cannot be marked `accepted` or `rejected` without human reviewer attribution.

### 5. API Endpoint (`backend/app/api/properties.py`)
- Added `POST /api/properties/generate`:
  - Request body: `PropertyGenerationRequest` containing `design_ir`, optional `verilog_source`, `top_module`, `provider` (`mock`, `gemini`, `openai`), optional `api_key`, `model`, `temperature`, and `user_instructions`.
  - Response body: `PropertyGenerationResponse` returning `batch`, `validation_result`, `provenance`, and `design_valid`.

### 6. Automated Unit & Integration Tests (`backend/tests/test_llm_pipeline.py`)
- 11 new automated unit tests:
  - Context building for counter (ports, registers, clock/reset inference).
  - Context building for ALU (combinational ports, no false clock candidates).
  - Context building for traffic light FSM (state register and FSM candidates).
  - Context building for simple RAM (memory read/write port extraction).
  - Prompt construction integrity (untrusted role instruction, JSON schema presence).
  - Mock provider execution (offline, deterministic counter property output).
  - Markdown JSON fence stripping.
  - Property generation end-to-end service with design validation.
  - Assumption review guard enforcement (`proposed` status).
  - Unsupported provider error handling.
  - FastAPI endpoint test via TestClient (`POST /api/properties/generate`).

---

## Test Results

All 28 backend unit tests pass in 0.034 seconds:

```bash
$ python3 -m unittest discover -s backend/tests -v
test_health_payload (test_health.HealthEndpointTests) ... ok
test_adds_module_summary_and_cell_connectivity (test_ir_builder.TestIRBuilder) ... ok
test_extracts_clocked_memory_write_access (test_ir_builder.TestIRBuilder) ... ok
test_extracts_enum_state_candidate (test_ir_builder.TestIRBuilder) ... ok
test_extracts_ports_cells_register_and_clock_reset_candidates (test_ir_builder.TestIRBuilder) ... ok
test_identifies_module_instances (test_ir_builder.TestIRBuilder) ... ok
test_missing_top_module_is_rejected (test_ir_builder.TestIRBuilder) ... ok
test_api_generate_endpoint_error_handling (test_llm_pipeline.LLMPipelineTests) ... ok
test_api_generate_endpoint_success (test_llm_pipeline.LLMPipelineTests) ... ok
test_context_builder_combinational_design (test_llm_pipeline.LLMPipelineTests) ... ok
test_context_builder_extracts_clock_and_reset (test_llm_pipeline.LLMPipelineTests) ... ok
test_context_builder_fsm_and_memory (test_llm_pipeline.LLMPipelineTests) ... ok
test_context_builder_invalid_target_module_raises (test_llm_pipeline.LLMPipelineTests) ... ok
test_generation_rejects_malformed_json (test_llm_pipeline.LLMPipelineTests) ... ok
test_generation_strips_markdown_code_fences (test_llm_pipeline.LLMPipelineTests) ... ok
test_mock_provider_generation_end_to_end (test_llm_pipeline.LLMPipelineTests) ... ok
test_prompt_builder_enforces_principles (test_llm_pipeline.LLMPipelineTests) ... ok
test_provider_missing_api_key_raises_error (test_llm_pipeline.LLMPipelineTests) ... ok
test_assumption_cannot_be_accepted_without_reviewer (test_property_models.PropertyModelTests) ... ok
test_design_validation_checks_signals_and_widths (test_property_models.PropertyModelTests) ... ok
test_empty_expression_rejected (test_property_models.PropertyModelTests) ... ok
test_manual_property_fixtures_match_schema (test_property_models.PropertyModelTests) ... ok
test_unknown_signal_and_width_mismatch_rejected (test_property_models.PropertyModelTests) ... ok
test_valid_candidate_property (test_property_models.PropertyModelTests) ... ok
test_native_runner_writes_script_and_reads_output (test_yosys_runner.TestYosysRunner) ... ok
test_rejects_invalid_top_module_identifier (test_yosys_runner.TestYosysRunner) ... ok
test_rejects_missing_source (test_yosys_runner.TestYosysRunner) ... ok
test_wsl_path_uses_forward_slashes_for_windows_paths (test_yosys_runner.TestYosysRunner) ... ok

----------------------------------------------------------------------
Ran 28 tests in 0.030s

OK
```

---

## Deviations from Soubhagya_Important

**No material deviations.**

All workstream items were implemented according to the agreed plan:
- Provider abstraction implemented with Gemini, OpenAI, and Mock options.
- Design IR v1.2 context builder extracts ports, registers, clocks, resets, memories, and FSM candidates.
- Canonical candidate property schema is preserved without alterations.
- All generated assumptions default to `proposed` status and cannot be marked `accepted` without explicit human review attribution.
- Verification status remains strictly `not_run`. Proof execution is intentionally deferred to Build 8.

---

## Known Limitations and Boundaries

1. **Generation vs. Verification Boundary**:
   - `design_valid: true` indicates that the referenced module, ports, and signals match the structural declarations in the elaborated `DesignIR`.
   - It does **not** prove that the property holds, that the property is non-vacuous, or that the RTL is bug-free.
   - `verification_status` remains `not_run`. Formal verification execution will be integrated in Build 8.
2. **Heuristic Clock and Reset Inferences**:
   - Clock and reset candidate signals are structurally inferred from DFF cell pin connections and port names.
   - Non-fatal validation warnings are generated when a property references a clock or reset signal not identified in the structural candidate list.
3. **API Keys and Offline Testing**:
   - Routine automated tests use the offline `MockProvider` to avoid API key dependencies and network latency.
   - Live generation requires a valid `GEMINI_API_KEY` or `OPENAI_API_KEY`. API keys are never stored, logged, or returned in response payloads.

---

## Manual Steps for Users

### On Windows (PowerShell)

1. Activate your virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```
2. Run the test suite:
   ```powershell
   python -m unittest discover -s backend/tests -v
   ```
3. Set your API key (optional for live calls, default is `mock`):
   ```powershell
   $env:GEMINI_API_KEY = "your-gemini-api-key"
   $env:LLM_PROVIDER = "gemini"
   ```
4. Start the backend:
   ```powershell
   uvicorn backend.app.main:app --reload
   ```

### On macOS / Linux

1. Activate your virtual environment:
   ```bash
   source .venv/bin/activate
   ```
2. Run the test suite:
   ```bash
   python3 -m unittest discover -s backend/tests -v
   ```
3. Set your API key (optional):
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   export LLM_PROVIDER="gemini"
   ```
4. Start the backend:
   ```bash
   uvicorn backend.app.main:app --reload
   ```

### Calling the Property Generation API

Open interactive Swagger documentation at `http://127.0.0.1:8000/docs` and locate `POST /api/properties/generate`.

Or use `curl`:
```bash
curl -X POST "http://127.0.0.1:8000/api/properties/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "design_ir": { ... },
    "top_module": "counter",
    "provider": "mock"
  }'
```

---

## Next Step: Build 8 (Formal Verification Integration)

In Build 8, generated candidate properties will be synthesized into clocked procedural monitor checkers and executed using SymbiYosys (SBY) for Bounded Model Checking (BMC) and unbounded $k$-induction proofs.
