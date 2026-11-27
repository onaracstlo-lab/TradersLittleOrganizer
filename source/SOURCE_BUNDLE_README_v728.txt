TLO Source Bundle v728 — SOURCE CANDIDATE / NOT A RUNNABLE DISTRIBUTION
Build 723: Add New Shows displays current folder, progress and action counts and automatically opens pending duplicate/upgrade review after processing (user can Quit and resume later). The reusable Windows deleteReplacedFolders.bat intentionally uses permanent rmdir /s /q after the exact current volume-label and reparse-point checks; no undo mechanism is generated. Immediate GUI Delete New/Keep Old still requests Recycle Bin.

Prior release context (retained): Build 728 retains the Build 720 Ruff correction and Build 719 venue/city capitalization. Process v165 hardens Windows public Git source publication.
=================================================
Traders Little Organizer v1.7 Build 728
=================================================================
Native GitHub Build Process: v168

Purpose
-------
Keep original trailing recording parentheticals, including (early), (late), (mtx), and (24). Do not append a redundant canonical performance qualifier when an equivalent complete original parenthetical is present. Refuse compliant folder renames that would discard, alter, or reorder any ordinary trailing group; retain existing collision/part and identity validation. Correct the historical projection to restore the original folder suffix, not the incomplete historical show name. Retain consecutive and nested trailing parenthetical recording qualifiers during parsing and venue matching. Apply venue/city display substitutions only to the name core, not the qualifier text. Match venue-only paths without treating the suffix as part of the venue. Keep existing missing/ambiguous catalog fallbacks, copy/alt verification, and historical venue protections. Recognize complete, context-supported venue names using read-only venues.sqlite; preserve historical names, unknown venues, legacy venues.txt and existing positional, setlist and online fallbacks. Reject ambiguous, partial and unsafe display changes. Do not modernize historical venue names. The four physical reference masters are artists.sqlite, venues.txt, cities.sqlite and venues.sqlite.

Build 726 integrated the external read-only SQLite matcher with the existing city parser, and retains the Windows Recycle Bin default-settings fix for immediate Delete New, and restores guarded permanent rmdir in the manually run Windows old-duplicate cleanup batch template. All prior Git publication hardening is retained. The earlier Build 719 correction handles uppercase fragments in mixed-case path-only names while retaining raw source evidence. Build 717 restored non-attested release verification report contracts following GitHub Actions run 45067649844. Build Process v159 (retained in v168) rejects missing or false verification fields locally, before upload, and on all native jobs. The prior Build 716 bytecode-suppression fix and Build 715 Pygments/Ruff locked-wheel hash fixes remain unchanged; the pip --require-hashes gate is still mandatory. This also retains the Build 714 MSI filename and PowerShell path handoff corrections; already-installed Build 685 binaries still require a manual MSI installation to update.

This source-only candidate bundle contains TLO v1.7 Build 728, its required tests,
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
TLO_Inventory_User_Manual_v728.rtf
TLO_Inventory_Requirements_Working_v728.docx
TLO_Requirements_Catalog_v728.csv
CHANGES_v728.txt
SOURCE_BUNDLE_README_v728.txt
BUILD_VERIFICATION_v728.txt
REGRESSION_RESULTS_v728.txt
SHA256SUMS_v728.txt
SOURCE.txt
THIRD_PARTY_NOTICES.txt
LICENSE
TEST_PLATFORM_OWNERSHIP_v677.md
WINDOWS_TEST_REMEDIATION_v677.csv (historical 71-case Windows CI incident inventory)
WINDOWS_TEST_REMEDIATION_v680.csv (historical 12-case Build 679 Windows CI checklist)
RELEASE_NOTES_v728.txt
REMEDIATION_PLAN_v728.md
TLO_RELEASE_REMEDIATION.json

Build and publication
---------------------
Use TLO_GitHub_Build_Process_v168.zip separately. The companion is GitHub Build Process v168. From PowerShell:
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 728 -RepositoryPreflightOnly
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 728

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
artists.sqlite, venues.txt, cities.sqlite and venues.sqlite may be replaced by installer updates.

Documentation policy
--------------------
The User Manual and Requirements describe CURRENT operation. Detailed prior
changes are retained in CHANGES_v728.txt and docs/history, not interleaved into
the current operating instructions. SOURCE.txt identifies the corresponding
source release tag. The package's SHA256 manifest covers all members except
itself. Source/database integrity must be validated during release assembly.

Current recovery/preview examples:
  python tlo-gi.py --TLOHome <home> --search-path <folder> --dry-run
  python tlo-reverse.py --TLOHome <home> --manual-updates --batch 2 --dry-run
  python tlo-reverse.py --TLOHome <home> --manual-updates --batch 2
Read REMEDIATION_PLAN_v728.md before selecting a batch; no intervening untracked catalog edits can be merged automatically.
For Win11 non-admin acceptance: tools/Test-TLO-Windows-Acceptance.ps1.

Current Windows stage recovery uses safe Win32 process checks. Historical Build 692: L6 explicit recovery for journaled interrupted same-volume staged moves. All prior fixes through Build 691 retained; remaining findings tracked in REMEDIATION_PLAN_v728.md. Native hosted success is not asserted.

Release source/test import audit:
  python tools/audit_unused_imports.py --root .
Native Ruff preflight (mandatory, source AND tests):
  python -m ruff check .
The offline AST audit is not proof of Ruff success. Do not publish until native lint completes.

Source database staging
-----------------------
This ZIP has a zero-byte TLO_DBs/artists.sqlite placeholder and may omit
TLO_DBs/venues.txt. It is not a self-contained runnable installation.
The build process injects the real artists.sqlite, venues.txt, cities.sqlite and venues.sqlite
from the configured ArtistDB-Master at build time. Only TLO_DBs/cities.sqlite
is the physical city runtime master. Obsolete city CSV files are ignored. Use an MSI or database-inclusive ZIP for the first upgrade from a CSV-only installation. For source
smoke tests, provide a test fixture DB and reference data in TLOHome/TLO_DBs.
Never interpret local source tests as signing/MSI or native acceptance.

Current short entry point: CURRENT_STATUS.md. History: docs/history/.

Retained source preflight hygiene: Python -B for source-stage verifier, and verify_build_lock.py disables .pyc creation before importing tlo_version. The original input ZIP is still rejected if compiled artifacts are present; no validation is bypassed.

Retained Build 717 change: exact historical verification-report format restored to prevent the Build 716 hosted CI report-only failures. Build Process v165 retains the preflight before native build work.

Retained earlier place-name formatting: fully uppercase recognized VENUE/CITY metadata is displayed in normal readable capitalization in show names, bootlist, new setlists and audio tags. Mixed-case spellings, known initials, artist names, path source and original setlist text are preserved.

For an already inventoried show, the new casing applies on a subsequent inventory/update processing pass. Build 728 does not silently rename existing folders or rewrite original setlist files as part of installation.

Retained earlier lint-only fix: unused local wholly_upper removed from tlo_place_display.py; no intended behavioral changes.

Build 728 / Process v168: Package source contains application source and tests; process package supplies protected public Git publication. After local artifact verification and successful native signing/CI, source repository must contain a GitHub-verified SSH-signed commit and GitHub-verified annotated pre-release tag before asset publication. No gate is bypassed for Windows Git object write failures.
