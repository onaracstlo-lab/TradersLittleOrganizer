TLO Source Bundle v746 — SOURCE CANDIDATE / NOT A RUNNABLE DISTRIBUTION
Traders Little Organizer v1.7 Build 746
Native GitHub Build Process: v170

Current functionality
---------------------
Close legacy storage-identity SQLite connections explicitly on success and failure, including test setup. Use the existing read-only catalog opener. Preserve log-owned identity, migration backups and reversal safeguards. Build Process v170 and database masters unchanged.

Make existing inventory and folder-operation logs the storage identity source. Refresh minimal verified disk and partition identifiers on log write opens; migrate legacy JSON/SQLite evidence safely; preserve old logs, separate roots, and reversal safeguards. Build Process v170 and database masters are unchanged.

Retained application changes from earlier builds:
Bound generic ancestor artist evidence to the selected root and prevent explicit dated artist text or existing tags from being replaced by container names; fold accent queries against the Artist DB; report non-Latin unrepresentable artists as unidentified; use the actual rename guard in Dry Run; lock mutating CLI Tag, GUI Tag and duplicate cleanup. Exclude TLO work/held-original directories from Tag Copy and Copy Requests; refuse Copy/Delete when held data is nested; retain duplicate-repair originals with source-relative provenance and log repairs; warn to re-inventory after moves; align home options, safe confirmation defaults, auxiliary search and CLI preview.

Fix native Windows re-inventory metadata backup finalization: finish the ZIP, flush and fsync the writable stream, close it, then atomically publish it. A durability failure still prevents inventory replacement and preserves prior metadata. Build 741 used Process v169; the database masters remain unchanged.

Correct source-owned remediation evidence: match the packaged build number, keep the exact 25 Build 681 review dispositions, and preserve STORAGE736 and RENAME737 in supplemental_findings. Source hygiene now rejects stale identity, invalid/missing dispositions and contaminated finding namespaces. The independent release-readiness gate introduced before Build 741 remains mandatory in Process v170.


Use same-volume retained originals and declared FLAC audio MD5 equality in duplicate repair; improve Artist/City/Venue search, shared read-only home resolution and explicit setlist.fm upgraded-access preference; fail CI startup without Tk; reconcile current documents and archive superseded notes.

The preceding safety iteration resolves the review safety and catalog findings: native Windows PowerShell location, lock-file validation and private recovery locks, sidecar filtering and consistent audio/video roles, read-only UNC-safe catalog access and optional legacy venues.txt at runtime. See the remediation plan for scope and outstanding findings.

Rename Compliantly expands verified alphanumeric Artist DB trading aliases and omits narrow ordinary dotted source/media tails (e.g. rw2c2002-03-24.aud.flac16), preserving the resolved performance name and other identity safeguards.

Manage Storage Identities is available in Main. Registration separates physical disk/partition, inventory folder and logical backup relationship. Numbered log headers contain minimal disk and partition IDs and last-seen observations. The existing folderOperations.log preserves durable registration and reversal history; no active storage JSON or SQLite database is required. Legacy stores are read once for migration and left intact as backups. The root marker remains a fallback and distinguishes folders on the same partition. Re-inventory requires explicit approval at 25% or more previous performances lost/changed; fresh logs and prior metadata snapshots safeguard the previous inventory. Use the GUI, not system commands. See the manual and FAQ.

This source candidate contains TLO inventory, tagging, Add New Shows, Manual Tweaks, copy requests, search, log research, folder reversal and duplicate cleanup. The Main hamburger includes Search (Inventory, Artist, Cities, Venues) and Reverse. Search preloads the clipboard; Reverse uses a single fully qualified Path(s), requires affirmative default-No confirmation, honors Dry Run, and uses the existing locked folder reversal engine. Ordinary Reverse does not restore audio tags or inventory records. See the User Manual for workflow details.

Undated Artist - Album writes the album title only even with Artist In Album Tag checked. Rename Compliantly normalizes the artist/album separator with one space on each side of the dash and preserves other identity information. The date-conflict validator compares distinct dates and only accepts uniquely corroborated performance evidence. Metadata evidence retains full drive, UNC and WSL mount paths. Venue matching preserves historical names and rejects unsafe or ambiguous changes.

The local createWindowsDist.ps1 helper builds eight onefile executables; v170 regenerates the hosted hybrid/shared-onedir distribution script.

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
TLO_Inventory_User_Manual_v746.rtf
TLO_Inventory_Requirements_Working_v746.docx
TLO_Requirements_Catalog_v746.csv
TLO-FAQ.txt
CHANGES_v746.txt
SOURCE_BUNDLE_README_v746.txt
BUILD_VERIFICATION_v746.txt
REGRESSION_RESULTS_v746.txt
RELEASE_NOTES_v746.txt
REMEDIATION_PLAN_v746.md
FINAL_DOCUMENTATION_AUDIT_v746.md
TLO_RELEASE_REMEDIATION.json
CURRENT_STATUS.md
SHA256SUMS_v746.txt
SOURCE.txt
THIRD_PARTY_NOTICES.txt
LICENSE
docs/history/TEST_PLATFORM_OWNERSHIP_v677.md
docs/history/WINDOWS_TEST_REMEDIATION_v677.csv (archival Windows CI incident matrix)
docs/history/WINDOWS_TEST_REMEDIATION_v680.csv (archival Windows CI checklist)

Build and publication
---------------------
Use TLO_GitHub_Build_Process_v170.zip separately. From PowerShell:
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 746 -RepositoryPreflightOnly
  .\Run-TLO-GitHub-Build.ps1 -vnumber 1.7 -bnumber 746

Every successful build is a public pre-release by default; production promotion is manual. Preserve each build ZIP; never overwrite or reuse an earlier build. Full native Windows, Linux and macOS tests, pinned Ruff, build, scan, signing and MSI gates must pass before publication/promotion as applicable. Source Git SSH-signed commit and annotated pre-release tag must be GitHub-verified before source publication. The source tree must not contain bytecode or generated caches. The offline AST audit is not proof of Ruff success.

Data and installation
---------------------
A complete hosted distribution includes the four authoritative reference masters TLOHome/TLO_DBs/artists.sqlite, venues.txt, cities.sqlite and venues.sqlite. This source ZIP includes the three supplied SQLite files; ArtistDB-Master supplies all four at build time, including the legacy venues.txt which is not present in this source. A valid venues.sqlite permits runtime use without venues.txt. Only cities.sqlite is the physical city reference. Runtime never substitutes a database from the executable directory. An alternate TLOHome needs its own references.

Windows MSI directly manages these four database files; user preferences, inventory, logs, setlists and unmanaged TLOHome content are preserved across upgrades/uninstall. Back up customized database files before an upgrade; the installer can replace or remove its own database files. Linux/WSL/macOS use portable ZIPs. Portable overlay updates may leave obsolete artist-only search executables from earlier versions; remove only the obsolete utility after the new searchAuxDBs is installed. Do not remove TLOHome.

Windows acceptance diagnostics
------------------------------
The opt-in tools/Test-TLO-Windows-Acceptance.ps1 checks the explicit TLOHome path and permissions without installing applications or mutating media. The hosted Windows MSI gate performs a signed install/uninstall against disposable fixtures. Both scripts use explicit data-home variables, separate from PowerShell’s built-in read-only HOME.

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
User Manual, FAQ and Requirements describe current operation. Historical changes and results are in CHANGES_v746.txt, SOURCE_BUNDLE_HISTORY.txt and docs/history; the older incident matrices above are retained as evidence, not current acceptance claims. CURRENT_STATUS.md is the current summary. SOURCE.txt points to the corresponding source release tag. SHA256SUMS_v746.txt covers every source member except itself. Local source results never substitute for successful hosted CI, signing or installation acceptance.
