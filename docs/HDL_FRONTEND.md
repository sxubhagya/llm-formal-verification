# HDL Frontend and Design IR (Initial Implementation)

## Frontend choice
The first implementation uses Yosys as the primary parser/elaborator. It is already installed in the project's Ubuntu WSL environment and can emit a JSON netlist. The Python backend normalizes that output into the project's own Pydantic-based `DesignIR` models. This separates the rest of the framework from Yosys-specific JSON details.

The integration is modular: `YosysRunner` owns process execution, `HDLAnalysisService` owns the workflow, `ir_builder` owns normalization, and the API owns upload validation. Slang/pyslang can be considered later if the supported SystemVerilog subset proves insufficient.

## API
`POST /api/designs/analyze` accepts multipart form data:
- `top_module`: top-level module name
- `files`: one or more `.v` / `.sv` files (2 MiB per file limit)

On success it returns `status: ANALYZED`, a serialized `design` IR, and a short Yosys log tail. Parse/elaboration failures return HTTP 422 with diagnostics. Missing Yosys returns HTTP 503.

## WSL configuration
On Windows, `HDL_FRONTEND_MODE=auto` selects WSL. `WSL_DISTRO` defaults to `Ubuntu`. Set `HDL_FRONTEND_MODE=wsl` to force WSL, or `native` to use a native `yosys` executable. In WSL/Linux, `auto` uses native Yosys.

## IR contents
The initial IR records modules, attributes, ports, net names, cells, cell connections and parameters. It classifies cells as sequential, combinational, internal, or module instances. Sequential cells are summarized as register-like elements, with clock/reset candidates inferred from common Yosys cell pin names.

## Important limitations
- Yosys supports synthesizable Verilog and a subset of SystemVerilog, not the entire language standard.
- The current script runs `read_verilog -sv`, `hierarchy -check`, `proc`, `opt`, and `write_json`.
- Optimization may transform source-level structures; this IR describes the elaborated/optimized representation, not a lossless syntax tree.
- Clock/reset identification is structural inference and requires review. It is not a designer-provided timing specification.
- The initial API accepts source files uploaded to the backend and uses temporary files. It does not persist designs.
- The API endpoint has basic file extension and per-file size validation; authentication, aggregate upload limits, and production hardening are future work.
