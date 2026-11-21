# TLO Build 691 — incremental backlog remediation

Complete Build 690 source retained. Build Process v143 unchanged. This increment fixes **L5**, the Add Shows cross-device copy/delete gap. The shared move helper now uses destination-local hidden staging, checks every file and empty directory against the source, then compares SHA-256 content before no-replace publication and source deletion. A crash/failure during copy cannot expose a normal show folder; a failed source cleanup leaves the published verified destination and raises an explicit reconciliation error. Same-filesystem moves remain atomic non-overwriting renames. Cross-device symbolic links are rejected. This protects ordinary Add Shows staging, duplicate holds, and replacement rollback destinations. It does not change the exact-name/size duplicate rule.

New regression file: `tests/behavior/test_build691_add_shows_verified_moves.py`, covering successful and interrupted copying, same-sized changed content, collisions, source cleanup failure, symlinks, and same-filesystem rename.

## Remaining backlog

**L6** interrupted Tag Copy/Delete staging recovery; **L7** Search error display; **L9** Windows lock-owner details; **L10** low-priority hygiene; **T3/T4** behavior coverage strengthening; nonreversible collection consolidation remains documented. **L3/L8** are accepted design. Native Windows, Ruff, hosted CI, signing and MSI remain unverified until performed. Never overwrite previous build ZIPs.
