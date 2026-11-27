# Build 733 / GitHub Build Process v169 — hosted test corrections

Correct metadata evidence paths to retain Windows drive/UNC roots and WSL mount prefixes. Resolve date conflicts with a complete venue confirmed by both the folder and unlabeled setlist header rather than vetoing the result with a partial legacy venue-catalog match; preserve explicit venue and geographic disagreements.

Build 732 run 46069821802 failed native regression checks. Build 733 local application suite: 3153 passed, 37 skipped, 1 deselected, 1 warning, 8 subtests passed in 80.88s (0:01:20). Build process v169: 194 passed, 14 skipped. Build 733 native acceptance has not been attested. Prior notes are historical.

# Build 732 / GitHub Build Process v169 — album and auxiliary search

Undated Artist - Album records write only String2 as the Album tag regardless of Artist in Album; lossless separator spacing is normalized for compliant renames. Main Search submenu opens Inventory, Artist, Cities or Venues with the clipboard query. searchAuxDBs searches the three installed SQLite catalogs read-only.

All three user-supplied SQLite catalogs pass quick_check and are included unchanged. Legacy venues.txt remains an external build input. Native release NOT ATTESTED. Prior notes are historical.

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

# Build 726 / GitHub Build Process v168 — SQLite venue matching

Recognize complete, context-supported venue names using read-only venues.sqlite; preserve historical names, unknown venues, legacy venues.txt and existing positional, setlist and online fallbacks. Reject ambiguous, partial and unsafe display changes. Do not modernize historical venue names. Database-inclusive packages carry all four physical reference masters. Native acceptance pending. Prior status follows.

# Build 725 / GitHub Build Process v167 — SQLite city matching

The supplied cities.sqlite and match_city.py are integrated read-only into folder and selected-setlist location handling. A known state/province/country can support high-confidence typo correction and multiword city boundaries; exact aliases retain source spelling. Unknown/ambiguous cities use the existing positional/region/online fallbacks. The SQLite master ships externally in TLO_DBs and is MSI-managed on Windows. The city CSV is retired: SQLite is the sole city reference master; older CSVs are ignored and are not deleted. Existing built-in and positional fallbacks remain. An old CSV-only city without other location evidence may no longer resolve. For the first upgrade from a CSV-only installation, use an MSI or database-inclusive ZIP. Windows/macOS hosted build, installer-signing and native runtime acceptance are NOT ATTESTED by these local tests.

## Retained prior findings and gates

## Historical TLO Build 723 / Process v165 — Add Shows workflow and cleanup-template correction

Current source candidate: live per-folder Add Shows progress, automatic duplicate review after processing, and volume-checked deferred Windows rmdir cleanup without reversal. Native Windows command execution remains unverified.

## Historical TLO Build 723 / Process v165 — Windows duplicate Recycle Bin correction

The current source candidate resolves the missing per-volume registry-default false refusal. Windows Shell end-to-end acceptance is still required; old Build 721-generated cleanup batch files must not be reused. The delete-new path remains COM recycle-only and policy-protected; the earlier generated Windows delete-old batch recycling has been superseded by the Build 723 permanent-delete template, under the same exact volume label requirement. Previous Git publication hardening remains. Native release testing/signing NOT ATTESTED.

---

## Historical TLO v1.7 Build 723 — source candidate (NOT production)

Retained Build 721 context: The Build 720 native Windows/Linux/macOS pipeline assembled and hash-bound local release artifacts, but public source publication failed in three attempts when Windows Git could not write loose objects under C:\TLO-GitHub-Build. The release helper now uses packed shallow Git fetch and short per-user temporary working directories, with controlled fallback. Signed source commits, verified annotated tags, immutable production releases and SHA-256/asset signing remain mandatory. The earlier publication-stage change remains; native Windows publication acceptance is pending.

**Historical Build 723 test evidence:** 3,028 application passes, 7 skips; 194 process passes, 14 skips; 13 independent behavior shards; ready/hygiene checks pass. Native Windows publication is not verified.

**Retained functionality:** Build 719 mixed-case city/venue display fix, Build 720 Ruff F841 correction, no new inventory/tag semantics.

---

### Earlier build context (archival)

Retained Build 720: removed unused wholly_upper assignment, preserving Build 719 display normalization; Ruff CI and native acceptance pending.

**Retained Build 719 display remediation:** compliant/path-only String2 is not split into city/venue fields. Final display normalization fixes uppercase city fragments embedded in raw mixed-case venue text (e.g., Calvin Theatre NORTHAMPTON, MA), retains terminal US state codes, and keeps the original path/setlist/evidence. Build 719 historic application 3,004 passed, 7 skipped; process 186 passed, 13 skipped. Native release acceptance pending.

Retained Build 719: Compliant/path-only String2 retains the full venue+city tail; its display normalization corrects embedded uppercase place words and terminal region codes only. No source file, artist, tag evidence, or lookup precedence is changed.

Retained Build 718 (2026-11-22): Apply conservative proper capitalization only to detected all-uppercase venue/city/location output at the final inventory metadata boundary; retain exact source case and intentional mixed case. Tests cover setlist headers and no-setlist folders. Hosted native CI pending.

## Historical TLO v1.7 Build 723 — source candidate (NOT production-ready)

Companion GitHub Build Process **v165**.

**Retained Build 716 CI staging fix:** local Build 715 halted after its wheel-pin verifier generated tlo_version.cpython-314.pyc within the temporary source snapshot. Build 716 disabled this bytecode creation, and process v158 also invokes local source Python checks with -B. Prior Build 715 Pygments/Ruff pin corrections and mandatory pip --require-hashes remain in force. CI run 44971626768 was the earlier Build 714 dependency-lock failure. Build 723 retains verified MSI handoff path continuity and Windows Installer source diagnostics; the standalone Build 685 updater cannot be retrofitted. Build 723 retains Build 712 detailed read-only CLI preview and a preflight for colliding Show/ALBUM names in multi-root mutating runs, safe linked Manual Tweaks `--batch N` undo, Windows private undo-key ACLs, strict MSI signer-certificate continuity and a Windows native acceptance script. All original audio is preserved; undo never duplicates media payloads.

**Unverified/remaining:** Win11 standard-user C:\.tlo installation and ACL acceptance; actual MSI update/signing/rotation; mapped-drive and UNC mutation/recovery tests; hosted Windows/Linux/macOS CI; full pin-locked Ruff; remaining free-form location ambiguity, later-inventory selective undo, GUI control regrouping, uncommon tag/frame types and requirements-addenda consolidation. Source preflight is not native release attestation.

Read `REMEDIATION_PLAN_v725.md` for the exact disposition and `REGRESSION_RESULTS_v725.txt` for measured test results. Every correction uses a new ZIP and build number; do not overwrite prior packages.

Build 713 fixed hosted CI fixture portability and the Windows byte-locked-file test assumption; these remain in Build 723. Build 715 corrected the Build 714 Pygments/Ruff dependency-lock typos; Build 716 corrected the subsequent local bytecode-contamination error. Full native signing and CI gates remain required.

**Retained Build 716 local staging remediation:** Run 715 failed before GitHub upload because the wheel verifier imported tlo_version without -B, leaving __pycache__/tlo_version.cpython-314.pyc in the prepared tree. Build 716 and Process v158 guard against source-local bytecode generation. Native CI/signing not attested.

**Retained Build 717 / process v159:** Restored non-attested verification-report contracts following run 45067649844. The gate remains mandatory in Build 723 / process v165. Native acceptance remains pending.

**Local Build 725 validation:** 3,039 passed and 7 skipped across 337 application test modules in 13 process-isolated groups; 194 process passes, 14 skipped. See REGRESSION_RESULTS_v725.txt for exact source-suite totals; source hygiene/readiness passed. Native and Ruff remain required.
