TLO Source Bundle v685 — Traders Little Organizer v1.7 Build 685
=================================================================
Native GitHub Build Process: v143

Purpose
-------
This complete source bundle contains TLO v1.7 Build 685, its required tests,
reference data, the current Requirements, User Manual, and checksum manifest.
No GitHub Build Process artifact is included in this source bundle.
The build process is independently versioned and distributed as its own separate package.

Entry points
------------
tlo-main.py: Main GUI.
tlo-search.py: collection search.
tlo-gi.py: inventory CLI.
tlo-tag.py: audio tagger CLI.
tlo-deleteDupes.py: duplicate-folder review/cleanup.

Current release files
---------------------
TLO_Inventory_User_Manual_v685.rtf
TLO_Inventory_Requirements_Working_v685.docx
TLO_Requirements_Catalog_v685.csv
CHANGES_v685.txt
SOURCE_BUNDLE_README_v685.txt
BUILD_VERIFICATION_v685.txt
REGRESSION_RESULTS_v685.txt
SHA256SUMS_v685.txt
SOURCE.txt
THIRD_PARTY_NOTICES.txt
LICENSE
TEST_PLATFORM_OWNERSHIP_v677.md
WINDOWS_TEST_REMEDIATION_v677.csv (historical 71-case Windows CI incident inventory)
WINDOWS_TEST_REMEDIATION_v680.csv (historical 12-case Build 679 Windows CI checklist)
RELEASE_NOTES_v685.txt
REMEDIATION_PLAN_v685.md
TLO_RELEASE_REMEDIATION.json

Build and publication
---------------------
Use TLO_GitHub_Build_Process_v143.zip separately. The companion is GitHub Build Process v143. From PowerShell:
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 685 -RepositoryPreflightOnly
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 685

Every successful build is a public pre-release by default; promotion to the
production release is a separate manual operation. Preserve every prior ZIP;
never overwrite or reuse an earlier build number.

For the native release, locally tested source alone is NOT sufficient: Windows
and macOS jobs, signing, MSI and release integrity gates must all pass. The
71 historical Build 675 Windows failures are accounted for in the included
remediation matrix, with hosted Windows acceptance still pending.

Data and upgrades
-----------------
TLOHome user preferences, inventory, logs and setlists are preserved across
MSI upgrades and uninstall. TLOHome/TLO_DBs is installer-managed; master
artists.sqlite, venues.txt and cities.csv may be replaced by installer updates.

Documentation policy
--------------------
The User Manual and Requirements describe CURRENT operation. Detailed prior
changes are retained in CHANGES_v685.txt and docs/history, not interleaved into
the current operating instructions. SOURCE.txt identifies the corresponding
source release tag. The package's SHA256 manifest covers all members except
itself. Source/database integrity must be validated during release assembly.

Build 685: source-only lint correction: removed two unused imports from the Build 683
rename/search/parallel regression tests (Ruff F401). No runtime behavior changes.
Build 683 retains non-lossy Rename Compliantly, Search View identity and parsing,
and conservative worker-crash recovery. Read
TLO_RELEASE_REMEDIATION.json for intentionally deferred review findings. The
Build 682 integrity/Reverse improvements remain part of this complete source.
No native hosted release success is asserted.
