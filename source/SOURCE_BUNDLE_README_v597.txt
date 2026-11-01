TLO Source and Utilities Bundle v597

Public application version: v1.7 Build 597
Source bundle label: v597
Paired native release GitHub Build Process: v120

Corruption policy: No inspection without tagging or Deep Audio Check. A tag failure
other than transient filesystem/resource failure proves corruption and short-circuits
all further checks. Deep Audio Check performs a reversible tag probe, then verifies
all FLAC PCM against STREAMINFO MD5 and sample totals with pinned source-built
LGPL FFmpeg; other audio formats retain full decode checks. This will be slow on
large collections. Deletion thresholds and safeguards are unchanged. Manual Tweaks
has no corruption checking.

Current documentation files:
- TLO_Inventory_User_Manual_v597.rtf (What's New plus concise usage)
- TLO_Inventory_Requirements_Working_v597.docx (consolidated specification)
- TLO-FAQ.txt
- CHANGES_v597.txt
- BUILD_VERIFICATION_v597.txt
- SHA256SUMS_v597.txt

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
Run with TLO GitHub Build Process v120. No process scripts are in this ZIP.
Prior historical change notes are retained in old-change-logs.zip.
The source-built audio-only FFmpeg 9.0.2 is pinned by SHA256; no GPL FLAC
binary is redistributed. Native signatures, scans and release validation remain
mandatory.

No GitHub Build Process artifact is included in this source bundle.
The GitHub Build Process is independently versioned and distributed as its own separate package.
tlo-main.py: Main GUI.
tlo-search.py: collection search.
