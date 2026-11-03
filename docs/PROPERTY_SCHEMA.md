# Candidate Property Schema — Update 6

## Purpose

This schema is the contract between future LLM property generation, property validation and formal execution. It is independent of any particular LLM provider.

## Main objects

- `CandidateProperty`: one candidate assertion with identity, target module, name, description, category, expression language and expression.
- `SignalReference`: each referenced signal, its role and optional expected bit width.
- `ClockContext` / `ResetContext`: explicit clock edge and reset polarity/context.
- `PropertyAssumption`: a separate, reviewable assumption with rationale, source and review state.
- `PropertyProvenance`: generator/model/prompt metadata for reproducibility.
- `PropertyLifecycle`: generated → schema_valid → design_valid → ready_for_formal, or rejected.
- `VerificationStatus`: not_run, pass, fail, unknown, timeout or invalid.

## Assumption policy

LLM-proposed assumptions start as `proposed`. An assumption cannot be marked `accepted` or `rejected` without a `reviewed_by` value. This records that a human review is required; it does not prove the assumption is appropriate. The future pipeline must still check for contradictions, overconstraint and vacuity.

## API

`POST /api/properties/validate`

Request:
- `design`: a serialized `DesignIR` object
- `batch`: a `PropertyBatch` object

The service checks:
- Batch and property top-module consistency
- Existence of the target module
- Existence of each referenced top-level port
- Optional expected port widths
- Top-level input role and width for clock/reset signals
- Unsupported internal-net references, signed ports and `inout` ports are rejected

It can issue warnings when a declared clock is not structurally recognised or reset role needs review.

## What this validation does not do

- It does not parse or elaborate SVA/PSL.
- It does not interpret arbitrary expression strings.
- It does not prove the assertion.
- It does not establish that assumptions are true or safe.
- It does not guarantee non-vacuity.
- It never changes RTL or weakens a property.

A `design_valid` result only means the structural references passed these checks. The verification status remains `not_run`.

## Build 14 checker binding boundary

The formal wrapper currently wires only top-level input/output ports. Internal DUT nets are not safely addressable through the current wrapper. They are intentionally rejected by both validation and checker synthesis. This avoids a critical failure mode where a same-named but undriven wrapper-local wire is asserted instead of the real DUT state. Do not remove this restriction until a Yosys-backed instrumentation mechanism exposes internal signals with verified identity, width, signedness and hierarchy.

Signed ports are also rejected until signed arithmetic and comparison semantics are preserved through the checker. `inout` ports are unsupported.

## Fixtures

`formal/examples/property_schema/` contains manual illustrative batches for the counter, ALU and traffic-light examples. They are test data, not automatically verified properties.
