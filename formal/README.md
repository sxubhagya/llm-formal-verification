# Formal verification workspace

The user's Ubuntu 24.04 WSL2 environment has Yosys 0.33, SBY v0.70-9-g79fc9ed, Z3 4.8.12, and Boolector 1.5.118 installed. A simple combinational assertion passed with `smtbmc z3`; a deliberately false assertion failed and produced a VCD trace. The test files are currently in `~/formal_test`, not this repository.

Planned backend integration must use isolated work directories; capture tool versions, command, logs, exit code, status and artifacts; preserve counterexamples; distinguish proof from bounded checks; and never classify timeout/unknown as PASS. No application-level formal runner is implemented in this build.
