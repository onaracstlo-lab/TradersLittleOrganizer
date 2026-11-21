# TLO Build 700 — Stable Show and ALBUM across runs

Fixed: N3. A venue/city token splitter no longer deletes commas embedded in a recognized venue. The change is limited to preserving original punctuation at the parser boundary; it does not override venue evidence, change duplicate matching, or relax uncertain renames.

Acceptance: actual four-pass CLI fixture with a real FLAC recording, verified folder names, FLAC ALBUM tags, and bootlist Show after (1) Rename Compliantly + tagging, (2) same again, (3) tag-only, (4) inventory-only. Preserve all historical change records, current requirements/user manual/catalog, regression and manifest.

Still pending: F4 safe legacy short dates, foreign ordinals and non-decomposing Latin letters; S1,S3,S4,S6,S7 usability; L9 Windows lock-owner details; collection consolidation reversal; broader T3/T4 coverage; native Ruff, Win11 MSI/signing and GitHub Actions. Companion Build Process v144 unchanged.

## Executed verification
The first rename/tag run, repeat rename/tag, tag-only and plain inventory ran as separate CLI processes against a real FLAC and synthetic artist database; all four retained the accepted venue comma in folder, ALBUM and bootlist. Core, behavior and legacy groups passed. The full-tree import and version audits, current Requirements and Manual render, release-readiness and SHA-256 verification are recorded independently. Native Ruff and Windows CI are not attested.

## Forward plan
The next release should isolate F4 date normalization and Latin transliteration changes without relaxing protection of source recording identifiers. Low-risk UX polish S1,S3,S4,S6,S7 can follow. Treat Windows lock-owner reporting (L9) and recovery/consolidation reverse support as platform-dependent, higher-risk items that require native Windows and recovery fixtures; no unsafe automatic recovery should be added without those tests.
