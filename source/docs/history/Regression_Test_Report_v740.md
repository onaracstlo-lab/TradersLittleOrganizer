# Build 740 source regression

Source candidate only. Build Process v169 is unchanged.

## Reproduced release blockers
The unmodified v169 release-readiness verifier reproduced both reported errors on the original Build 739 source: stale evidence build 737 and an extra two keys inside the exact Build 681 disposition namespace. Build 740 updates the build identity, preserves all 25 original records and moves STORAGE736 and RENAME737 intact to supplemental_findings. Review 732 evidence and open issues are retained.

## Current local verification
| Check | Result |
|---|---|
| Process v169 release-readiness verifier | PASS |
| Source release hygiene | PASS |
| Ruff lint (local version) | PASS |
| New remediation contract cases | 7 passed |
| Final source suite | 3241 passed, 39 skipped, 1 deselected, 2 warnings, 8 subtests passed in 89.41s (0:01:29) |
| Companion Process v169 suite | 194 passed, 14 skipped, 1 warning in 2.36s |

The first full run found four incorrectly renumbered requirement-catalog test file references. Those were restored to their original Build 739 references, the targeted checks passed, and the final source suite was rerun. No application feature or database change was required.

The local application suite was run with `XDG_DATA_HOME` unset and `PYTHONDONTWRITEBYTECODE=1`, using `python -m pytest -q -p no:cacheprovider -k 'not test_process_pool_crash_retains_completed_groups'`. The excluded test was also attempted separately and its multiprocessing manager failed before the test could exercise crash recovery because this environment prohibits Unix socket creation (PermissionError / EOFError). This existing test is unmodified and the exclusion is local only. The 39 skips relate to native-platform requirements, Tk display or fixture encoder availability. Local warnings are not suppressed.

All native Windows/Linux/macOS release acceptance, pinned CI lint, scanning, signing, release-integrity verification, MSI install/uninstall and publication still require a successful hosted run. The DOCX and RTF edits are build-identity updates; full rendered visual verification has not been performed for the current document version.
