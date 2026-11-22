TLO Source Bundle v717 — SOURCE CANDIDATE / NOT A RUNNABLE DISTRIBUTION
=================================================
Traders Little Organizer v1.7 Build 717
=================================================================
Native GitHub Build Process: v159

Purpose
-------
Build 717 restores the precise, non-attested release verification report fields required by historical tests, after GitHub Actions run 45067649844 failed all three platform test jobs on report assertions. Build Process v159 rejects missing or false verification fields locally, before upload, and on all native jobs. The prior Build 716 bytecode-suppression fix and Build 715 Pygments/Ruff locked-wheel hash fixes remain unchanged; the pip --require-hashes gate is still mandatory. This also retains the Build 714 MSI filename and PowerShell path handoff corrections; already-installed Build 685 binaries still require a manual MSI installation to update.

This source-only candidate bundle contains TLO v1.7 Build 717, its required tests,
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
TLO_Inventory_User_Manual_v717.rtf
TLO_Inventory_Requirements_Working_v717.docx
TLO_Requirements_Catalog_v717.csv
CHANGES_v717.txt
SOURCE_BUNDLE_README_v717.txt
BUILD_VERIFICATION_v717.txt
REGRESSION_RESULTS_v717.txt
SHA256SUMS_v717.txt
SOURCE.txt
THIRD_PARTY_NOTICES.txt
LICENSE
TEST_PLATFORM_OWNERSHIP_v677.md
WINDOWS_TEST_REMEDIATION_v677.csv (historical 71-case Windows CI incident inventory)
WINDOWS_TEST_REMEDIATION_v680.csv (historical 12-case Build 679 Windows CI checklist)
RELEASE_NOTES_v717.txt
REMEDIATION_PLAN_v717.md
TLO_RELEASE_REMEDIATION.json

Build and publication
---------------------
Use TLO_GitHub_Build_Process_v159.zip separately. The companion is GitHub Build Process v159. From PowerShell:
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 717 -RepositoryPreflightOnly
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 717

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
changes are retained in CHANGES_v717.txt and docs/history, not interleaved into
the current operating instructions. SOURCE.txt identifies the corresponding
source release tag. The package's SHA256 manifest covers all members except
itself. Source/database integrity must be validated during release assembly.

Build 717 recovery/preview examples:
  python tlo-gi.py --TLOHome <home> --search-path <folder> --dry-run
  python tlo-reverse.py --TLOHome <home> --manual-updates --batch 2 --dry-run
  python tlo-reverse.py --TLOHome <home> --manual-updates --batch 2
Read REMEDIATION_PLAN_v717.md before selecting a batch; no intervening untracked catalog edits can be merged automatically.
For Win11 non-admin acceptance: tools/Test-TLO-Windows-Acceptance.ps1.

Current Windows stage recovery uses safe Win32 process checks. Historical Build 692: L6 explicit recovery for journaled interrupted same-volume staged moves. All prior fixes through Build 691 retained; remaining findings tracked in REMEDIATION_PLAN_v717.md. Native hosted success is not asserted.

Release source/test import audit:
  python tools/audit_unused_imports.py --root .
Native Ruff preflight (mandatory, source AND tests):
  python -m ruff check .
The offline AST audit is not proof of Ruff success. Do not publish until native lint completes.

Source database staging
-----------------------
This ZIP has a zero-byte TLO_DBs/artists.sqlite placeholder and may omit
TLO_DBs/venues.txt. It is not a self-contained runnable installation.
The build process injects the real artists.sqlite, venues.txt and cities.csv
from the configured ArtistDB-Master at build time. The root cities.csv is a
build input; TLO_DBs/cities.csv is the staged runtime copy. For source
smoke tests, provide a test fixture DB and reference data in TLOHome/TLO_DBs.
Never interpret local source tests as signing/MSI or native acceptance.

Current short entry point: CURRENT_STATUS.md. History: docs/history/.

Build 717 preflight hygiene: Python -B for source-stage verifier, and verify_build_lock.py disables .pyc creation before importing tlo_version. The original input ZIP is still rejected if compiled artifacts are present; no validation is bypassed.

Build 717: exact historical verification-report format restored to prevent the Build 716 hosted CI report-only failures. Build Process v159 blocks report-contract regressions before native build work.
