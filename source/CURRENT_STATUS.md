# Build 746 / GitHub Build Process v170

Fix Build 745 Windows migration fixture unlink failure. Legacy SQLite connections now explicitly close after every read or error; fixture setup closes all database handles after transaction completion. Log-owned minimal storage identity, bootlist, root marker, migration backups, operation evidence and shipped database bytes are unchanged. Build Process v170 remains unchanged.

Local application regression: 3282 passed, 39 skipped, 1 deselected, 2 warnings, 8 subtests passed in 123.34s (0:02:03). Process v170: 198 passed, 20 skipped. Ruff, source hygiene and independent release readiness passed. Native Windows retest, pinned CI, hardware and signed installer acceptance remain pending.
