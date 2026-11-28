# Build 735 source-candidate regression report

TLO v1.7 Build 735 — NOT RELEASE-ATTESTED
Companion GitHub Build Process v169 (unchanged).

GitHub Actions run 46074831272 (Build 734): the Windows MSI was created through WiX, signed successfully through Azure Artifact Signing and then aborted before native installation. PowerShell rejected assignment to its read-only automatic variable HOME. The supplied log ends with exit code 1 and preservation of the failed hosted run. Per-user ICE91 messages were warnings, not the terminating error.

Corrected the case-insensitive collision in msi/Build-TLO-MSI.ps1 and tools/Test-TLO-Windows-Acceptance.ps1. All references to the explicit test/data directory now use unambiguous names, including install command line, configured TLOHome verification and sentinel checks. No native MSI gate is bypassed. WiX signing, direct ownership/hash comparison of four master catalogs, new auxiliary search shortcut, install/uninstall and user-data preservation checks remain mandatory. The existing forced replacement policy for installer-owned payload is unchanged.
Audited other application and companion PowerShell scripts for direct assignments to read-only automatic variables; no additional collisions of this type were found.

Local regression (Python 3.12, pinned pytest 9.1.1): 3173 passed, 39 skipped, 1 deselected, 1 warning, 8 subtests passed in 82.80s (0:01:22).
Focused PowerShell regression: 3 passed, 2 skipped; runtime execution requires native Windows, which is unavailable here. On hosted Windows, the tests require PowerShell and exercise the real smoke-test fixture preparation and opt-in diagnostics without installing the MSI, before actual installer acceptance.
One existing process-pool crash test is deselected due to local UNIX socket restrictions; it remains enabled in GitHub CI. Native GUI, native Windows and other environment-dependent checks may skip locally.
Pinned Ruff 0.16.10, source hygiene and release-readiness checks passed.
Unmodified Build Process v169: 194 passed, 14 skipped in 2.26s.
Current manual, specification, requirements catalog, FAQ and current version references retained from Build 734 and advanced to Build 735. Both documents rendered successfully, and the requirements catalog integrity contract passed.
Build 734 Reverse and documentation cleanup and earlier behavior remain intact. All three supplied SQLite catalogs remain byte-identical. Authoritative ArtistDB-Master staging still supplies venues.txt.
Native Windows MSI signing/install/uninstall, hosted Linux/macOS/Windows CI and signed release acceptance for Build 735: NOT ATTESTED.
