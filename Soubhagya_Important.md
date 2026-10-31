# Soubhagya_Important

## Build 7 --- LLM Integration: Implementation Brief and Instructions

**Document purpose:** This is the controlling handover and
implementation brief for Build 7 of the LLM-Assisted Formal Verification
of Verilog RTL project. It is intended for the project partner and for
Claude (or another coding agent) to use alongside the earlier project
specification, build updates, and the current repository.

**Primary instruction to the implementation agent:** Follow this
document and the existing project architecture closely. Do not silently
change the scope, architecture, interfaces, terminology, assumptions, or
roadmap. If a change or deviation is technically necessary or materially
beneficial, explicitly identify it, explain why it is needed, describe
its consequences, and record it in the build documentation. Ask for
clarification or approval when a decision would materially change the
agreed design. Do not claim that a feature is implemented or verified
unless it has actually been implemented and tested.

------------------------------------------------------------------------

# 1. Project overview

## 1.1 Project idea

We are developing a framework that uses Large Language Models (LLMs) to
automatically generate candidate formal properties from Verilog RTL
designs.

These candidate properties are then checked using traditional formal
verification tools to determine whether they hold for the design.

**Core principle: AI generates candidate properties; classical formal
verification tools determine whether those properties hold.**

The LLM must not be treated as the authority on correctness. The formal
verification engine is the authority for proof outcomes, subject to the
quality of the design, specification, assumptions, and verification
setup.

## 1.2 Overall objective

Develop a framework that can:

-   Accept Verilog RTL designs as input.
-   Analyse the design and understand its structure.
-   Generate relevant formal properties using an LLM.
-   Validate the generated properties.
-   Formally verify them and report the results.

The framework should ultimately work across different types of digital
designs, including counters, ALUs, finite-state machines (FSMs),
register files, arbiters, pipeline control, and RISC processor
components.

The counter is an initial demonstration and test case, not the focus or
limit of the research. The system must be designed for generalisation
across designs and verification tasks.

## 1.3 Important boundaries

-   A property passing schema or design-structure validation has **not**
    thereby been formally proven.
-   A formally proven property does not, by itself, prove that the
    entire RTL design is correct.
-   A property can be trivial, irrelevant, or based on an incorrect
    specification or assumption and still pass formal verification.
-   Assumptions must be visible, justified, traceable, and reviewed. Do
    not blindly accept assumptions proposed by an LLM.
-   A timeout or inconclusive result must never be reported as PASS.
-   Do not automatically edit RTL to make a property pass.
-   Do not weaken or rewrite assertions merely to obtain a passing
    result.
-   Fine-tuning an LLM is not a core requirement. The planned approach
    is to use hosted LLM APIs, with optional prompt/context experiments
    or model comparisons later.
-   One LLM request may generate a batch of properties for one
    design/task. Formal verification itself does not require LLM
    requests. Optional LLM calls for explanations or bounded refinement
    may be considered later, but are not required for the initial
    integration.

------------------------------------------------------------------------

# 2. Current project state

Build 6 is the latest completed and locally verified milestone.

## 2.1 Existing infrastructure

The project currently has:

-   A Python backend built with FastAPI.
-   A React frontend.
-   Yosys-based RTL parsing and elaboration.
-   A design-specific intermediate representation (IR).
-   A property schema and structural property-validation service.
-   A local formal-tool environment in Ubuntu on WSL2, including Yosys,
    Icarus Verilog, Verilator, Z3, Boolector, and SymbiYosys (SBY).

The Windows application communicates with the formal/HDL tools through
WSL where required.

## 2.2 Completed work

The following has been implemented and tested in previous builds:

1.  Project repository and environment foundation.
2.  Backend health endpoint and frontend development/build setup.
3.  Yosys-based RTL ingestion and analysis.
4.  Design IR, including module, port, net, cell, register,
    memory-access, clock/reset candidate, and FSM-candidate information.
5.  Structural property models and lifecycle/status representations.
6.  Property-batch validation against the analysed design.
7.  API endpoint for property validation.
8.  Example RTL designs and property fixtures.

Build 6 introduced IR v1.2 and the property schema/validation layer.

## 2.3 Latest verification evidence

The user confirmed that all **17 automated tests passed** after applying
Build 6.

The user also successfully tested:

-   `POST /api/designs/analyze` on the counter RTL design.
-   `POST /api/properties/validate` using the analysed design IR and the
    counter property-batch fixture.

The counter analysis identified, among other things:

-   `clk` as a positive-edge clock candidate.
-   `rst_n` as an asynchronous active-low reset candidate.
-   `enable` as an input.
-   `count` as an 8-bit output/register.
-   `$add` and `$adffe` cells.

The property-validation response showed the counter property batch was
schema-valid and design-valid. Its verification status remained
`not_run`, as expected.

**Interpretation:** The RTL analysis and structural property-validation
pipeline is working. No LLM generation or application-integrated formal
proof has yet been completed. Do not describe those later capabilities
as already implemented.

------------------------------------------------------------------------

# 3. Build 7 objective and scope

Build 7 introduces the first AI component.

**Objective:** Connect a hosted LLM to the backend so that it can
receive structured design context derived from the existing design IR
and generate batches of candidate properties conforming to the existing
property schema. The generated properties must then be parsed and
validated by the existing validation system.

Build 7 should end with a working, testable pipeline through property
validation.

**Formal verification integration belongs to Build 8.** Do not pull the
formal execution engine into Build 7 unless an explicitly approved
change is documented.

## 3.1 Build 7 pipeline

1.  User uploads a Verilog RTL design.
2.  Existing Yosys analysis parses/elaborates the RTL.
3.  Existing design IR is produced.
4.  A context builder prepares useful structured context from the IR,
    with relevant source snippets where appropriate.
5.  A prompt builder creates the property-generation request.
6.  A configurable LLM provider sends the request to the hosted model.
7.  The model returns a structured batch of candidate properties.
8.  The backend parses the response into the existing property models.
9.  The existing validation service checks the generated batch against
    the design.
10. The API returns the generated properties, validation outcomes,
    assumptions, provenance, and any relevant errors/warnings.

The LLM must not directly determine whether a property is true or false.

------------------------------------------------------------------------

# 4. Build 7 implementation workstreams

Build 7 should be implemented in the following order. Each component
should be tested before moving to the next.

## Workstream 1 --- OpenAI API integration and provider abstraction

### Goal

Establish secure communication between the Python backend and a hosted
LLM provider.

### Tasks

-   Create a provider-independent interface for LLM calls.
-   Implement an OpenAI provider behind that interface.
-   Use the official Python SDK where appropriate.
-   Read credentials from backend environment variables.
-   Keep API keys out of the frontend, source control, logs, generated
    ZIP files, and documentation.
-   Add clear configuration and error handling for missing keys, invalid
    credentials, rate limits, network failures, and provider errors.
-   Make the model identifier configurable rather than hardcoding it
    throughout the application.
-   Keep the design extensible so another provider can be added without
    rewriting the property-generation pipeline.

### Cost and account context

The project partner has access to premium LLMs, which may make
development and experimentation less constrained by API credits or token
budgets. The implementation must nevertheless retain a backend provider
abstraction and configurable model/provider settings.

OpenAI API billing is separate from a ChatGPT subscription. Do not
assume a ChatGPT plan includes API credits. The project should not
hardcode a particular credit amount or assume that OpenAI must be the
only provider. Select the actual provider/model based on the partner's
available access and the project's requirements, while preserving the
provider-independent architecture.

### Acceptance criteria

-   Backend can make a minimal successful request using the configured
    provider.
-   Credentials are read from environment variables.
-   Missing or invalid credentials produce a clear, safe error.
-   No secret is exposed to the frontend or committed to the repository.
-   Provider/model configuration is documented.

## Workstream 2 --- Design context preparation

### Goal

Give the LLM accurate, relevant, structured context about the design.

### Required approach

Do **not** rely on asking the LLM to infer everything from raw Verilog
alone. The existing Yosys frontend and design IR are central to the
architecture.

The context builder should use relevant IR information, such as:

-   Top module and module hierarchy.
-   Input and output ports.
-   Signal names and widths.
-   Registers and their data/control connections.
-   Clock candidates and clock polarity.
-   Reset candidates, reset type, polarity, and values where available.
-   Memory accesses and their address/data/enable/clock information.
-   FSM candidates and available state-related metadata.
-   Cell categories and relevant connectivity.
-   Existing warnings and limitations.

Where useful, include selected source snippets or source-level
information to clarify behavioural intent that may not survive
elaboration into the IR. The context must not imply that structural
clues establish behavioural intent.

The context builder should avoid sending irrelevant or unnecessarily
large data. It should be deterministic, traceable, and testable.

### Acceptance criteria

-   An analysed design IR can be converted into a well-defined LLM
    context.
-   The context includes relevant design signals and sequential
    information.
-   Warnings/limitations are retained rather than hidden.
-   The context does not invent clock, reset, protocol, or functional
    semantics.
-   Tests cover at least the counter and one combinational design.

## Workstream 3 --- Property-generation prompt

### Goal

Create a controlled prompt that asks the model to generate useful
candidate properties.

### Prompt should communicate

1.  The model's task and the limits of its authority.
2.  The design's top module and relevant design context.
3.  Available signals, widths, registers, clocks, resets, and
    connectivity.
4.  Relevant source snippets, if included.
5.  Which property categories to consider.
6.  The required assertion language and output schema.
7.  That unsupported assumptions must not be silently introduced.
8.  That every assumption must be explicitly listed and justified.
9.  That properties should be meaningful and non-duplicative.
10. That the model must not claim a property has been formally proven.

### Initial property categories

Use the categories already represented by the existing schema where
appropriate:

-   Safety.
-   Liveness.
-   Invariant.
-   Temporal.
-   Combinational.

The prompt should request a useful, bounded batch of properties rather
than an arbitrary large number. The batch size should be configurable.

### Counter example

For the existing counter design, candidate property themes may include:

  -----------------------------------------------------------------------
  Theme                               Intended behaviour
  ----------------------------------- -----------------------------------
  Reset                               Counter is reset to zero when
                                      asynchronous active-low reset is
                                      asserted.

  Enable                              Counter holds its value when enable
                                      is low.

  Increment                           Counter increments by one on an
                                      active clock edge when enabled and
                                      not reset.

  Width                               Counter is represented by an 8-bit
                                      value.

  Overflow                            Counter wraps according to 8-bit
                                      arithmetic when it reaches its
                                      maximum value.
  -----------------------------------------------------------------------

These are **illustrative behavioural intentions**, not assertions
already verified by the system. The exact SVA must respect the actual
clocking, reset, sampling, and disable semantics. In particular, do not
use an incorrect assertion template merely because it looks plausible.

### Acceptance criteria

-   Prompt construction is separate from provider communication.
-   Prompt includes design context and explicit output requirements.
-   Prompt instructs the model not to invent design facts.
-   Prompt requests explicit assumptions and justifications.
-   Prompt version or equivalent provenance is recorded.

## Workstream 4 --- Structured property output

### Goal

Ensure model responses are machine-readable and compatible with the
existing Build 6 property schema.

The backend must not depend on free-form paragraphs or fragile
regular-expression extraction as the primary response format. Use
structured output/functionality supported by the chosen model/provider
where available, followed by strict local parsing and validation.

### Existing property model

Build 6 already defines models including:

-   `CandidateProperty`
-   `PropertyBatch`
-   `PropertyCategory`
-   `AssertionLanguage`
-   `PropertyLifecycle`
-   `AssumptionReviewStatus`
-   `VerificationStatus`
-   `SignalReference`
-   `ClockContext`
-   `ResetContext`
-   `PropertyAssumption`
-   `PropertyProvenance`
-   Validation issue/result models

Use and extend these models only when necessary. Do not create a
parallel incompatible schema without a documented reason and approval.

### Illustrative property

The following is a simplified example of the kind of object we expect.
It is not a final assertion template and must be reconciled with the
exact schema fields and correct SVA semantics in the repository:

``` json
{
  "property_id": "counter_holds_when_disabled",
  "description": "Counter retains its value when enable is low.",
  "category": "invariant",
  "assertion_language": "SVA",
  "expression": "disable |-> $stable(count)",
  "signals": [
    {
      "name": "enable",
      "width": 1
    },
    {
      "name": "count",
      "width": 8
    }
  ],
  "assumptions": [],
  "provenance": {
    "generation_method": "llm"
  }
}
```

The implementation agent must inspect the actual Pydantic models and
required fields before finalising the response contract. Do not assume
this illustrative JSON exactly matches the repository schema.

### Acceptance criteria

-   Provider response is parsed into the existing property models.
-   Malformed JSON or schema-incompatible output is rejected safely.
-   No invalid property is silently accepted.
-   The raw response is retained where practical for debugging/audit,
    subject to safe handling and privacy considerations.
-   The generated batch has stable property identifiers.

## Workstream 5 --- Property validation

### Goal

Reuse the Build 6 validation service to check generated properties
against the analysed design.

At minimum, validate:

-   Batch and top-module consistency.
-   Property schema validity.
-   Referenced module and signal existence.
-   Signal widths where provided.
-   Clock/reset references.
-   Any other structural constraints already implemented in Build 6.

As the system evolves, consider additional checks for assertion-language
syntax, supported constructs, clocking semantics, and suspicious
expressions. Do not claim those checks exist unless implemented and
tested.

A property that fails validation must not be treated as ready for formal
execution.

### Crucial distinction

Structural validation checks whether a property is compatible with the
available design representation. It does **not** establish that the
assertion expresses the intended behaviour, is non-vacuous, or is true.

### Acceptance criteria

-   Generated properties are passed through the existing validation
    service.
-   Valid and invalid properties receive explicit, traceable outcomes.
-   Validation warnings are preserved.
-   Verification status remains `not_run` in Build 7.

## Workstream 6 --- Assumptions, provenance, and auditability

### Goal

Prevent the LLM from silently introducing unsupported environmental or
design assumptions.

### Requirements

-   Newly generated assumptions start as `proposed`.
-   Human review is required before an assumption is treated as
    accepted.
-   Acceptance/rejection must retain reviewer identity as required by
    the existing model.
-   Record the reason/justification for each assumption.
-   Record the model/provider identifier, prompt version, generation
    timestamp where available, and generation method.
-   Preserve the original generated property and any bounded repair
    history.
-   Distinguish model output from backend validation results and human
    review decisions.
-   Never let the LLM mark a property as formally proven.

### Acceptance criteria

-   Assumptions are visibly proposed, not silently accepted.
-   Provenance can be traced from a property to its generation request.
-   Human review status is preserved.
-   The system does not conflate generation, validation, and proof.

## Workstream 7 --- API endpoint and integration tests

### Goal

Expose property generation through the backend.

A proposed endpoint is:

`POST /api/properties/generate`

The exact request/response design should fit the existing FastAPI
conventions and models. Inspect the current code before implementation;
do not assume the endpoint or payload contract is already present.

### Expected flow

1.  Receive the analysed design IR and any generation configuration/task
    context.
2.  Validate the incoming design representation.
3.  Build the LLM context.
4.  Construct the prompt.
5.  Call the configured provider.
6.  Parse the structured response.
7.  Convert it into the existing property models.
8.  Run structural property validation.
9.  Return the generated batch, validation outcomes, assumptions,
    provenance, warnings, and safe error information.

### Error handling

Handle, at minimum:

-   Missing API key/configuration.
-   Provider authentication failure.
-   Rate limits.
-   Network/timeouts.
-   Provider service errors.
-   Invalid or incomplete structured output.
-   Schema-validation failures.
-   Design-validation failures.
-   Unexpected backend exceptions.

Do not expose secrets, full sensitive headers, or raw credential
material in errors or logs.

### Testing

Test at least:

-   Counter generation.
-   ALU generation.
-   Traffic-light FSM generation.
-   Register-file generation.

Use deterministic mocked provider responses for automated
unit/integration tests so tests do not require paid API calls. Add a
separately marked manual/live API smoke test that is only run when
credentials and network access are configured.

Test malformed output, missing fields, unknown signals, invalid widths,
provider failures, and empty responses.

### Acceptance criteria

-   The generation endpoint works end-to-end with a configured provider.
-   The generated batch is structurally validated.
-   Mock-based tests pass without API credits.
-   Live API testing is documented separately.
-   API errors are clear and safe.

------------------------------------------------------------------------

# 5. Recommended architecture

Keep the LLM implementation modular and separate from HDL analysis and
property validation.

Suggested structure (adapt to the existing repository rather than
duplicating or moving working code unnecessarily):

``` text
backend/
└── app/
    ├── api/
    │   ├── designs.py
    │   └── properties.py
    │
    ├── models/
    │   ├── design_ir.py
    │   └── property_models.py
    │
    └── services/
        ├── hdl/
        │   ├── parser.py
        │   └── design_analyzer.py
        │
        ├── llm/
        │   ├── provider.py
        │   ├── openai_provider.py
        │   ├── context_builder.py
        │   ├── prompt_builder.py
        │   └── property_generator.py
        │
        └── property_validation.py
```

Responsibilities:

  -----------------------------------------------------------------------
  Module                              Responsibility
  ----------------------------------- -----------------------------------
  `provider.py`                       Common interface for LLM providers

  `openai_provider.py`                OpenAI API communication

  `context_builder.py`                Converts design IR into useful LLM
                                      context

  `prompt_builder.py`                 Creates the property-generation
                                      prompt

  `property_generator.py`             Coordinates provider call, response
                                      parsing, and validation
  -----------------------------------------------------------------------

This is a proposed logical structure. If the repository's existing
conventions suggest a better location or naming scheme, preserve the
same separation of responsibilities and document any deviation.

------------------------------------------------------------------------

# 6. Model and provider recommendations

Start with one cost-efficient model that supports reliable structured
output. The first objective is to establish a reliable end-to-end
generation pipeline, not to maximise model performance or conduct a
broad model comparison.

Keep provider and model identifiers configurable.

Later, optional comparisons can evaluate:

-   Valid property generation rate.
-   Useful property rate.
-   Design-behaviour coverage.
-   Formal verification outcomes.
-   Cost per design/property batch.
-   Latency.
-   Reliability and response-format compliance.

The partner's premium LLM access may reduce practical constraints during
implementation. However, the application architecture must not become
dependent on a single person's interactive subscription or on a coding
assistant's access. Runtime inference must use an explicitly configured
provider/API integration with credentials available to the backend. Do
not assume a Claude coding subscription automatically provides a Claude
API key or API credits; confirm the actual provider access and billing
arrangement before implementing that provider.

The initial recommendation was OpenAI because it is a straightforward
hosted API option, but the provider abstraction is more important than
the specific provider. If the partner chooses a different provider,
document the choice and keep the rest of the architecture
provider-independent.

------------------------------------------------------------------------

# 7. Build 7 acceptance checklist

Build 7 is complete only when the following have been implemented and
verified:

-   [ ] A provider-independent LLM interface exists.
-   [ ] A configured provider can be called from the backend.
-   [ ] API keys are stored securely in environment variables.
-   [ ] Missing/invalid credentials and provider errors are handled
    safely.
-   [ ] Design IR is converted into structured LLM context.
-   [ ] The prompt includes relevant design context and explicit
    constraints.
-   [ ] The prompt requests multiple candidate properties in a bounded
    batch.
-   [ ] The LLM returns structured output compatible with the existing
    property schema.
-   [ ] Generated properties are parsed into
    `CandidateProperty`/`PropertyBatch` models.
-   [ ] Generated properties are validated against the analysed design.
-   [ ] Invalid properties are rejected with clear explanations.
-   [ ] Assumptions remain proposed until human review.
-   [ ] Generation provenance and prompt/model information are retained.
-   [ ] Mocked tests cover successful and failed responses.
-   [ ] Counter, ALU, FSM, and register-file cases are exercised.
-   [ ] Documentation distinguishes implemented, tested, and planned
    functionality.
-   [ ] The full automated test suite passes.
-   [ ] The Build 7 ZIP and numbered Markdown update document are
    produced and checked.

This checklist describes acceptance criteria, not completed features.

------------------------------------------------------------------------

# 8. What comes after Build 7

The agreed roadmap is:

  -----------------------------------------------------------------------
  Build                               Main objective
  ----------------------------------- -----------------------------------
  Build 7                             LLM generates candidate properties
                                      and the backend validates them

  Build 8                             Integrate formal verification
                                      execution for generated properties

  Build 9                             Frontend for uploading designs,
                                      generating properties, and viewing
                                      results

  Build 10                            Failure analysis, explanations, and
                                      bounded candidate refinement

  Build 11                            Test across a broader range of RTL
                                      designs

  Build 12                            Research evaluation, documentation,
                                      and packaging
  -----------------------------------------------------------------------

Build 8 is the milestone at which generated properties are connected to
formal tools and can receive formal outcomes such as PASS, FAIL,
UNKNOWN, TIMEOUT, or INVALID.

Do not prematurely implement the entire Build 8 scope as part of Build
7. Small interface decisions that make Build 8 easier are welcome,
provided they do not destabilise or expand Build 7.

------------------------------------------------------------------------

# 9. Key recommendations and non-negotiable design principles

1.  **Keep the first implementation simple.** Start with one provider,
    one design at a time, and a bounded batch of candidate properties
    per request. Add provider/model comparisons later.
2.  **Prioritise property quality over quantity.** Twenty irrelevant or
    incorrect properties are less useful than a smaller set of
    meaningful properties.
3.  **Keep generation, validation, and verification distinct.** They are
    separate stages with separate statuses and evidence.
4.  **Use the design IR.** Do not make raw RTL-only prompting the
    central architecture.
5.  **Retain source-level context when useful.** IR can omit or abstract
    behavioural intent; selected source snippets can help, but must not
    override or contradict the elaborated design.
6.  **Do not invent design semantics.** Structural clock/reset
    candidates and cell connectivity are clues, not proof of intended
    behaviour.
7.  **Treat assumptions cautiously.** LLM assumptions must be explicit,
    justified, traceable, and subject to human review.
8.  **Use structured outputs.** Strictly parse and validate model
    responses.
9.  **Use bounded retries/repairs only.** Any repaired response must be
    parsed and validated again. Preserve the original response and
    repair history. Never repair by silently weakening a property.
10. **Do not claim proof in Build 7.** Formal verification is a later
    stage. The Build 7 verification status should remain `not_run`.
11. **Keep credentials secure.** No API keys in frontend code, Git, ZIP
    files, screenshots, logs, or documentation.
12. **Test without paid calls.** Mock provider responses for routine
    automated tests. Live API tests should be optional and separately
    documented.
13. **Make cost visible.** Where provider usage data is available,
    record token usage, model, and estimated/requested cost without
    exposing secrets.
14. **Preserve compatibility.** Extend existing models and services
    rather than replacing working Build 6 foundations without a
    compelling, documented reason.
15. **Do not overstate generalisation.** Testing four example designs is
    a useful integration check, not proof that the framework generalises
    to all Verilog/SystemVerilog designs or all RISC architectures.

------------------------------------------------------------------------

# 10. Explicit instructions to Claude / implementation agent

The following instructions are mandatory.

## 10.1 Read the existing project materials first

Before changing code:

1.  Inspect the current repository and its actual state.
2.  Read the existing project specification and previous numbered build
    update documents, especially the latest Build 6 update.
3.  Inspect the existing design IR, property models, validation service,
    API routes, tests, README, and project status tracker.
4.  Treat the repository as the source of truth for what is currently
    implemented.
5.  Treat this document as the controlling scope and design brief for
    Build 7.
6.  Do not assume an earlier document's planned feature has been
    implemented.

If a referenced file is unavailable, say so. Do not invent its contents.

## 10.2 Follow the agreed plan

Implement the seven workstreams in the order described above:

1.  Provider abstraction and API connection.
2.  Design context preparation.
3.  Prompt construction.
4.  Structured property output.
5.  Existing property validation integration.
6.  Assumptions and provenance.
7.  API endpoint and tests.

Do not skip directly to a large, untested implementation. Work
incrementally, run tests, inspect failures, and correct them before
proceeding.

## 10.3 Do not silently deviate

If you believe a deviation is necessary:

-   Explicitly state what the original plan requires.
-   State the proposed deviation.
-   Explain the technical reason.
-   Explain the effect on architecture, scope, dependencies, cost,
    security, compatibility, and later builds, as applicable.
-   Record it in the Build 7 update documentation under a clearly
    labelled **Deviations from Soubhagya_Important** section.
-   Ask the user/partner for approval before making a material scope or
    architecture change.

Minor implementation details may be chosen independently if they
preserve the agreed architecture and behaviour. Still document
meaningful differences.

**Do not silently replace the property schema, change the IR contract,
change the provider architecture, alter the roadmap, or pull Build 8
functionality into Build 7.**

## 10.4 Preserve the current project and working environment

-   Preserve the existing `.venv` and `frontend/node_modules` when
    packaging/replacing project files.
-   Do not include `.venv`, `frontend/node_modules`, `dist`, `.env`,
    `.git`, or caches in the project ZIP.
-   Never package actual API keys or secrets.
-   Do not overwrite or delete user data.
-   Maintain the existing Windows + WSL workflow.
-   Use PowerShell commands for Windows instructions and `npm.cmd` where
    needed due to PowerShell execution policy.
-   Do not introduce unnecessary dependencies.
-   Respect the existing no-unnecessary-external-library approach.
-   Keep formal tools local/WSL-based; do not move them to an unapproved
    hosting platform.

## 10.5 Test and report honestly

For every meaningful change:

1.  Add or update tests.
2.  Run the full backend test suite.
3.  Run relevant API tests.
4.  Run frontend build if frontend files change.
5.  Run a live provider smoke test only when credentials/network are
    available and the user has authorised the cost.
6.  Report exact commands and actual outcomes.
7.  Distinguish **Implemented**, **Tested**, **Verified**, **Planned**,
    and **Not implemented**.
8.  Never fabricate test output or claim an unrun test passed.

Use mocked provider responses for normal tests so that automated tests
do not consume API credits.

## 10.6 Documentation and deliverables

At the end of Build 7:

-   Update `README.md`.
-   Update `docs/PROJECT_STATUS.md`.
-   Add/update technical documentation for provider configuration,
    prompt/context construction, schema/output, endpoint, assumptions,
    security, and testing.
-   Produce a numbered `UpdateDoc7.md` in Markdown.
-   Include a section titled **Deviations from Soubhagya_Important**. If
    there are none, explicitly write: "No material deviations."
-   Include known limitations, unresolved issues, and exact manual steps
    required from the user.
-   Produce a complete ZIP named
    `LLM_Formal_Verification_Project_Update7.zip`.
-   Verify ZIP integrity and confirm the expected files are present.
-   Exclude secrets, `.env`, `.venv`, `node_modules`, `dist`, `.git`,
    and caches.
-   Do not overwrite the user's local environment or remove their
    dependencies.

The numbered update document must clearly describe what changed in Build
7, what was tested, what remains incomplete, and how to run the new
functionality.

## 10.7 Communication style

Keep implementation instructions and handoff documentation clear,
formal, and direct. Explain decisions in simple technical language. Do
not overwhelm the user with unnecessary alternatives. When a decision
materially affects the project, present the recommendation and
rationale, then ask for approval rather than silently choosing a
different direction.

------------------------------------------------------------------------

# 11. Immediate next actions

1.  Partner/implementation agent reviews this document and the previous
    project specification/build updates.
2.  Inspect the current Build 6 repository and confirm that the baseline
    matches the documented state.
3.  Confirm which hosted provider and model can actually be accessed
    through an API by the partner. Do not assume an interactive premium
    LLM subscription includes API access.
4.  Agree on the provider/model configuration while retaining the
    provider-independent interface.
5.  Begin Workstream 1 and implement incrementally.
6.  Complete the Build 7 acceptance checklist and deliver the ZIP plus
    `UpdateDoc7.md`.

## Final objective for Build 7

At the end of this phase, we should be able to upload or analyse an RTL
design, send its structured design context to a configured LLM, receive
a batch of candidate formal properties in our existing schema, and
validate those properties against the design---with assumptions and
provenance retained.

**Build 7 does not yet prove the properties. It establishes the
AI-driven property-generation and validation pipeline that Build 8 will
connect to classical formal verification.**
