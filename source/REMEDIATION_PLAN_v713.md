# TLO Build 713 — remediation disposition and release acceptance

**Baseline:** Build 712 / process v154 (failed hosted CI run 44808377418). **New candidate:** Build 713 / process v155. All older release ZIPs remain immutable. No file payload is copied for Manual Tweaks undo.

## Addressed and locally testable in this iteration

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

**Release gate:** A full GitHub Actions run, all nine verified native assets, Windows EXE/MSI Authenticode, independent signed update metadata, native UNC/MSI acceptance and explicit manual promotion are mandatory. Neither the source ZIP nor these local tests satisfies those gates. **Do not mark Build 713 production-ready or publish it as Latest.**

## Build 713 follow-up to failed GitHub Actions run 44808377418

- Linux: All eight Build 711 `test_tag_undo_roundtrip_per_container` cases crashed before reading media because `ffmpeg` was not on PATH. Replaced on-the-fly FFmpeg generation with eight synthetic 440-Hz encoded fixtures stored in `tests/fixtures/tag_undo` and checked against independent SHA-256 pins. The tests continue executing Mutagen tagging and actual metadata undo rather than being skipped on Linux/Windows CI.
- Windows: `test_copy_destination_lock_leaves_no_host_identity` read a file while `msvcrt` had exclusively locked byte 0. Windows correctly rejected the read. The test now checks held-lock semantics and its release-time empty owner JSON only once it is unlocked, with `finally` ensuring release. Production lock semantics remain fail-closed.
- Process v155 adds early targeted gates on Linux and Windows before the full suites. The suite still blocks packaging and signing on failures.
- Live GitHub hosted jobs, Windows signing/MSI, and hardware UNC remain unverified until the next run.
