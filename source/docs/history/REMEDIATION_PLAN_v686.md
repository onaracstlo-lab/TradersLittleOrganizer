# TLO v685 deep-review remediation plan — Build 686 execution and follow-on releases

## Release policy

Every application build is a new complete source ZIP with matching `vN` filenames, Requirements DOCX, User Manual RTF, catalog, SHA256SUMS manifest, release notes and independently runnable tests. Never overwrite Build 685 or any prior ZIP. Build Process v143 stays unchanged unless its code changes. All native Windows MSI, signing, Linux/macOS packaging, and GitHub pre-release gates remain mandatory; local Python tests do not attest these platform jobs.

Each new build must pass Python compilation, plain pytest without bytecode environment hacks, the available Ruff check on **all** files including tests, documentation content/metadata stale-reference checks, archive manifest checks, and executable regression cases for its fixed findings. When Ruff is unavailable, record the limitation and keep Windows lint a mandatory release gate.

## Staging / findings disposition

| Review finding | Planned stage | Status in Build 686 |
|---|---|---|
| N1 child re-inventory Reverse archive | 686 data integrity | Fixed and regression tested |
| N2 numeric identity lost on rename | 686 data integrity | Fixed and regression tested |
| N3 tag/bootlist idempotency | 687 behavior | Deferred |
| N4 invalid bootlist encoding detected late | 686 data integrity | Fixed and regression tested |
| N5 formula escaping/identity mismatch | 686 data integrity | Fixed and regression tested |
| N6 unset MD5 unverifiable messaging/tagging | 688 audio behavior | Deferred |
| N7 Dry Run collection consolidation | 688 workflow, needs reverse design | Deferred |
| N8 multilingual rename protection | 687 behavior | Deferred |
| N9 multi-path prompt defaults | 686 small safety change | Fixed; targeted GUI verification remains native |
| N10 worker crash summary overclaims completion | 687 messaging | Deferred |
| N11 ambiguous Search View placeholder error | 687 user-facing search | Deferred |
| N12 Search grammar corner cases | 687 search | Deferred |
| N13 rename skip count visibility | 687 reporting | Deferred |
| N14 non-UTF-8 Linux folder names | 688 platform-specific | Deferred |
| N15 bootlist postprocess write not atomic | 686 data integrity | Fixed and regression tested |
| N16 deleteDupes unverifiable FLAC explanation | 688 audio behavior | Deferred |
| T1 plain pytest bytecode failure | 686 validation | Fixed; plain suite required |
| M8/L1/L2/L4-L7/L9/L10/T3/T4 | separate existing backlog | Deferred; no broad refactoring |
| L3 duplicate identity by name and size | accepted user design | Unchanged |

## Additional requested enhancement

Windows MSI `Traders Little Organizer` Start Menu folder gets **TLO Artist Database Search** shortcut to `search-artist-db.exe`; the executable must be staged for the shortcut to appear. The cross-platform portable ZIP approach is unchanged.

## Build 686 acceptance

Focused tests must demonstrate that pruning one branch leaves operations in another branch reversible, identifier/date checks skip lossy renames, non-UTF8 bootlists are refused before mutations, formula-escaped CSV remains searchable, writer failure preserves the bootlist, and WiX includes the shortcut. Full suite / source-manifest verification evidence is recorded in REGRESSION_RESULTS_v686.txt and BUILD_VERIFICATION_v686.txt. Native Windows MSI compilation, Windows Ruff, and signed publication cannot be validated in this Linux workspace.
