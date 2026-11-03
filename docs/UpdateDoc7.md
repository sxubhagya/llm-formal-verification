# UpdateDoc7 — LLM Integration

**Build status:** Implemented in the inherited repository. This document records the implementation as retained in the stabilised Build 9 package.

## Objective
Connect a provider-independent hosted LLM interface to the backend. Use Design IR v1.2 and selected source context to generate structured candidate properties, parse them into the existing property schema, and validate them against the design.

## Implemented
- Provider abstraction with Gemini, OpenAI, and deterministic Mock providers.
- Design context builder and prompt builder.
- Property generation orchestration and `POST /api/properties/generate`.
- JSON extraction and Pydantic schema parsing.
- Structural validation against module/signal names and widths.
- Generation provenance and proposed assumptions.

## Stabilisation changes included in Update 9
- Provider-specific credentials are selected after provider selection. An OpenAI key is no longer passed to Gemini, or vice versa.
- Gemini key is sent in `x-goog-api-key` header rather than URL query parameters.
- Gemini system instructions use the provider's `systemInstruction` request field.
- Provider adapters reject empty or non-normal completion responses.
- `httpx` is declared in `backend/requirements.txt`.
- LLM output with a mismatched design top/module or duplicate/missing property IDs is rejected rather than silently normalised.
- Property batches are limited to 20 properties.
- Prompt version is now 1.1. It treats RTL/source/focus text as untrusted data and requests only the currently supported same-sample Boolean-expression subset.
- The frontend no longer accepts or transmits API keys; credentials are configured in backend `.env`.
- Mock provider examples were updated to the supported Boolean-expression subset and are explicitly trivial illustrations, not meaningful sequential behaviour properties.

## Configuration
Copy `.env.example` to `.env` and set `LLM_PROVIDER`, `LLM_MODEL`, and the matching provider key (`GEMINI_API_KEY` or `OPENAI_API_KEY`). Never commit `.env`.

## Limitations
- Full bit-level dependency-scoped Cone of Influence extraction is not implemented.
- Expression validation is conservative and is enforced at checker synthesis; structural validation alone does not parse or prove expressions.
- The current formal checker does not compile temporal SVA.
- No live Gemini/OpenAI API request was executed in the packaging environment.

## Testing
The combined backend suite passed 46 tests in the packaging environment. Provider tests use deterministic mocks; live API calls are not part of routine tests.
