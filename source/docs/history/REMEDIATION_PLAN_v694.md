# TLO Build 694 — incremental remediation

**L10 date-range hygiene**: every recognized same-month multi-day date must be a valid calendar day on or before today. The entire range is rejected when any day is future, while historical full-date behavior stays unchanged.

**T3/T4 incremental behavioral coverage**: new Build 694 tests exercise the actual date parser and known historical range fixtures. The Build 693 city-label source-only test has been replaced with an executable real-CSV catalog test. Coverage improvement is measured by executable behaviors, not by inflating a source-text assertion count. T3/T4 remain partially open; GUI/CLI and platform-specific coverage remains insufficient.

All Build 693 and earlier fixes are retained. No changes to duplicate matching, FLAC integrity policy, staged transfers, or signed updater.

## Remaining open / accepted items

- L9: Windows mandatory lock owner details: native Windows execution required before claiming a correction.
- L10: remaining dormant dry-run and compatibility parameters: preserved pending characterization.
- T3/T4: expand actual GUI/CLI/worker failure tests and replace more source-text assertions, cautiously.
- Collection consolidation: not reversible automatically; a durable journal design requires explicit review before implementing it.
- L3/L8: accepted designs.

Every build must include full source, tests, current requirements/manual/catalog, verified SHA-256 manifest, and evidence of stale-version and import audits. Native Ruff, Windows MSI, signing and hosted platform jobs remain independent release gates.
