# Build 699 — Reporting and recovery output

Implemented: F6 current-run Rename Compliantly counts; S2 clear error for unexpected Boolean Search close parenthesis; S5 staged-move dry-run counts. All prior corrections retained, including audio safety and Windows recovery. No change to folder mutation rules. Build Process v144 unchanged.

Remaining: N3 Album/Show/folder idempotency; F4 permissible two-digit/foreign-format date and special-character renames subject to safety tests; S1,S3,S4,S6,S7; L9 Windows lock-owner native testing; test-coverage T3/T4; collection consolidation reverse design; native Windows CI and signing acceptance.

## Execution and gates
Five new executable tests address F6, S2 and S5. In addition, an older broad-exception regression detected a silent handler while inspecting optional FLAC metadata; the handler now records diagnostic detail without changing the fail-closed decision. Each module is checked against legacy tests, source compilation, full-tree import audit and current documentation rules. The complete v699 source ZIP has an independent SHA-256 manifest. The requirements DOCX and manual RTF were rendered and visually checked. Build Process v144 is the companion, unchanged; native Windows acceptance and pinned Ruff are *pending*, not passed.

## Release order and planned remaining increments
- Build 700 (planned): N3 record/ALBUM/Show idempotency under repeated Rename Compliantly, plain inventory and tag-only; preserve folder/source identity, require real multi-run FLAC tagging fixtures.
- Build 701 (planned): F4 safe two-digit-date/foreign-ordinal/transliteration rename behavior; allow only an independently resolved exact date and artist, and retain numeric source identifiers.
- Later focused builds: S1,S3,S4,S6,S7 UX; L9 native Windows lock diagnostics; collection-consolidation Reverse design/recovery (no guessing or overwriting); additional T3/T4 behavior tests. Native CI windows test/failure diagnostics must be validated, including full logs and signed MSI.
