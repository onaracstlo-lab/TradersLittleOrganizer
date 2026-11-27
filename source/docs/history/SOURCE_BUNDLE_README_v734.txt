TLO Source Bundle v734 — SOURCE CANDIDATE / NOT A RUNNABLE DISTRIBUTION
Traders Little Organizer v1.7 Build 734
Native GitHub Build Process: v169

Current functionality
---------------------
This source candidate contains TLO inventory, tagging, Add New Shows, Manual Tweaks, copy requests, search, log research, folder reversal and duplicate cleanup. The Main hamburger includes Search (Inventory, Artist, Cities, Venues) and Reverse. Search preloads the clipboard; Reverse uses a single fully qualified Path(s), requires affirmative default-No confirmation, honors Dry Run, and uses the existing locked folder reversal engine. Ordinary Reverse does not restore audio tags or inventory records. See the User Manual for workflow details.

Undated Artist - Album writes the album title only even with Artist In Album Tag checked. Rename Compliantly normalizes the artist/album separator with one space on each side of the dash and preserves other identity information. The date-conflict validator compares distinct dates and only accepts uniquely corroborated performance evidence. Metadata evidence retains full drive, UNC and WSL mount paths. Venue matching preserves historical names and rejects unsafe or ambiguous changes.

No GitHub Build Process artifact is included in this source bundle.
The build process is independently versioned and distributed as its own separate package.

Entry points
------------
tlo-main.py: Main GUI.
tlo-search.py: collection search.
searchAuxDBs.py: read-only Artist, City, or Venue catalog search.
tlo-gi.py: inventory CLI.
tlo-tag.py: audio tagger CLI.
tlo-research.py: metadata log research.
tlo-reverse.py: folder reversal, Manual Tweaks undo, and interrupted staging recovery CLI.
tlo-deleteDupes.py: duplicate-folder review/cleanup.

Current release files
---------------------
TLO_Inventory_User_Manual_v734.rtf
TLO_Inventory_Requirements_Working_v734.docx
TLO_Requirements_Catalog_v734.csv
TLO-FAQ.txt
CHANGES_v734.txt
SOURCE_BUNDLE_README_v734.txt
BUILD_VERIFICATION_v734.txt
REGRESSION_RESULTS_v734.txt
RELEASE_NOTES_v734.txt
REMEDIATION_PLAN_v734.md
FINAL_DOCUMENTATION_AUDIT_v734.md
TLO_RELEASE_REMEDIATION.json
CURRENT_STATUS.md
SHA256SUMS_v734.txt
SOURCE.txt
THIRD_PARTY_NOTICES.txt
LICENSE
TEST_PLATFORM_OWNERSHIP_v677.md
WINDOWS_TEST_REMEDIATION_v677.csv (archival Windows CI incident matrix)
WINDOWS_TEST_REMEDIATION_v680.csv (archival Windows CI checklist)

Build and publication
---------------------
Use TLO_GitHub_Build_Process_v169.zip separately. From PowerShell:
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 734 -RepositoryPreflightOnly
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 734

Every successful build is a public pre-release by default; production promotion is manual. Preserve each build ZIP; never overwrite or reuse an earlier build. Full native Windows, Linux and macOS tests, pinned Ruff, build, scan, signing and MSI gates must pass before publication/promotion as applicable. Source Git SSH-signed commit and annotated pre-release tag must be GitHub-verified before source publication. The source tree must not contain bytecode or generated caches. The offline AST audit is not proof of Ruff success.

Data and installation
---------------------
A complete installation requires the four authoritative reference masters TLOHome/TLO_DBs/artists.sqlite, venues.txt, cities.sqlite and venues.sqlite. This source ZIP includes the three supplied SQLite files; ArtistDB-Master supplies all four at build time, including the legacy venues.txt which is not present in this source. Only cities.sqlite is the physical city reference. Runtime never substitutes a database from the executable directory. An alternate TLOHome needs its own references.

Windows MSI directly manages these four database files; user preferences, inventory, logs, setlists and unmanaged TLOHome content are preserved across upgrades/uninstall. Back up customized database files before an upgrade; the installer can replace or remove its own database files. Linux/WSL/macOS use portable ZIPs. Portable overlay updates may leave obsolete artist-only search executables from earlier versions; remove only the obsolete utility after the new searchAuxDBs is installed. Do not remove TLOHome.

Safe operations
---------------
Ordinary Reverse and Manual Tweaks undo are separate. Preview using Main Dry Run or CLI --dry-run. The confirmed Reverse preview writes an audit record to TLOHome/logs/reverseFolders.log but never changes folders or tags. Manual Tweaks undo uses original tag values and catalog/setlist journals, not media-copy backups. The Windows deleteReplacedFolders.bat deferred old-folder cleanup template runs permanent rmdir /s /q after safe-target/volume-label verification; it has no undo. Immediate GUI Delete New/Keep Old requests the Recycle Bin.

Examples:
  python tlo-gi.py --TLOHome <home> --search-path <folder> --dry-run
  python tlo-reverse.py <folder> --TLOHome <home> --dry-run
  python tlo-reverse.py --TLOHome <home> --manual-updates --batch 2 --dry-run
  python tlo-reverse.py --TLOHome <home> --manual-updates --batch 2
  python -m ruff check .

Documentation and evidence
--------------------------
User Manual, FAQ and Requirements describe current operation. Historical changes and results are in CHANGES_v734.txt, SOURCE_BUNDLE_HISTORY.txt and docs/history; the older incident matrices above are retained as evidence, not current acceptance claims. CURRENT_STATUS.md is the current summary. SOURCE.txt points to the corresponding source release tag. SHA256SUMS_v734.txt covers every source member except itself. Local source results never substitute for successful hosted CI, signing or installation acceptance.
