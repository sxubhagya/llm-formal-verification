# Build 12 — Specification-Guided Verification and Workbench Redesign

**Date:** 1 November 2026  
**Project:** LLM-Assisted Formal Verification of Verilog RTL

## 1. Why the methodology is changing

The earlier workflow generated properties from the RTL implementation and then checked those properties against the same RTL. This creates a circularity risk: if the RTL contains an incorrect reset value, an LLM that treats the implementation as the behavioural authority may generate an assertion that expects that incorrect value. The formal engine can then correctly prove the wrong requirement.

Build 12 introduces an independent behavioural specification. The specification expresses what the design is required to do. The RTL expresses what the implementation actually does. The LLM translates the specification into candidate properties, using the RTL and DesignIR only to resolve implementation details such as signal names, widths, module structure, clock candidates and reset candidates.

The formal backend remains the authority on whether the RTL satisfies the generated properties. It cannot independently determine whether the human-authored specification is complete or correct; that remains a review responsibility.

## 2. Revised information flow

1. User selects or supplies RTL source files and a top module.
2. Yosys elaborates the RTL and produces the existing architecture-independent DesignIR.
3. User writes behavioural requirements independently of the RTL, one requirement per line in the initial interface.
4. User identifies themselves as the reviewer and explicitly approves the specification by initiating generation.
5. The backend validates the specification structure, unique requirement IDs and design-top match.
6. Gemini receives the approved specification as the authority for intended behaviour, plus the DesignIR and RTL as implementation context.
7. Gemini returns candidate properties. Every property must cite one or more requirement IDs.
8. The backend rejects properties with missing or unknown requirement IDs, then runs the existing schema and structural DesignIR checks.
9. The user reviews assumptions and properties, then runs the existing Yosys/SBY/solver flow.
10. Experiment records preserve the specification, its SHA-256 hash, the RTL source/hash, property batch, formal configuration and results.

## 3. New and changed backend components

### New
- `backend/app/models/specification_models.py`: `DesignSpecification`, `BehaviouralRequirement` and requirement-source classification.
- `backend/app/api/specifications.py`: `POST /api/specifications/validate` endpoint.
- `backend/tests/test_specification_models.py`: specification validation, approval-gate, stable-hash and RTL-only rejection tests.

### Changed
- `PropertyGenerationRequest` now requires a specification.
- `PropertyGenerationService` refuses RTL-only generation and refuses unapproved or top-module-mismatched specifications.
- The property-generation prompt is version 2.0 and states explicitly that the specification is authoritative and RTL is not a source of expected behaviour.
- `CandidateProperty` includes `requirement_ids`.
- The generator rejects missing or unknown requirement IDs.
- Per-property and batch provenance records include RTL and specification hashes when available.
- Formal experiment records include the approved behavioural specification and its hash alongside RTL hashes and archived RTL source files.

## 4. Gemini request changes and cost implications

The intended request count does not increase by default. One generation request still returns a batch of properties. The request now includes the approved requirements, DesignIR and relevant RTL context. The prompt and response are therefore larger, but formal proof execution still makes no Gemini request.

Optional extra requests remain limited to repair, explanation or future specification-assistance workflows. Build 12 does not automatically call Gemini to invent or approve missing requirements. This is deliberate: inferred requirements must not silently become ground truth.

The mock provider remains a canned testing provider, not a semantic specification interpreter. For meaningful specification-guided experiments, select the configured hosted provider and inspect the generated property-to-requirement mapping.

## 5. Frontend redesign

The workbench is reorganised around a clearer sequence:
1. RTL implementation — choose a benchmark, edit the top module and source, then analyse.
2. Behavioural specification — enter one requirement per line and identify the reviewer.
3. Generate properties — select a provider, optionally provide focus guidance, and request a batch.
4. Formal verification — select proof mode and solver, then run the accepted batch.

The UI now uses a lighter, more restrained layout, clearer labels, consistent cards, responsive columns, and a visible approved-specification summary. Editing RTL or requirements invalidates previously generated state so stale properties are not accidentally reused against changed inputs.

## 6. What this adds to project complexity

The core proof engine is retained. The main new complexity is semantic and methodological:
- Requirements must be explicit and independently authored/reviewed.
- Generated properties must map to requirement IDs.
- A formal PASS is meaningful only relative to the exact specification, RTL, assumptions and proof configuration.
- Ambiguous or conflicting requirements need a future review/consistency layer.
- Property-to-requirement mapping is traceability, not proof that the translation is semantically correct. Human review and controlled reference tests remain necessary.

Build 12 does not yet implement automated natural-language contradiction detection, requirement completeness analysis, a graphical requirement editor, or automatic reference-property comparison. These are future research increments, not claimed features.

## 7. Acceptance criteria and limitations

Implemented in Build 12:
- Independent specification model with stable content hash.
- Unique requirement ID validation.
- Explicit reviewer approval gate.
- Specification required by the property-generation API.
- RTL-only generation rejected.
- Gemini prompt separates intended behaviour from implementation evidence.
- Property-to-requirement IDs required and checked.
- Specification and hash recorded in formal experiment artifacts.
- Frontend workflow and styling redesigned.

Automated validation performed in the packaging environment:
- Backend Python compilation.
- Full backend unit suite.
- Frontend production build was not run because dependency installation (`npm ci`) timed out in the packaging environment. The user must run `npm.cmd run build` locally.
- No live Gemini request or real WSL/Yosys/SBY/Z3 specification-guided mutation experiment was run during packaging. These remain user-side acceptance tests.

## 8. Recommended user-side acceptance test

Use the `counter_sync` benchmark and review its specification before generating properties. Generate the properties once against the correct RTL and preserve that exact batch. Then change only the RTL reset assignment from zero to one and rerun formal verification without regenerating properties. The reset requirement should fail while unrelated hold/increment requirements should remain unaffected. Restore the correct RTL afterwards.

This experiment is the primary acceptance test for the circularity fix. If properties are regenerated after mutating RTL, the test no longer measures independent specification-guided verification.
