TLO Source and Utilities Bundle v397

Public application version: v1.4 Build 397
Source bundle label: v397

Build 397 summary
- Remediates the Build 396 technical review across correctness, bounded input, timeout handling, update security/availability, test categorization, documentation consolidation, and maintenance hygiene.
- One-word setlist-filename Artist DB matches now accept a date only when it is the first substantive component after the artist.
- Selected-setlist metadata reads follow the 1 MiB sample / 16 MiB rejection policy.
- Duplicate-cleanup FLAC validation has a 180-second timeout; an unverifiable keeper blocks duplicate relocation.
- Update checks are pinned to the official repository and downloads are chunked with a 1 GiB hard ceiling.
- setlistFM.py is a compatibility CLI over the production tlo_setlistfm_lookup implementation; it requires normal TLOHome resolution for shared rate-limit state.
- Requirements are consolidated into authoritative Sections 1-20 rather than appending new per-build normative sections.
- Public application version remains v1.4.
- GitHub Build Process v067 remains recommended/required; no packaging dependency changed.

Current documentation files:
- TLO_Inventory_User_Manual_v397.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v397.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v397.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 396.

Primary applications:
- tlo-ggi.py: main Inventory GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-deleteDupes.py: duplicate-folder analysis/holding-area cleanup utility.
- search-artist-db.py: Artist DB search utility.

Compatibility/source utility:
- setlistFM.py: thin command-line wrapper around production tlo_setlistfm_lookup; uses TLOHome rate-limit/quota state.

Build/release helpers:
- createWindowsDist.ps1
- createLinuxDist.sh
- createMacOSDist.sh
- scan_release_artifacts.py

Run the GitHub-compatible regression suite with:
  python -m pytest -q test_tlo_requirements.py

Run the categorized suite with:
  python -m pytest -q
