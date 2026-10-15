TLO Source and Utilities Bundle v590

Public application version: v1.7 Build 590
Source bundle label: v590
Paired native release GitHub Build Process: v117

Corruption policy: No inspection without tagging or Deep Audio Check. A tag failure
other than transient filesystem/resource failure proves corruption and short-circuits
all further checks. Deep Audio Check performs a reversible tag probe, then verifies
all FLAC PCM against STREAMINFO MD5 and sample totals with pinned source-built
LGPL FFmpeg; other audio formats retain full decode checks. This will be slow on
large collections. Deletion thresholds and safeguards are unchanged. Manual Tweaks
has no corruption checking.

Current documentation files:
- TLO_Inventory_User_Manual_v590.rtf (What's New plus concise usage)
- TLO_Inventory_Requirements_Working_v590.docx (consolidated specification)
- TLO-FAQ.txt
- CHANGES_v590.txt
- BUILD_VERIFICATION_v590.txt
- SHA256SUMS_v590.txt

Build 590 requires successful Add New Shows Tag In Place completion before a
performance is staged, inventoried or exported as a setlist. Incomplete tag
runs leave originals for review and report tagged/unchanged/skipped/failed and
excluded audio. Deep Audio Check honors the established corruption policies;
ambiguous multi-show input remains in source; unsupported copy modes fail
explicitly. Potential duplicates still move directly to TLOHome/dups.
Build Process v117 is unchanged.

Main programs: tlo-main.py, tlo-gi.py, tlo-tag.py, tlo-search.py,
tlo-research.py, tlo-reverse.py, tlo-deleteDupes.py, search-artist-db.py.
All platform build programs/tests and LGPL source licensing materials are included.
Run with TLO GitHub Build Process v117. No process scripts are in this ZIP.
Prior historical change notes are retained in old-change-logs.zip.
The source-built audio-only FFmpeg 9.0.2 is pinned by SHA256; no GPL FLAC
binary is redistributed. Native signatures, scans and release validation remain
mandatory.

No GitHub Build Process artifact is included in this source bundle.
The GitHub Build Process is independently versioned and distributed as its own separate package.
tlo-main.py: Main GUI.
tlo-search.py: collection search.
