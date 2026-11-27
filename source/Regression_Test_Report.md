# Build 728 source-candidate regression report

## Correction to Build 727's historical review
The earlier Parenthetical_Review_Build727.csv wrongly used the historical show-name suffix as the basis for its suggested projection, although the historical show name already omitted original qualifiers in many rows. That report must not be used to determine a restored folder name. Parenthetical_Review_Build728.csv supersedes it: the suggested projection explicitly uses every complete trailing group from the ORIGINAL folder, preserving order and wording. All 364 suggestions were mechanically checked against the original suffix. For unresolved rows it keeps the original folder intact. The historical suffix and any historical-only groups remain separately visible. This is an advisory comparison, not a set of rename commands.

## Path fixture replay of all 364 affected rows
The real Build 728 metadata extractor was exercised with all 364 original folder names and recorded compliant/non-compliant mode, the packaged cities/venues databases, an isolated artist matcher seeded from the logged artist, and temporary directories without original media/setlists or online access. The 364 are comparison rows, not necessarily unique performances; 193 are in the previous unexpected-changes report.

- 358 produced a resolved show name; none lost ordinary source qualifiers.
- Six did not resolve a show name (five rows for the same Graham Parker collaborative performance without a logged artist, and one malformed Los Lobos name). The source qualifiers were still captured; the suggested and guarded folder names retain the original.
- 154 resolved rows contained a copy marker that was classified as an alt marker in the isolated fixture. This is expected when no matching sibling is available; the actual audio trees must be checked under the existing duplicate rules. The advisory suggested projection keeps the original copy marker.
- The corrected CSV distinguishes the historical projection (original suffix restored), actual path-fixture show name, and the conservative guarded folder-name preview using the tagger's filename sanitizer. The guard preview alone is not a physical rename (it does not include collision allocation, selected options, or actual media). It permits a different name in 83 of these isolated rows.
- The six exact user-reported source names retain all original qualifiers; their logged mode is compliant. All six were also tested in both modes with and without the catalog, including actual temporary Add Shows folder renames or intentional refusals to rename.

## Additional runtime protection
Build 727's non-compliant mode could display both (Late Show) and (late), or both (Early Show) and (early), from a single source qualifier. Build 728 suppresses only the redundant canonical addition when a complete recognized equivalent source group exists. Independently derived qualifiers and free-form notes remain supported. The final compliant rename safety guard now explicitly verifies presence and order of complete ordinary trailing groups, including nested groups and repetition, rather than relying on a set of source words. Existing structural marker, numeric, source-word, date, and collision guards remain in place. A rejected name leaves the original folder untouched.

## Tests executed
- 81 targeted tests passed: 29 new cases, 45 retained venue/suffix tests, and 7 retained artist-performance-qualifier tests.
- Exact paired comparisons of the original Build 727 source and Build 728 candidate: 28 targeted cases; 8 changed (4 eliminate a redundant qualifier; 4 reject unsafe proposed folder names), 20 unchanged. Separate Test_Folder_Name_Changes_v728.csv lists all 8, including explicit test kind and mode/catalog.
- Final full local application suite: 3,089 passed, 37 skipped, 1 failed, 2 warnings in 61.07s. Sole failure: test_build683_rename_search_parallel.py::test_process_pool_crash_retains_completed_groups. Same failure reproduced in exact original Build 726 and 727 under the restricted environment (multiprocessing.Manager AF_UNIX socket denied, PermissionError then EOFError); native gate remains required. No prior expectation weakened.
- Source hygiene and package hash verification: passed. No native CI/signing, installer, pinned Ruff/Python, or full rendered documentation QA claimed. Requirements specification/version metadata updated without layout changes; existing normative rule already requires original parenthetical preservation. Build Process v168 unchanged.

Original media and actual test folders remain unavailable. No user files or folders have been renamed. This is a tested source candidate, not a published release.
