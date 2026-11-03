# Build 10 Status

## Completed
- Corrected ALU preset and failure phase classification.
- Added solver-generated VCD trace extraction and display.
- Added Gemini transient retry policy and API-key-scoped model discovery (Update 10.1).

## Still to verify
- Windows frontend build after the user's local update.
- Live `GET /api/llm/models` using the user's Gemini key.
- Live Gemini property generation after selecting a model actually listed for the key.
- Real ALU counterexample trace viewer usability and formatting improvements.

## Known formal limitations
- Same-sample Boolean property expressions only.
- Temporal SVA and sequential semantics are not yet supported.
- Vacuity remains NOT_CHECKED; cover mode remains disabled.
- No LLM-assisted counterexample diagnosis/refinement loop yet.


## Build 10.2 status (2026-11-01)
- Added formatted counterexample values (binary, hexadecimal, unsigned decimal) and heuristic signal grouping.
- Added local formal-run artifact storage, source SHA-256 fingerprints, run listing/retrieval endpoints, and frontend saved-run history.
- Stored record includes DesignIR, property batch, proof configuration, verification outcomes, counterexample trace, and exact RTL source bundle. API credentials are not stored.
- Automated backend suite: 59 tests passed in the build environment.
- Frontend production build remains to be verified on the user's Windows environment because dependency installation timed out in the packaging environment.
- Signal grouping is a display heuristic, not a semantic HDL port-direction analysis. Values are unsigned representations; signed interpretations are not inferred.


## Build 11.0 alpha
See `UpdateDoc11.md` for the temporal SVA subset and required WSL verification. The packaging environment has not run a real Yosys/SBY/Z3 temporal proof.
