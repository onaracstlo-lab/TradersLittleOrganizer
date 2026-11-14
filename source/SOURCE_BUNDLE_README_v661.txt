Traders Little Organizer (TLO) - Source and Utilities Bundle v661
==================================================================
Public application version: v1.7 Build 661
Native GitHub Build Process: v133 (separate complete package)

CURRENT RELEASE
---------------
Build 661: Correct WiX 6 TARGETDIR virtual-symbol conflict in MSI generation; leave the MSI TLOHome selection and HKCU settings unchanged. Fix Main/Search menu regression test to check labels regardless of menu order. Remove stale Build 659 verification/results reports accidentally shipped in Build 660. Linux Build 660: 2 failed, 2,556 passed, 26 skipped; Windows signed executables and scanners passed, MSI WiX compilation failed with WIX7009. GitHub Build Process v133 unchanged. Native MSI validation still required.

Build 660: MSI setup chooses a TLOHome data folder (default C:\.tlo), persists per-user TLOHome, and keeps executables under LocalAppData. On the first launch after an MSI upgrade, replaces installer-managed master database files in TLOHome\TLO_DBs; never overwrites user preferences, logs, inventory or setlists. Open TLO Folder added to Main and Search. Existing folders take precedence. Prior release ZIPs unchanged; GitHub Build Process v130 unchanged.

Build 659: Correct missing verification-report literal contracts that failed 3 of 2,573 Linux CI tests in Build 658 (3 failed, 2,544 passed, 26 skipped). Restore "lint not attested" and "full GitHub Actions run" while accurately reporting mandatory release gates as NOT ATTESTED.
No changes to application runtime, MSI generator, signing, or auto-update behavior; Build Process v130 unchanged. Build 658 ZIP remains preserved.

Build 658: Add MSI ICE64-compliant uninstall entries for every installer-owned per-user directory. Build 657 hosted Windows build generated valid WiX source but failed MSI ICE validation because three intermediate directories lacked removal entries.
Build Process v130 is unchanged; signed MSI and portable ZIP update paths remain separate, with TLOHome preserved.
This is a NEW build, not a replacement for Build 657.

Build 657: Correct WiX source creation of nested Windows-onedir folders (KeyError THIRD_PARTY), with regression coverage.
Build 656: Remove unused MSI regression-test import that fails Ruff F401.
MSI update identity and TLO runtime unaffected; use Build Process v130.
This is a new numbered source release, not a reissue of Build 656.

Build 655: Add Windows MSI installation and signed MSI automatic-update handoff
while preserving the ZIP update path for portable installations.

Build 654: Full Inventory and supporting tools accept Windows UNC share paths
without drive mapping. Persist the network share as UNC:server/share and the
folder path relative to it; Copy Requests reconstruct the share path and
Manual Updates match share-scoped identities. See CHANGES_v661.txt.

Build 653: Main and Search update checks enforce the GitHub production-release
approval gate. Normal v126 builds produce public pre-releases, which are not
shown in the updater until manually promoted. Previously published full releases
remain intact; GitHub Latest is the only moving selection. Existing signed ZIP
verification and download-only behavior are unchanged.

Build 652 (historical): Remove an unused function-local zipfile import in the legacy tests that blocked the mandatory Ruff F401 gate. No production behavior changes; retain the Build 651 TLOHome setup improvements. Build Process v125 is unchanged.

Build 651: Missing TLOHome setup now provides complete, copyable Windows and Linux/WSL startup commands, Windows shortcut Target instructions, an environment-variable option and the installation website. Main and Search show a copyable GUI setup dialog and stop startup when TLOHome is missing; CLI tools receive the same actionable guidance. Build Process v125 is unchanged.

Build 650: The current consolidated specification is delivered in every signed complete and update release together with the matching RTF User Manual and current CHANGES file. Historical change narratives are consolidated in CHANGES_v652.txt; the old-change-logs.zip archive is no longer distributed. Build Process v125 requires exactly these current three documents in source, complete and update releases, and includes them in SHA-256 package manifests. Runtime behavior is unchanged from Build 649.

Build 649: Verify the whole independently signed ZIP (pinned key and SHA-256) and its safety/identity; do not hard-code a database master filename inventory inside the downloader. Build Process v124 remains responsible for ensuring all three physical TLO_DBs masters (including cities.csv) are present in full and database-inclusive updates. The update should INCLUDE databases; do not use the database-free bridge for old installations that lack cities.csv. Older installed updaters such as Build 591 cannot be retrofitted; use a trusted manual installation as needed. See TLO_UPDATE_MIGRATION_v649.txt.

Build 648: Update package database compatibility and migration. Verify old releases with artists.sqlite + venues.txt and newer releases with artists.sqlite + venues.txt + cities.csv according to downloaded package build/manifest; never trust undeclared or extra database members. Database-free update ZIPs preserve TLO_DBs and provide a bridge for old installed updaters. For legacy clients: use a signed Build 648 database-free update (Build Process v124, leave -IncludeDatabasesInUpdates OFF), then a higher build containing all three databases, or manually install a trusted signed official complete release. Updating source code does not retrofit old Build 591's validator. Signing/native CI are mandatory. See TLO_UPDATE_MIGRATION_v649.txt.

Build 647: New numbered release for the Ruff F401 correction in the city-database staging tests. All Build 646 runtime/city recognition and file-layout semantics are preserved. Use GitHub Build Process v124, which adds cities.csv alongside artists.sqlite and venues.txt in the release/update build workflow. The source bundle includes the three-file staging checks; native builds, Ruff and signing remain release gates.

Build 646: City reference is physically TLO_DBs/cities.csv, just like TLO_DBs/artists.sqlite and TLO_DBs/venues.txt. The embedded Python city catalog introduced in Build 645 is now completely removed. Do not embed cities.csv into PyInstaller executables. Complete and database-inclusive update packages MUST include all three files and declare them in database_files; build verification will fail for missing/mismatched city data. The separately supplied GitHub Build Process v124 stages/validates the three database files. Release signing/native CI still required.

Build 645 (superseded by 646): The embedded city fallback has been removed at user request. It is not present in Build 646 sources or native executable data options.

Build 643: Use Keep/Never for missing corruption options without altering explicit Delete requests; detect stale preference file edits and single-instance editors per process; exclude recoverably held SHNs from Tag Copy and Copy Requests at every nesting depth while keeping transfer checks consistent; store held originals under unique subfolders retaining original filenames; add read-only held-original report and non-security MD5 compatibility.
Native Windows/macOS/Linux builds and signing not attested.

Build 642: Restore 35 carefully selected ambiguous touring-city names without guessing country; safely layer user additions over the bundled CSV; individually reject malformed and conflicting records; remove per-show CSV sniffing and cache drift; prevent city/artist first-name confusion and hyphen-as-delimiter mistakes. Keep folder alias spellings.
Native Windows/macOS/Linux builds and signing not attested.

Build 641: Remove two unused imports blocking Ruff; report update no-overwrite rename filesystem incompatibility without unsafe fallback; restore city metadata source attribution in conflicting setlist observations; add mandatory local source release-gate runner and harden test collection/subprocess isolation.
Native Windows/macOS/Linux builds and signing not attested.

Build 640: Conservative city and alias recognition. The curated
conventional comma CSV is part of the source and frozen executables. Shared
lookup indexes canonical names and aliases together and preserves the exact
spelling from the original folder in metadata/show names (subject only to
TLO's existing ASCII output normalization). City-name matches must not
replace Artist DB identities, venue data, explicit regions/countries, or
other established geographic fields. Missing or invalid optional local city
CSV files fail closed. Legacy caret-separated overrides remain supported.
See CHANGES_v644.txt and the regression log for the tested cases and limits.
GitHub Build Process v123 remains unchanged; native signing is pending.

Build 639: Enable native-Windows Explorer drag/drop in the Tag Copy and Tag
Copy/Delete Original Destination of Copies prompt. All other GUI path text
entries were audited; they already had drop targets. Folder drops continue
to use the current destination-validation logic. The build process v123 is
unchanged; native platform verification and signing are pending.

Build 638: Single startup preferences file and restart-only editing.
Startup Profiles has been completely removed from Main, together with its
preset application module. Main and Search load TLOHome/tlo-preferences.ini
at startup. Edit Preferences offers Save & Close and Cancel. A valid Save &
Close writes the INI atomically and closes the window, but does not update
any live GUI setting, selected option, path, font or active operation.
Restart Main and Search to use changed defaults. Cancel never saves.
The Build 634 live-font feature and Build 635 profiles are superseded.
GitHub Build Process v123 remains unchanged; hosted gates pending.

Build 637: Simplified duplicate identification, rename-only updates, SHN recovery.
The duplicate-cleanup tool compares recursive relative file names, exact byte
sizes and folder structure; it no longer hashes or reads candidate file contents.
Files of equal name/size are treated as duplicates even if content differs.
This explicitly supersedes Build 625's duplicate-move hash gate. FLAC corruption
repair remains independent, and all transfer/update integrity gates are unchanged.

After signed-asset verification and package inspection, update downloads are
published by an atomic same-directory no-overwrite rename rather than a hard
link. A conflicting existing Downloads file is never replaced. The update is
never installed or unzipped by the checker.

Convert shn continues to verify full decoded PCM equivalence. If native Trash
fails, the verified source is renamed without copying or deleting into
<source-directory>/.tlo-shn-originals/track.shn.<unique-id> on the same volume.
This folder is excluded from TLO traversal; its original remains recoverable.
If both methods fail, the newly created FLAC is rolled back while the original
SHN is retained. No fallback is used for ordinary corrupt-file removal.
GitHub Build Process v123 is unchanged; hosted native/signing gates pending.

Build 636: Windows-safe source ZIP and Ruff preflight correction.
Removed unused source names and an invalid Windows ZIP entry.

Build 635: Preview-first nondestructive startup profiles.
Main offers small preview-first startup profiles for cataloging, tagging in place and manually configured ingest/move. Profiles require confirmation, and none silently enables deletion, conversion or a destructive transfer.

Build 634: Apply safe cosmetic preferences live.
Validated edits can update cosmetic fonts in Main and Search without resetting operational controls. Restart remains required for structural, search and destructive-mode changes; invalid values are rejected.

Build 633: CLI compatibility aliases and opt-in clipboard.
Main, Search and Tag accept --tlo-home alongside --TLOHome; --tag-move-to aliases the existing destination-taking copy/delete argument. Search clipboard prefill is opt-in for new installations.

Build 632: Trusted process checks and cross-process settings.
Copy Requests uses an absolute trusted ps path. Run-settings entries use an operating-system advisory lock across processes. etreeDB User-Agent reflects the current version. No log rotation is introduced.

Build 631: Recoverable XDG Trash when gio is absent.
On Linux without gio, a private same-filesystem XDG Trash location stores recoverable originals with collision-safe metadata. Failures or unavailable Trash preserve originals; no hard-delete fallback is permitted.

Build 630: Safe corruption defaults for new installations.
New installations default to Keep and report for corrupt files and Never remove folders. Existing preferences and explicit deletion choices remain unchanged. Tagging and Deep Audio controls retain their semantics.

Build 629: Headless preferences and frozen parsing regression corpus.
Preference parsing and validation import without Tk. Test collection detects GUI imports instead of relying on a stale filename list. A frozen folder-name corpus guards artist, city and ambiguous-date behavior.

Build 628: Consistent INI syntax and Auto Update writes.
Preferences accept both = and : assignments, preserve inline comments and unknown user text during validated atomic saves, and keep the Auto Update toggle consistent with grammar accepted by the editor.

Build 627: Per-item POSIX cleanup volume verification.
Generated POSIX cleanup scripts skip and report each wrong or unverifiable volume instead of aborting the entire list. They continue to later valid entries, preserve existing label safeguards and report deleted/skipped counts.

Build 626: Transactional update-package validation.
A downloaded update must pass signed-asset size/hash checks and archive inspection while staged under a non-release filename. Only a validated file may receive its official Downloads name. An unrelated same-named user file is never overwritten. Failure removes the staged file.

Build 625: Verified duplicate file identity.
The duplicate cleanup utility must verify matching directory structure and SHA-256 bytes for every regular file (including FLAC, SHN, MP3 and WAV) immediately before a duplicate is moved. It rejects symlinks, unreadable files and files modified during comparison. Coarse size-based matching can identify candidates but never authorize a destructive move.

Build 624 is a documentation-only consolidation of Builds 622 and 623.
The application behavior is identical to Build 623.

Build 623: SHN conversion now requests strict FFmpeg decoding (-xerror),
verifies the complete source and destination decoded 32-bit PCM MD5 and
byte/sample counts, and moves a verified SHN original to native Trash.
Failures preserve the original; an unverified FLAC is not published.

Build 622: Artist, City Date parsing requires positive city-reference evidence
(built-in reference or TLOHome/TLO_DBs/cities.csv). Capitalized recording
terms such as Soundboard, Matrix, Rehearsals, and Bootleg cannot become cities
by capitalization alone. Inverted artist aliases such as Kinks, The are
protected. Jethro Tull, Derby 2007-02-04 remains supported.

Build 621: for explicit comma-delimited artist/city dates, selected-setlist
evidence and enabled etreeDB/setlist.fm services can uniquely corroborate
ambiguous numeric dates without guessing. All existing path/date safety
conditions remain in force.

BUILD CONTENTS
--------------
- tlo-main.py: Main GUI.
- tlo-gi.py   : inventory CLI
- tlo-search.py: collection search.
- tlo-tag.py : tagging CLI
- tlo-research.py : inventory research
- tlo-deleteDupes.py : duplicate cleanup
- Additional scripts, source modules, tests and build recipes in the ZIP root.
- TLO_Inventory_User_Manual_v653.rtf : end-user instructions
- TLO_Inventory_Requirements_Working_v653.docx : current specification
- TLO-FAQ.txt : support answers
- tlo-preferences.ini : default startup configuration (never overwrite
  an existing TLOHome configuration)
- CHANGES_v653.txt : current release and consolidated change history
- REGRESSION_RESULTS_v653.txt and BUILD_VERIFICATION_v653.txt : local checks
- SHA256SUMS_v653.txt : hashes of all other files in this source ZIP
- CHANGES_v653.txt : one current change log, including historical records

BUILD / DISTRIBUTION
--------------------
The native builders use Python 3.13.16, PyInstaller 6.22.3, and
requirements-build.txt installed with --require-hashes. Source-built,
version/hash-pinned FFmpeg 9.0.2 provides the audio conversion/verification
binary; no downloaded precompiled FFmpeg release binary is used.
Native Windows, Linux and macOS compilation and release verification must run
in the separate TLO GitHub Build Process v126.

No GitHub Build Process artifact is included in this source bundle.
The GitHub Build Process is independently versioned and distributed as its own separate package.

SECURITY AND VERIFICATION
-------------------------
Source checks and local tests do not constitute a signed public release.
Ruff, native smoke tests, vulnerability scans, Windows Authenticode signing,
and signed update metadata must pass the hosted release gates.
SHN verification requires the app-bundled FFmpeg executable and working native
Trash functionality. If either is unavailable, conversion fails without
permanently deleting the SHN original.

Release artifacts include only the current Manual, Requirements Specification,
and CHANGES_v653.txt; historical notes are consolidated in that file. Do not rely on old verification reports to attest
current-build results.
