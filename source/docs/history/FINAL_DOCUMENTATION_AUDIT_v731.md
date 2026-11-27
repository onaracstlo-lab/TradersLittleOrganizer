# Build 731 / GitHub Build Process v168 — date conflict and GraphQL correction

When non-compliant inventory finds competing complete dates involving sampled DATE tags and an online source is enabled, retain all date provenance and query every distinct candidate (up to four) against each enabled provider before applying online metadata. Compare actual ordered local setlist song titles, or recognizable track filenames when local setlist titles are unavailable, with the exact artist/date performances; independently compare venue, city, region and country. Do not prefer a date merely because it occurs in multiple tags, a folder, or a published concert. An explicit local performance date remains stronger than tags unless substantial contradictory song/place evidence warrants review. Select a uniquely corroborated date; with insufficient or tied evidence leave the date conflict unresolved and block ordinary automatic tagging/rename/transfer. Keep raw DATE_MATCH and per-date lookup evidence. Failed or incomplete requests are not no-match evidence. Only the selected date supplies online metadata and cached setlists. With both providers disabled retain existing local date behavior. Use the current eTreeDB GraphQL direct first/after cursor arguments at artistsRoot and nested performances, including exact article variants. Preserve KC in venue display.

29 targeted tests passed: 12 new date-conflict, GraphQL and setlist.fm regressions; 10 Build 730 rename regressions; 7 Build 729 MSI database-ownership regressions. Test fixtures inject fail-on-call audio/trash modules because Mutagen is unavailable; online API replies are mocks, not live authenticated service calls. The offline AST import-use audit passed for 450 Python files. Native full pytest, Ruff, audio tag writes, WiX/MSI installation, signing and hosted Windows/Linux/macOS CI are not attested.

The supplied Build 730 source baseline contains a zero-byte TLO_DBs/artists.sqlite and no TLO_DBs/venues.txt. This source candidate preserves the baseline database bytes without manufacturing replacement data. Build Process v168 must inject the authoritative reference files from ArtistDB-Master, as designed; this source archive alone is not a complete runnable distribution. Existing cities.sqlite and venues.sqlite are unchanged. Prior notes below are historical.

# Build 730 / GitHub Build Process v168 — verified trading shorthand rename

Non-compliant inventory identifies the original source path before Copy/Delete, uses selected setlist metadata, and retains short DB-backed artist prefixes as a last resort. When one YY-MM-DD shorthand date is ambiguous and no selected setlist supplies a date, at least two distinct same-prefix full-date track filenames must agree on one path candidate before resolving it. Rename Compliantly accepts verified artist/date trading-folder shorthand (such as trey05-12-02.flac) and can expand an exact, unique Artist DB alias for the resolved artist. Only plain format suffixes in this narrow structure can disappear; known dates, venue/location, IDs, bit-depth/source markers, and trailing recording parentheticals remain protected. The same guard applies to Inventory in-place, Copy/Delete, and Add Shows. Track filenames are not renamed.

10 targeted metadata and physical folder operation regressions passed using injected fail-on-call media/trash dependencies (Mutagen unavailable); 7 Build 729 database-installation regressions also passed. Offline AST import audit passed. Native full pytest, Ruff, actual audio tagging, WiX/MSI installation and signing, and hosted Windows/Linux/macOS CI are not attested. The working requirements DOCX was structurally checked but not fully visually reviewed. Prior notes below are historical.

# Build 729 / GitHub Build Process v168 — direct MSI database installation

MSI owns its database files at the selected TLOHome/TLO_DBs; applications only read them. Runtime no longer probes the executable distribution. Database paths and availability appear before scanning. The signed MSI integration gate checks actual installed bytes and unmanaged user data on hosted Windows. Local targeted testing passed; native Windows, full CI and full visual QA pending. Prior notes below are historical.

# Build 728 / GitHub Build Process v168 — original-folder parenthetical preservation

Keep original trailing recording parentheticals, including (early), (late), (mtx), and (24). Do not append a redundant canonical performance qualifier when an equivalent complete original parenthetical is present. Refuse compliant folder renames that would discard, alter, or reorder any ordinary trailing group; retain existing collision/part and identity validation. Correct the historical projection to restore the original folder suffix, not the incomplete historical show name. Native CI, signing and full visual documentation QA not attested. Prior status follows as historical evidence.

# Build 727 / GitHub Build Process v168 — trailing parenthetical preservation

Retain consecutive and nested trailing parenthetical recording qualifiers during parsing and venue matching. Apply venue/city display substitutions only to the name core, not the qualifier text. Match venue-only paths without treating the suffix as part of the venue. Keep existing missing/ambiguous catalog fallbacks, copy/alt verification, and historical venue protections. Native CI, signing and full visual documentation QA not attested. Prior status follows as historical evidence.

# Build 726 source-candidate documentation update

Venue matching, database packaging, fallback and historical-name policy updated. Native acceptance and final visual QA not attested. Prior audit follows as historical only.

# Build 725 / GitHub Build Process v167 — SQLite city matching

The supplied cities.sqlite and match_city.py are integrated read-only into folder and selected-setlist location handling. A known state/province/country can support high-confidence typo correction and multiword city boundaries; exact aliases retain source spelling. Unknown/ambiguous cities use the existing positional/region/online fallbacks. The SQLite master ships externally in TLO_DBs and is MSI-managed on Windows. Existing Build 723 behavior is retained. Windows/macOS hosted build, installer-signing and native runtime acceptance are NOT ATTESTED by these local tests.

## Current Build 725 source verification

- Application: **3,039 passed, 7 skipped** across 337 modules in 13 isolated source suites; 4 warnings.
- GitHub Build Process v167: **194 passed, 14 skipped**.
- SQLite matcher remains external/read-only. The fallback CSV, region/state/country positioning, venue and existing network/setlist sources are retained.
- Current Requirements DOCX and Manual RTF metadata, source-release pointer, requirements catalog, third-party notices and remediation build identity have been corrected.
- Native Ruff, Windows installer/signing, runtime Windows acceptance and hosted CI remain **NOT ATTESTED**.

## Retained prior findings and gates

## Historical Build 723 document and source audit — pre-release candidate

The current build restores guarded permanent rmdir in the reusable Windows deferred cleanup template, adds Add Shows progress and automatic duplicate review, and retains manual resume. Earlier recycle-only batch documentation is superseded. Native Windows release remains NOT ATTESTED.

## Historical TLO v1.7 Build 723 — documentation and source audit

**Historical Build 723 status:** The older source candidate was not signed or hosted-CI-attested; its companion was Process v165.

## Current correction

Build 723 changes the deferred Windows `deleteReplacedFolders.bat` template to **permanent `rmdir /s /q`**, guarded by an exact current volume-label check, safe rooted folder validation and reparse-point rejection. No batch deletion undo or recycling mechanism is generated. This script may be reused for other inventory copies after verifying each target drive and label. The separate GUI **Delete New / Keep Old** operation retains its Windows Recycle Bin implementation (and the Build 722 default-registry fix).

Add New Shows displays per-folder execution status, progress totals and staged/duplicate/held/error counts. Once Process New Shows finishes, it automatically launches review for existing/new pending folders in `dups`. The **Process Potential Duplicate/Upgrades** button remains; quitting without a resolution retains the candidate for later review. Original new-show source processing and artist metadata rules are unchanged.

## Evidence verified locally

- Application behavior: **2,733 passed, 7 skipped, 3 warnings** across **284 modules** in 13 independently completed shards.
- Application contracts/unit/integration: **295 passed**; combined unique application **3,028 passed, 7 skipped**.
- Build-process suite: **194 passed, 14 skipped**.
- Release hygiene and 25-disposition source readiness: passed before packaging.
- All 435 application Python files parsed without syntax errors, no compiled artifacts found; Ruff lint is local-unattested and mandatory pinned Ruff, native cmd.exe operations and hosted CI remain release gates.
- Historical Build 723 carried Requirements DOCX and RTF manual, catalogs, changelog, README, release notes, verification and manifests; Build 725 provides newly versioned counterparts and Process v167.

## Remaining acceptance

Native Windows 11 confirmation of the immediate GUI Recycle Bin path and the independent deferred rmdir batch on labeled/unlabeled volumes; pinned Ruff 0.16.10; native Windows/Linux/macOS GitHub Actions; package signing/scanning and release publication **remain NOT ATTESTED**. Retained earlier MSI, wheel-lock, packed Git-publication, tag-undo, and capitalization fixes require their ordinary native release gates. Prior released ZIPs have not been modified.
