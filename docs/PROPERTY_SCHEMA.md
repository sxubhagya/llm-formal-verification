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
- Existence of each referenced signal in that module
- Optional expected signal widths
- Existence of declared clock and reset signals

It can issue warnings when a declared clock is not structurally recognised or reset role needs review.

## What this validation does not do

- It does not parse or elaborate SVA/PSL.
- It does not interpret arbitrary expression strings.
- It does not prove the assertion.
- It does not establish that assumptions are true or safe.
- It does not guarantee non-vacuity.
- It never changes RTL or weakens a property.

A `design_valid` result only means the structural references passed these checks. The verification status remains `not_run`.

## Fixtures

`formal/examples/property_schema/` contains manual illustrative batches for the counter, ALU and traffic-light examples. They are test data, not automatically verified properties.
