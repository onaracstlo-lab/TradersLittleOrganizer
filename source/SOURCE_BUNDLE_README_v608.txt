TLO Source and Utilities Bundle v608

Public application version: v1.7 Build 608
Source bundle label: v608
Paired native release GitHub Build Process: v122

Corruption policy: No inspection without tagging or Deep Audio Check. A tag failure
other than transient filesystem/resource failure proves corruption and short-circuits
all further checks. Deep Audio Check performs a reversible tag probe, then verifies
all FLAC PCM against STREAMINFO MD5 and sample totals with pinned source-built
LGPL FFmpeg; other audio formats retain full decode checks. This will be slow on
large collections. Deletion thresholds and safeguards are unchanged. Manual Tweaks
has no corruption checking.

Current documentation files:
- TLO_Inventory_User_Manual_v608.rtf (What's New plus concise usage)
- TLO_Inventory_Requirements_Working_v608.docx (consolidated specification)
- TLO-FAQ.txt
- tlo-preferences.ini (user-approved concise default, choices and ranges annotated; copied on first startup into TLOHome)
- CHANGES_v608.txt
- BUILD_VERIFICATION_v608.txt
- SHA256SUMS_v608.txt

Build 594 retains Build 590 behavior: successful Add New Shows Tag In Place completion before a
performance is staged, inventoried or exported as a setlist. Incomplete tag
runs leave originals for review and report tagged/unchanged/skipped/failed and
excluded audio. Deep Audio Check honors the established corruption policies;
ambiguous multi-show input remains in source; unsupported copy modes fail
explicitly. Potential duplicates still move directly to TLOHome/dups.
Build 594 additionally fixes artist/venue/date identification for NRBQ-style Artist Venue City Date folders with independent setlist confirmation. Collector/source text is not misused as a venue. Build Process v120 includes fail-closed macOS artifact scanning and a security-patched setuptools lock.

Build 594 additionally prevents Windows access-denied log rewrites during re-inventory by releasing open TLO FileHandlers while pruning, reopening in append mode, and retrying transient Windows sharing locks. Existing log data and failure reporting are preserved.

Build 595 adds a conditional vertical scrollbar to the shared Review Operation dialog, keeping the action buttons accessible and preserving the settings log without behavior changes.

Build 596 repairs the macOS/Linux FFmpeg build recipe under strict Bash by avoiding an empty optional-flags array. The Windows static-link flags and DLL import checks are preserved.

Build 597 retries transient official FFmpeg source download failures, including connection resets on macOS, using a bounded schedule and official host fallback. Every archive is SHA-256 verified before caching and compilation; security checks are unchanged. Build Process v120 is unchanged.

Main programs: tlo-main.py, tlo-gi.py, tlo-tag.py, tlo-search.py,
tlo-research.py, tlo-reverse.py, tlo-deleteDupes.py, search-artist-db.py.
All platform build programs/tests and LGPL source licensing materials are included.
Run with TLO GitHub Build Process v122. No process scripts are in this ZIP.
Prior historical change notes are retained in old-change-logs.zip.
The source-built audio-only FFmpeg 9.0.2 is pinned by SHA256; no GPL FLAC
binary is redistributed. Native signatures, scans and release validation remain
mandatory.

No GitHub Build Process artifact is included in this source bundle.
The GitHub Build Process is independently versioned and distributed as its own separate package.
tlo-main.py: Main GUI.
tlo-search.py: collection search.

Build 599: TLO Main/Search GUI uses its own icon for the running window and child dialogs. Windows/macOS/Linux PyInstaller builds bundle the necessary PNG artwork; Windows also bundles ICO. Native builds and signing remain required before distribution.

Build 599 adds unique Artist DB compressed-name fallback for etree-style folders with adjacent dates, with local setlist corroboration and ambiguity safeguards.

Build 600 corrected source Windows PNG/ICO preflight and paired with GitHub Build Process v121, which regenerates Windows onefile and shared-onedir scripts with both runtime icons present and checked.

Build 601 requires GitHub Build Process v122. FFmpeg 9.0.2 upstream source is fetched and SHA-256 checked once on Ubuntu, transferred via short-lived artifact to all native platform jobs, and independently verified by each job before native compilation. The TLO_FFMPEG_SOURCE_ARCHIVE environment variable is a mandatory, fail-closed local artifact override when provided; absent override retains source-fetch behavior for manual/local builds.

Build 602 isolates upstream-download unit tests from the CI shared-archive override and removes an impermissible numeric build reference from the evergreen FAQ. Native source validation, hashing, fail-closed policy, and packaging are unchanged.

Build 606: TLO Main and Search create and read TLOHome/tlo-preferences.ini on startup. All Main checkbox defaults (including Dry Run), corruption policy and threshold, performance mode, Max Workers, font families and sizes, Search Deep/font/query defaults, Manual Tweaks Update Tags, Add New Shows Check For Duplicates, and shared Auto Update are configurable. The hamburger Edit Preferences text editor validates before an atomic save and prompts for restart. Explicit Main CLI flags and Search --find take precedence. Existing preference files are never overwritten. The versioned source bundle includes a default tlo-preferences.ini template.

Build 606: Non-compliant path artist detection suppresses distant two-character storage-directory collisions when a nearer exact full Artist DB directory identifies the performer. Setlist Artist / City, Country / Unknown venue / Date headers identify the performer and location while leaving venue blank. Explicit artist and conflicting full-name safety guards remain in force.

Build 607: Release verification report again includes the required exact Ruff lint: label and explicit lint-not-attested status; this fixes hosted Linux CI test failures without relaxing mandatory lint or changing application behavior.

Build 608: Removes an unused Path import in the Build 607 release-report regression test to satisfy Ruff F401. No application runtime or GitHub Build Process changes. Native release checks are still mandatory.
