# TLO Build 695 — strict lint remediation

## Problem

Build 694 passed an offline import audit but failed Windows preflight (Ruff F401) because `tlo_postprocess.py` still imported `csv` without using it. This was a failure of release-preparation coverage: older AST tests checked selected files rather than the entire package. An additional unused `FLAC` import probe in `tlo_corruption.py` was found in the full-tree check and removed.

## Corrective action

- Remove unused imports; do not alter file-transfer, name, date, duplicate, audio decoding or tagging policies.
- Run `python tools/audit_unused_imports.py --root .` on **all** source and test files before producing an archive.
- Add executable regression fixtures that introduce a real `import csv` with no use in both a source module and a test module. They must be rejected by the audit.
- Preserve the mandatory Windows Ruff `python -m ruff check .` preflight. AST audit is a secondary guard and does not certify Ruff.
- Update full Requirements DOCX, User Manual RTF, requirements catalog and current-source metadata for Build 695, retaining accurate historical build references.
- Validate complete suite, source compilation, archive membership and SHA-256 before delivering.

## Acceptance and limitations

A local build that lacks Ruff cannot claim a Ruff pass or native release acceptance. Build Process v143 remains unchanged and requires native Ruff. The published pre-release must not be promoted until all native Windows/macOS, MSI, signing and hosted release gates have passed.

Existing deferred backlog items are not silently closed by a packaging-only correction. Build 694 remains immutable.
