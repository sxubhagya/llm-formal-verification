# Build 11.1 — Temporal Validation Harness

## Purpose

Build 11.1 adds a backend-only, manually authored validation suite for the restricted temporal SVA subset introduced in Build 11. It does not change the React frontend, the Gemini generation workflow, the property schema, or the formal proof engine.

The purpose is to test the temporal checker independently of the LLM. The suite deliberately uses properties authored from the intended behaviour of the synchronous counter, rather than properties regenerated from RTL.

## Supported constructs exercised

1. `$past(expr, 2)` — two-cycle sampled history.
2. `$stable(expr)` — current value equals the previous sampled value.
3. `$rose(enable)` — current enable is high and its previous sample was low.
4. `$fell(enable)` — current enable is low and its previous sample was high.
5. `|->` — consequent checked in the same sampled cycle as the antecedent.
6. `|=>` — consequent checked one sampled cycle after the antecedent.
7. `disable iff (!rst_n)` — synchronous sampled reset masking, with `ResetContext.asynchronous=false`.

The tests are intentionally scoped to a single positive-edge clock and synchronous active-low reset. They do not establish full IEEE 1800 SVA compliance.

## Run the real-tool suite

Prerequisites:
- Project virtual environment installed.
- Backend dependencies installed.
- Ubuntu WSL has Yosys, SymbiYosys (`sby`) and Z3 available.
- The canonical `rtl/examples/counter_sync/counter_sync.sv` is restored to its correct implementation.

From the project root in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python backend\scripts\run_temporal_validation.py
```

The script:
- Runs Yosys to analyse the benchmark RTL and construct DesignIR.
- Builds eight manually authored temporal properties.
- Sends each property through the same checker synthesis and SBY/Z3 verification service used by the application.
- Expects every property to prove.
- Saves each run in `formal/runs/`, using the existing experiment-history mechanism.
- Exits with code 0 only if all eight expected proofs pass.

The suite does not call Gemini and does not modify the frontend.

## Test-case intent

| Case | Construct | Expected result |
|---|---|---|
| `past_depth_2` | `$past(..., 2)` | PASS |
| `stable_next_cycle` | `$stable` and `|=>` | PASS |
| `rose_enable` | `$rose` | PASS |
| `fell_enable` | `$fell` | PASS |
| `overlapped_implication` | `|->` | PASS |
| `non_overlapped_implication` | `|=>` | PASS |
| `reset_enable_priority` | reset priority with reset and enable asserted together | PASS |
| `disable_iff_mask` | `disable iff` | PASS |

The expressions include reset/history guards so the properties describe the counter's actual synchronous semantics and avoid relying on uninitialised prior samples.

## Unit tests

A separate unit-test module verifies that the checker lowers each construct into the expected monitor expression and rejects `disable iff` when reset timing is unspecified.

Run the full backend suite:

```powershell
python -m unittest discover -s backend\tests -v
```

## Validation evidence and limitations

In the packaging environment:
- Python compilation passed.
- Full backend unit suite: **71/71 passed**.
- The real Yosys/SBY/Z3 integration script was not executed in the packaging environment. It must be run on the user's WSL installation.

A successful run of the script will establish that these seven curated properties are accepted and proven on this counter benchmark. It will not establish complete SVA support, vacuity checking, asynchronous reset semantics, multi-clock support, or correctness of arbitrary LLM-generated temporal properties.
