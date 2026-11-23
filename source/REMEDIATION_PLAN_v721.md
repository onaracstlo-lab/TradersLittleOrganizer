# Build 721 public release Git publication remediation

Build 721 / Process v163: The Build 720 native Windows/Linux/macOS pipeline assembled and hash-bound local release artifacts, but public source publication failed in three attempts when Windows Git could not write loose objects under C:\TLO-GitHub-Build. The release helper now uses packed shallow Git fetch and short per-user temporary working directories, with controlled fallback. Signed source commits, verified annotated tags, immutable production releases and SHA-256/asset signing remain mandatory. Application inventory/tagging functionality is unchanged. Native Windows publication acceptance is pending.

Acceptance: repeat native Windows release with Build 721 and process v163; confirm shallow source checkout, SSH-signed commit and annotated tag verified by GitHub, exact nine release artifacts and RELEASE_HASHES.json bound, pre-release default, no alteration of earlier release. If antivirus/Controlled Folder Access still denies Git objects, preserve artifacts, inspect its security log, and stop—do not disable integrity gates.

---

Build 721 / Process v163: Work around Windows Git loose-object Permission denied during public source publication using packed shallow fetch and short per-user temporary working copies. Require signed commit and verified annotated tag as before. Original files retained; native Windows verification required.

## Retained Build 720 F841 remediation

Removed assigned-but-unused local wholly_upper in tlo_place_display.py. Old behavior and state-code protections remain. Source regression and mandatory CI Ruff gate ensure future verification. Do not promote until native CI passes.

## Retained Build 719 — embedded uppercase fragments in compliant String2
User-reported examples showed raw String2 values such as Calvin Theatre NORTHAMPTON, MA and Lincoln Theater W.HARTFORD, CT. In compliant mode String2 is used as supplied and is not parsed into structured city/venue; the Build 718 all-uppercase-only display rule skipped these mixed-case fields. At the final display-only metadata boundary, uppercase Latin place words inside mixed-case raw String2 are now converted while terminal region abbreviations remain uppercase. Verified all five source examples through `_extract_metadata_for_group_compliant` with no setlist; original source evidence and punctuation, even a misspelling, remain unchanged. Existing inventories are not silently migrated. Application tests: 3,004 passed / 7 skipped, process: 186 passed / 13 skipped. Hosted native acceptance pending.

Retained Build 719: Compliant/path-only String2 retains the full venue+city tail, even when its casing is mixed. Display normalization corrects embedded uppercase place words and terminal region codes only. No source file, artist, tag evidence, or lookup precedence is changed.

Build 721 (2026-11-22): Apply conservative proper capitalization only to detected all-uppercase venue/city/location output at the final inventory metadata boundary; retain exact source case and intentional mixed case. Tests cover setlist headers and no-setlist folders. Hosted native CI pending.

# TLO Build 721 — remediation disposition and release acceptance

**Baseline:** Build 714 / process v156. **New candidate:** Build 721 / process v163. All older release ZIPs remain immutable. No file payload is copied for Manual Tweaks undo.

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

**Release gate:** A full GitHub Actions run, all nine verified native assets, Windows EXE/MSI Authenticode, independent signed update metadata, native UNC/MSI acceptance and explicit manual promotion are mandatory. Neither the source ZIP nor these local tests satisfies those gates. **Do not mark Build 721 production-ready or publish it as Latest.**

## Historical Build 713 follow-up to failed GitHub Actions run 44808377418

- Linux: All eight Build 711 `test_tag_undo_roundtrip_per_container` cases crashed before reading media because `ffmpeg` was not on PATH. Replaced on-the-fly FFmpeg generation with eight synthetic 440-Hz encoded fixtures stored in `tests/fixtures/tag_undo` and checked against independent SHA-256 pins. The tests continue executing Mutagen tagging and actual metadata undo rather than being skipped on Linux/Windows CI.
- Windows: `test_copy_destination_lock_leaves_no_host_identity` read a file while `msvcrt` had exclusively locked byte 0. Windows correctly rejected the read. The test now checks held-lock semantics and its release-time empty owner JSON only once it is unlocked, with `finally` ensuring release. Production lock semantics remain fail-closed.
- Process v157 adds early targeted gates on Linux and Windows before the full suites. The suite still blocks packaging and signing on failures.
- Live GitHub hosted jobs, Windows signing/MSI, and hardware UNC remain unverified until the next run.

## Build 721 — local preflight bytecode contamination (GitHub dispatch blocked)

Build 715 failed at the final prepared-source .pyc gate after the offline wheel-pin verifier imported tlo_version. The source included no compiled artifacts on entry; a local Python interpreter wrote __pycache__/tlo_version.cpython-314.pyc during preflight. The retained Build 716 verifier suppresses bytecode before the import, process v158 calls local Python checks with -B, and a new intermediate gate rejects source-stage artifacts. The incoming-archive and post-compile gates are unchanged. Tests execute these source-level safeguards on an isolated source copy. Hosted Windows/Linux/macOS validation and Windows signing remain mandatory. No previously published ZIP is replaced.

## Retained Build 717 — hosted report-contract failure, run 45067649844

All three platform tests failed because Build 716 changed the report literal heading and omitted Ruff/headless fields, not because an application behavior defect was demonstrated. Restore fail-closed format, label 50/6 and 26 skipped as historical tests only, require process v163 to validate contract before native launch. Windows stopped at the first failure under pytest -x; Linux observed all eight. No native release claimed.
