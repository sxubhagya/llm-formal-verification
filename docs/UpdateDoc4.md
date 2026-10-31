# UpdateDoc4 — WSL Windows-Path Translation Fix

**Project:** LLM-Assisted Formal Verification Framework for Verilog RTL  
**Update:** 4  
**Scope:** Fix the Windows-to-WSL path conversion failure found during the first real RTL upload test.

## 1. Issue observed

The user submitted the example counter through:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/api/designs/analyze" -F "top_module=counter" -F "files=@rtl/examples/counter/counter.sv"
```

The API accepted the upload but failed when the Yosys runner attempted to translate the temporary Windows upload path into a WSL path. The diagnostic showed a path resembling:

`C:UsersfatehAppDataLocalTempuploaded_rtl_...`

The backslashes in the Windows path had been lost during WSL command argument translation. This is a runner integration bug, not an RTL syntax error and not a problem with the user's counter file.

## 2. Fix implemented

`backend/app/services/hdl/yosys_runner.py` now normalizes resolved Windows paths to forward slashes before passing them to `wslpath`:

- Before: `C:\Users\...\source_0.sv`
- After: `C:/Users/.../source_0.sv`

The WSL path conversion remains performed through an argument list with `shell=False` (the default). The patch does not introduce shell command interpolation.

## 3. Regression test added

A unit test mocks the WSL path-conversion process and verifies that:
- The path passed to `wslpath` uses forward slashes.
- The returned WSL path is read correctly.

This test protects the specific Windows-to-WSL path handling behaviour that failed in the user's live run.

## 4. What this update does and does not establish

This update fixes the identified path-conversion defect and adds a regression test. It does **not** establish that a full Yosys invocation and JSON IR generation has succeeded on the user's machine. That remains the next integration test after the user installs this update.

The user's previous six tests passed before this fix. The new expected unit-test count is seven.

## 5. Apply the update

1. Stop the backend server with `Ctrl + C`.
2. Extract this ZIP into `C:\Users\fateh\Desktop\Program Folder`.
3. Replace existing files when prompted.
4. Keep `.venv` and `frontend/node_modules` intact; this archive excludes them.
5. In PowerShell at the project root, activate `.venv` if desired, then run:

```powershell
python -m unittest discover -s backend\tests -v
```

Expected: seven tests pass.

6. Restart the backend:

```powershell
python -m uvicorn backend.app.main:app --reload
```

7. In a second PowerShell terminal, retry the same `curl.exe` upload command for the counter.

## 6. Acceptance criteria for the next test

A successful next integration test should return HTTP 200 and include the structured design representation for top module `counter`. If it fails, capture the complete JSON error response and the backend terminal output.

---

**Status:** Path-translation fix implemented; regression test added. Full Windows-to-WSL RTL analysis remains pending user-side verification.
