# TLO Build 692 — incremental backlog remediation

Complete independent Build 692 source includes the prior Build 691 transfer fix and all older work. **L6** now uses an exclusively-created, fsync'd journal before each same-volume staged Copy/Delete rename, recording the original path, stage path, intended destination and worker PID/host. A normal completed move or successful rollback clears its record. If a worker dies between the two renames, `tlo-reverse.exe "DESTINATION_DIRECTORY" --recover-staging --dry-run` displays the orphaned recorded move. An explicit rerun without `--dry-run` restores the entire staged tree to its unoccupied original source path via no-replace rename. It never moves unjournaled partial copies, refuses occupied source names, validates journal paths and current owner, and fails closed on conflicts.

New regression tests: `tests/behavior/test_build692_stage_recovery.py` (including real subprocess termination, preview and recovery, owner liveness, malformed journals, collisions and rollback), plus existing Build 563 staged Copy/Delete tests. The existing duplicate identity rule is unchanged.

## Remaining backlog

**L7** Search error presentation; **L9** native Windows lock-owner details; **L10** hygiene; **T3/T4** behavior test coverage improvements and retirement of source-only assertions. Collection consolidation remains explicitly nonreversible. **L3/L8** remain accepted-design. Native Windows/MSI, Ruff and release/signing CI remain required. Never overwrite old build ZIPs.
