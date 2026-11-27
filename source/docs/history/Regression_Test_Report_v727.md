# Build 727 source-candidate regression report

## Scope
Build 727 fixes preservation of complete, balanced trailing parentheticals (including nested and consecutive groups), limits place-name display substitutions to the name core, and excludes recording qualifiers from venue-only path matching. The venue SQLite catalog, legacy and missing-catalog fallbacks, and copy/alt verification are unchanged. GitHub Build Process v168 is unchanged. The existing requirements already mandate preservation of trailing parentheticals.

## Executed application tests
- Targeted Build 726 + 727 venue and suffix suite: 45 passed (24 new tests, 21 retained tests).
- Actual paired folder-metadata outputs from the original Build 726 source and corrected Build 727 source, using identical synthetic folder inputs: 22 pairs, 7 changed, 15 unchanged. The separate Test_Folder_Name_Changes_v727.csv lists all 7 changed pairs in this targeted set (not instrumentation of every folder emitted by legacy tests).
- Full application suite, final cleaned run: 3,060 passed, 37 skipped, 1 failed, 2 warnings in 59.02s. The sole failing test, test_build683_rename_search_parallel.py::test_process_pool_crash_retains_completed_groups, also failed in the exact original Build 726 source when rerun in isolation: the execution environment prohibits the AF_UNIX socket required by multiprocessing.Manager (PermissionError, then EOFError). This gate is not waived; recheck in native CI.
- The earlier full run exposed stale release metadata, a missing manifest, pre-existing local bytecode, and XDG_DATA_HOME pointing outside the test's fake home. The release metadata and manifest were corrected, bytecode removed and XDG_DATA_HOME unset; the final cleaned run passed those tests.
- Source release hygiene checks: passed. The runtime is Python 3.12.14 with pytest 9.2.0, not the pinned release Python and pytest. Native Windows/macOS, GUI display-dependent, pinned Ruff, installer, signing, distribution and hosted CI gates are not attested.

## Historical log review (not a TLO replay)
Read-only review of the supplied Build 726 Historical_Log_Comparison.csv and Unexpected_Changes.csv, using balanced trailing groups. Compare original leaf, logged historical show name and projected show name (case-insensitive group membership, with multiplicity; exact group sequence for historical-to-projection comparison). 364 comparison rows had an original trailing group missing/altered in the projection; 193 were in the unexpected-changes report. Of the 364 rows, 352 already had an original group missing/altered in the historical show name and 12 changed a historical suffix in the projection. These are log rows, not unique performances or verified physical changes. Parenthetical_Review_Build727.csv includes these rows, evidence, and a suggested projection preserving the logged suffix. Historical omissions require review against original media/context, particularly copy/alt/part markers; do not automatically reverse or rename folders using this file.

No original audio media or source test folders were available. No user inventory folders were modified. Build 727 is a source candidate, not a native release or installer. Required source documents have updated version metadata; full rendered visual document QA has not been performed.

Previous Build 726 source and test report: docs/history/Regression_Test_Report_v726.md.
