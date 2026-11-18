# Build 685 — Ruff F401 remediation

**Application:** TLO v1.7 Build 685.  **Build Process:** v143 (unchanged).

## Symptom and cause

Native Windows preflight on Build 684 passed readiness and stopped on two
F401 unused imports in `tests/behavior/test_build683_rename_search_parallel.py`:
`json` and `tlo_rename_safety`. Local pytest did not exercise a Ruff lint
binary, so the earlier test report correctly marked lint as not attested.

## Applied correction

Remove only the two unused imports. Preserve all application behavior and
Build Process v143. Assign a new source-build number and produce a new
complete ZIP. Keep previously distributed ZIPs intact. Refresh Requirements,
User Manual, catalog, release notes and SHA-256 manifest for Build 685.

## Regression and release policy

Rerun compilation, application pytest, focused rename/Search/parallel tests,
Python AST import-use verification, and the v143 release-readiness gate.
Native Windows `python -m ruff check .`, MSI, signing, and GitHub release
assembly must still pass; no claim of signed publication based on local tests.

## Executed checks (local)

- Python syntax: all 390 Python sources compiled.
- Focused Build 683 rename/Search/parallel and release metadata: 15 passed.
- Full application pytest: **2,757 passed, 6 skipped, 0 failed**, four warnings.
- Unchanged v143 build-process pytest: **157 passed, 13 skipped, 0 failed**.
- Build 685 readiness: PASS, 25 recorded finding dispositions.
- Requirements DOCX: 100 pages; User Manual RTF: 34 pages.
- Archive checksums: verified against each member after final packaging.
- Ruff binary not available in this Linux environment; the two reported unused imports
  have been removed and their absence checked via Python AST. The native Windows
  Ruff gate is required before any public prerelease can be deemed successful.
