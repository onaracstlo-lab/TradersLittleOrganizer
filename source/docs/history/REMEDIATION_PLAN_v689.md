# TLO Build 689 — incremental remediation execution and backlog

Baseline: complete Build 688 source; companion Build Process v143 unchanged. Never overwrite prior source ZIPs. This build targets **M8** (log-token exhaustion) and **L4** (recursive duplicate-tree scan). All 36 original token names remain unchanged, and any existing token is excluded when allocating new ones. The first expansion values are 10, 11, 12. The current bounded sequence supports 1,296 distinct tokens. No log history is deleted or rewritten to make space.

Duplicate comparison is now iterative and continues to identify candidate duplicates by relative folder/file names and exact sizes, as required. It does not hash content for duplicate identity. Symlinks and unsupported objects still cause a fail-closed error. Regression fixtures test deep trees with an artificially low recursion limit, symlinks, retained legacy logs, and long-token cleanup.

## Remaining backlog (as of Build 689)

- **L1 and L2:** alternate-date city lookup and foreign-month/date-range ambiguity; require parser-grounded non-loss tests.
- **L5:** verify and safely publish cross-device Add Shows transfers before deleting a source.
- **L6:** recover or report abandoned `.tlo-partial-*` stages without unsafe automatic deletion.
- **L7:** improve Search expression error feedback (CSV formula unescaping already addressed in Build 686).
- **L9:** lock-owner message on Windows; requires native Windows reproduction.
- **L10:** incidental hygiene and UI wording with targeted tests.
- **T3/T4:** improve entry-point coverage and replace fragile source-inspection checks incrementally, not by removing validation.
- **N7 remaining limitation:** sibling collection consolidation is previewed but Reverse does not undo it; retained as documented limitation pending a safe transactional design.
- **L3:** *accepted by design*: name/structure/exact-size duplicate identity is unchanged. **L8:** empty source-only artist DB remains a build-process placeholder, with real master injected by release builder.

Every increment requires executable regression tests, up-to-date Requirements/Manual/catalog, fresh versions, source ZIP + checksum manifest, stale-reference and unused-import audit, and honest native CI/Ruff status. Windows MSI/signing, hosted CI, and release publication are not attested by local source testing.
