# TLO Build 693 — incremental remediation

Full, independently versioned Build 693 source includes all Build 692 changes. **L7 Search display/error reporting** is explicitly tested and improved: Search distinguishes invalid UTF-8 input and malformed CSV from expression failures, retains formula-escaped Show identity without visible apostrophes, and gives a CSV UTF-8 remedy.

**L10 safe hygiene increment** removes an unused MP3 import and an unreachable return, corrects the city catalog diagnostic, and documents retained compatibility signatures. No behavioral change to corruption criteria, duplicate identity, date parsing, or transfer semantics is intended. Other L10 items that might affect behavior remain deferred.

## Remaining backlog

- **L9** Windows lock-owner details: native Windows-only validation needed.
- **L10** Remaining hygiene: dry-run code path and legacy compatibility parameters require proof before removal.
- **T3/T4** Add executable behavioral coverage for risky paths; retire source-only assertions only when equivalent behavioral tests exist.
- **Collection consolidation** is not automatically reversible; do not guess source layout or overwrite folders.
- **L3/L8** remain accepted designs.

Each subsequent increment needs a separate complete source ZIP, up-to-date Requirements and User Manual, regression tests, stale-version checks, real Ruff F401 checks including tests, and SHA-256 integrity. Ruff and native MSI/signing/GitHub Actions acceptance are not attested by local source checks.
