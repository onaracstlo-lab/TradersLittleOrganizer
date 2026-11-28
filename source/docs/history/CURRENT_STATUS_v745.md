# Build 745 / GitHub Build Process v170

Existing numbered logs now contain minimal storage identity snapshots on writable reopen. Existing `folderOperations.log` stores durable records and historical operation evidence. Legacy JSON/SQLite are read only for migration; original files remain recovery backups. No bootlist format change. No process update.

Local validation passed: 3280 application tests; 39 skipped; one sandbox-only deselection; 8 subtests passed. Process v170: 198 passed, 20 skipped. Ruff, source hygiene and independent release readiness passed. Native hardware, pinned CI and signed installer acceptance remain pending.
