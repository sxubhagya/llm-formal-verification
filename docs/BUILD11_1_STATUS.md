# Build 11.0.1 Status

This patch corrects clock/reset candidate naming in DesignIR. Candidate bit-vectors are mapped to exact matching top-level input ports and exposed as `name` and `signal` for frontend summaries and downstream consumers.

A `$sdffe` regression fixture confirms clock and synchronous reset extraction. Backend tests: 63 passed.

Still required on the user's machine: re-analyse `counter_sync` in WSL/Yosys, confirm the UI shows `clk` and `rst_n`, inspect generated property clock/reset metadata, and run actual SBY/Z3 temporal proofs plus a mutation test.
