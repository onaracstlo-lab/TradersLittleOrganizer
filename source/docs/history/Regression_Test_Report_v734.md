# Build 734 source-candidate regression report

TLO v1.7 Build 734 — NOT RELEASE-ATTESTED
Companion GitHub Build Process v169 (unchanged).

Local application regression (Python 3.12, pinned pytest 9.1.1): 3170 passed, 37 skipped, 1 deselected, 1 warning, 8 subtests passed in 85.75s (0:01:25).
One existing process-pool crash test was deselected because the local environment prevents required UNIX socket creation; it remains enabled in GitHub CI. The skipped tests include native Windows, graphical Tk and FLAC encoder tests. The real-GUI menu test remains enabled when a display is available.
Focused Reverse behavior: 15 passed, including negative or closed confirmation, actual restoration, preview/audit, invalid input, quoted literal paths, concurrent-operation and shutdown guards.
Documentation contract: 2 passed; catalog checks use the standard-library XML parser without adding a runtime dependency.
Pinned Ruff 0.16.10: all checks passed. Source hygiene and companion release-readiness checks passed.
Unmodified GitHub Build Process v169: 194 passed, 14 skipped in 2.29s.

The user manual (39 rendered pages) and requirements specification (114 rendered pages) were converted to PDF for visual checking; changed sections were inspected. The 1,078 stable catalog records were retained, including 732 repaired paragraph references, 23 synchronized paragraph texts, 293 verified table rows and 24 revised supplemental locator labels.
The three supplied SQLite catalogs remain byte-identical. The authoritative legacy venues.txt master is not supplied in the source ZIP; the normal ArtistDB-Master staging remains required.
No hosted GitHub Actions acceptance, native platform packaging, MSI installation/upgrade/uninstall, scan or signing acceptance is claimed for Build 734.
