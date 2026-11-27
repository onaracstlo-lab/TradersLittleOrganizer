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

# Build 726 venue integration

Recognize complete, context-supported venue names using read-only venues.sqlite; preserve historical names, unknown venues, legacy venues.txt and existing positional, setlist and online fallbacks. Reject ambiguous, partial and unsafe display changes. Do not modernize historical venue names. Update package stages and tests. Historical plan follows.

# Build 725 / GitHub Build Process v167 — SQLite city matching

The supplied cities.sqlite and match_city.py are integrated read-only into folder and selected-setlist location handling. A known state/province/country can support high-confidence typo correction and multiword city boundaries; exact aliases retain source spelling. Unknown/ambiguous cities use the existing positional/region/online fallbacks. The SQLite master ships externally in TLO_DBs and is MSI-managed on Windows. The city CSV is retired: SQLite is the sole city reference master; older CSVs are ignored and are not deleted. Existing built-in and positional fallbacks remain. An old CSV-only city without other location evidence may no longer resolve. For the first upgrade from a CSV-only installation, use an MSI or database-inclusive ZIP. Windows/macOS hosted build, installer-signing and native runtime acceptance are NOT ATTESTED by these local tests.

## Retained prior findings and gates

# Build 723 Add Shows workflow and cleanup policy

New behavior: immediate status counters and current folder displayed, automatic duplicate/upgrade review after Process New Shows when dups contains folders, Quit retains outstanding items, Process Duplicates remains. Deferred Windows old-folder batch has exact-label/reparse-point guard then permanent rmdir /s /q (no batch undo), and is intended as a reusable template for separate inventory copies. Immediate Delete New continues to recycle. Run native Windows cmd.exe tests before release.

# Build 723 Windows Recycle Bin defaults and duplicate cleanup

The user reproduced a failed Handle Duplicates Delete New operation from `C:\.tlo\dups` while the Windows per-volume BitBucket key was absent. TLO refused before invoking the Shell. Retain NTFS/fixed-drive, reparse-point, volume, quota and policy safeguards, but treat absent per-volume overrides as Windows defaults. Previously replaced by recycling; this is superseded by the explicitly requested Build 723 guarded rmdir policy. See tests/behavior/test_build722_recycle_defaults_and_duplicate_cleanup.py. Native Windows positive/negative real-Recycle-Bin tests and CI/signing remain acceptance requirements.

# Retained Build 721 public release Git publication remediation

Retained Build 721 / Process v163: The Build 720 native Windows/Linux/macOS pipeline assembled and hash-bound local release artifacts, but public source publication failed in three attempts when Windows Git could not write loose objects under C:\TLO-GitHub-Build. The release helper now uses packed shallow Git fetch and short per-user temporary working directories, with controlled fallback. Signed source commits, verified annotated tags, immutable production releases and SHA-256/asset signing remain mandatory. Application inventory/tagging functionality is unchanged. Native Windows publication acceptance is pending.

Acceptance: repeat native Windows release with Build 723 and process v165; confirm shallow source checkout, SSH-signed commit and annotated tag verified by GitHub, exact nine release artifacts and RELEASE_HASHES.json bound, pre-release default, no alteration of earlier release. If antivirus/Controlled Folder Access still denies Git objects, preserve artifacts, inspect its security log, and stop—do not disable integrity gates.

---

Build 723 / Process v165: Work around Windows Git loose-object Permission denied during public source publication using packed shallow fetch and short per-user temporary working copies. Require signed commit and verified annotated tag as before. Original files retained; native Windows verification required.

## Retained Build 720 F841 remediation

Removed assigned-but-unused local wholly_upper in tlo_place_display.py. Old behavior and state-code protections remain. Source regression and mandatory CI Ruff gate ensure future verification. Do not promote until native CI passes.

## Retained Build 719 — embedded uppercase fragments in compliant String2
User-reported examples showed raw String2 values such as Calvin Theatre NORTHAMPTON, MA and Lincoln Theater W.HARTFORD, CT. In compliant mode String2 is used as supplied and is not parsed into structured city/venue; the Build 718 all-uppercase-only display rule skipped these mixed-case fields. At the final display-only metadata boundary, uppercase Latin place words inside mixed-case raw String2 are now converted while terminal region abbreviations remain uppercase. Verified all five source examples through `_extract_metadata_for_group_compliant` with no setlist; original source evidence and punctuation, even a misspelling, remain unchanged. Existing inventories are not silently migrated. Application tests: 3,004 passed / 7 skipped, process: 186 passed / 13 skipped. Hosted native acceptance pending.

Retained Build 719: Compliant/path-only String2 retains the full venue+city tail, even when its casing is mixed. Display normalization corrects embedded uppercase place words and terminal region codes only. No source file, artist, tag evidence, or lookup precedence is changed.

Retained Build 718 (2026-11-22): Apply conservative proper capitalization only to detected all-uppercase venue/city/location output at the final inventory metadata boundary; retain exact source case and intentional mixed case. Tests cover setlist headers and no-setlist folders. Hosted native CI pending.

# TLO Build 723 — remediation disposition and release acceptance

**Baseline:** Build 714 / process v156. **New candidate:** Build 723 / process v165. All older release ZIPs remain immutable. No file payload is copied for Manual Tweaks undo.

## Retained Build 715 — GitHub Actions dependency-lock remediation

Run 44971626768 failed across all three native jobs at `pip install --require-hashes` because the Pygments wheel SHA-256 was mistyped in requirements-build.txt. Fixes: correct the published Pygments wheel hash and an additional corrupted Linux x64 Ruff wheel hash per PyPI metadata, add offline lock verifier before installation, and retain --require-hashes. Windows missing-package errors were downstream of the failed pip install. Only native CI can attest complete builds.

## Retained Build 714 — MSI download-to-install handoff

- MSI download and installation now use the verified final (renamed) absolute path, never a temporary name or a newly guessed path.
- The GUI refuses installation if the final file moved, disappeared, became a symlink or no longer matches the signed digest, with the exact path in the message.
- The MSI worker resolves PowerShell provider paths to native filesystem paths before calling msiexec, with improved diagnostics for missing downloaded MSIs versus missing prior MSI source (Windows Installer 1612).
- Added six regression tests for download-to-install path continuity, filenames with spaces/non-ASCII characters, missing/modified files and worker invocation.
- Source-only remediation. The running Build 685 updater cannot be patched retroactively: users must obtain the latest signed MSI manually once. Hosted Windows native installation is still required.

The exact Build 685 error text and its MSI verbose log were not supplied, so native root cause remains unproven. This source change addresses a real worker path ambiguity and improves diagnostics, not a certified reproduction of the 685 installation.

## Prior Build 713 source remediation (retained)

- **B4 (multi-root):** when more than one search root can mutate files, run read-only all-root identity preview before `walk_trees`; refuse two different folders with the same final Show/ALBUM, and refuse incomplete preflights. Per-root preflight from Build 711 remains. Cross-root warnings also appear in the GUI/CLI preview. No claim of all historic inventory collisions.
- **U3 (batch):** `tlo-reverse --manual-updates --batch N --TLOHome ... [--dry-run]` selects exactly N signed, linked journals with unique matching bootlist/unidentified state. It replays newest first under the existing inventory lock and validates tags and files before each reversal. Later, untracked inventory changes are deliberately not merged: refuse rather than rewrite unrelated rows.
- **U6:** `tlo-gi --dry-run` reuses the existing show-level preview with planned tags, never a real inventory pass. Online metadata, full post-consolidation identity and corruption probe results may still differ from the actual mutation run.
- **S2 (source implementation):** independently keyed undo journals now apply explicit Windows current-user/SYSTEM ACLs on key creation/migration; POSIX retains 0700/0600. Win11 ACL behavior still needs native acceptance.
- **S4 (source implementation):** require valid installed TLO EXE Authenticode plus exact incoming MSI signing certificate thumbprint. This prevents a same-subject certificate substitution. Automatic certificate rotation is deliberately disallowed; install a separately verified MSI manually to establish a new trusted baseline. Native signing acceptance remains open.
- **S1/S5 acceptance preparation:** add `tools/Test-TLO-Windows-Acceptance.ps1` for ordinary-user data-folder, read-only UNC/mapped-drive and signer checks. It does not claim to run installer, rename, copy, or hosted CI.

## Remaining items requiring separate validation or deeper changes

| ID | Remaining scope | Required acceptance |
|---|---|---|
| B4 | Collisions against previously inventoried but *different* search scopes; preview divergence after sibling consolidation | Build a distinct-folder re-inventory fixture; ensure no unsafe mutation |
| B5 | Ambiguous free-form place phrases not proved by comma/venue/city DB rules | Curate counterexamples and require independent venue/geography evidence |
| B7 | Every rare ID3/MP4/APE/frame variant and codec combination | Real-media byte/tag comparison on each supported container |
| U3 | Selective reversal after unrelated inventory changes | Row-level merge/rebase design and interleaving conflict tests before enabling |
| U4 | Broad reorganization of GUI options/windows | User-facing layout review and native Win11 acceptance |
| U6 | Precise results when network lookups or sibling reorganization vary | Compare preview and actual end-state on non-destructive fixture |
| S1 | `C:\.tlo` may be unwritable under standard-user MSI; generated .bat policy | Fresh Win11 non-admin install/upgrade/repair/uninstall; explicitly select user-writable TLOHome if needed; review batch script creation/execution |
| S2 | Prove inherited ACL protection on existing and newly migrated keys | Win11 standard and administrator accounts; rotation/reinstall recovery |
| S4 | Authenticode, Azure signing and manual signer rotation | Sign old/new MSI and EXE on trusted Windows machine; test rotation denial and documented manual procedure |
| S5 | Real UNC shares, mapped drives, WSL and staging journal recovery | Use two physical Windows 11 machines and disposable share fixtures; assert no cross-share/path traversal |
| R5 | Unmerged long Requirements appendices | Editorial structural consolidation after independent content reconciliation |
| T1 | Pinned Ruff and native build run | Install locked Ruff 0.16.10 and run `python -m ruff check .`; hosted Windows, Linux, macOS CI |
| P1 | Donation contact street address | Intentionally unchanged as explicitly requested by user; separate authorized edit required |

**Release gate:** A full GitHub Actions run, all nine verified native assets, Windows EXE/MSI Authenticode, independent signed update metadata, native UNC/MSI acceptance and explicit manual promotion are mandatory. Neither the source ZIP nor these local tests satisfies those gates. **Do not mark Build 723 production-ready or publish it as Latest.**

## Historical Build 713 follow-up to failed GitHub Actions run 44808377418

- Linux: All eight Build 711 `test_tag_undo_roundtrip_per_container` cases crashed before reading media because `ffmpeg` was not on PATH. Replaced on-the-fly FFmpeg generation with eight synthetic 440-Hz encoded fixtures stored in `tests/fixtures/tag_undo` and checked against independent SHA-256 pins. The tests continue executing Mutagen tagging and actual metadata undo rather than being skipped on Linux/Windows CI.
- Windows: `test_copy_destination_lock_leaves_no_host_identity` read a file while `msvcrt` had exclusively locked byte 0. Windows correctly rejected the read. The test now checks held-lock semantics and its release-time empty owner JSON only once it is unlocked, with `finally` ensuring release. Production lock semantics remain fail-closed.
- Process v157 adds early targeted gates on Linux and Windows before the full suites. The suite still blocks packaging and signing on failures.
- Live GitHub hosted jobs, Windows signing/MSI, and hardware UNC remain unverified until the next run.

## Build 723 — local preflight bytecode contamination (GitHub dispatch blocked)

Build 715 failed at the final prepared-source .pyc gate after the offline wheel-pin verifier imported tlo_version. The source included no compiled artifacts on entry; a local Python interpreter wrote __pycache__/tlo_version.cpython-314.pyc during preflight. The retained Build 716 verifier suppresses bytecode before the import, process v158 calls local Python checks with -B, and a new intermediate gate rejects source-stage artifacts. The incoming-archive and post-compile gates are unchanged. Tests execute these source-level safeguards on an isolated source copy. Hosted Windows/Linux/macOS validation and Windows signing remain mandatory. No previously published ZIP is replaced.

## Retained Build 717 — hosted report-contract failure, run 45067649844

All three platform tests failed because Build 716 changed the report literal heading and omitted Ruff/headless fields, not because an application behavior defect was demonstrated. Restore fail-closed format, label 50/6 and 26 skipped as historical tests only, require process v165 to validate contract before native launch. Windows stopped at the first failure under pytest -x; Linux observed all eight. No native release claimed.
