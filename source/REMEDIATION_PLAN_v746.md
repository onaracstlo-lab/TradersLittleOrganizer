# Build 746 — SQLite handle lifetime remediation
Baseline Build 745, companion Build Process v170 unchanged.
1. Diagnose native Windows failure in run 46105172247 (2340 passed, 75 skipped, one failure in migration fixture unlink). Distinguish this database handle error from the prior Git object staging failure.
2. Reproduce the leaking production connection on both successful and exceptional reads by retaining the actual SQLite connection and requiring explicit close. Keep the original regression's unlink and exact-byte checks.
3. Close legacy read-only connections in all paths; use the existing UNC-safe read-only catalog opener. Preserve migration, existing log formats, read-only behavior, original backups and evidence safeguards.
4. Ensure fixture database transactions commit/rollback and connections close deterministically; audit the other direct SQLite transaction-only contexts and remedy the same issue in tests.
5. Execute targeted and full regression tests, lint, source and independent release preflight checks. Update documents and current version references, preserve historical evidence and package a complete new source archive.
6. Native Windows retest and hosted signing/installer acceptance remain mandatory and pending.

Execution: steps 1–5 complete locally. Final native acceptance (step 6) remains pending. See REGRESSION_RESULTS_v746.txt and docs/validation.
