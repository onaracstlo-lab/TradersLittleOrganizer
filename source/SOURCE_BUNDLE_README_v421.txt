TLO Source and Utilities Bundle v421

Public application version: v1.4 Build 421
Source bundle label: v421

Build 421 summary
- Fixes multipart tagging order for validated Parent (1) through Parent (N) release folders.
- The parenthesized part number now sorts before the filename track number, so each part completes before the next and Track Number tags no longer stripe all track 01 files across parts.
- Album-wide sequential Track Number behavior is preserved.
- Public application version remains v1.4.
- GitHub Build Process v073 remains independently versioned and unchanged by Build 421.
- Build 420 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v421.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v421.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v421.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 419.

Primary applications:
- tlo-ggi.py: main Inventory GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-deleteDupes.py: duplicate-folder analysis/holding-area cleanup utility.
- search-artist-db.py: Artist DB search utility.

Compatibility/source utility:
- setlistFM.py: thin command-line wrapper around production tlo_setlistfm_lookup; uses TLOHome rate-limit/quota state as Inventory.

Build/release helpers:
- createWindowsDist.ps1
- createLinuxDist.sh
- createMacOSDist.sh
- scan_release_artifacts.py

Run the GitHub-compatible regression suite with:
  python -m pytest -q test_tlo_requirements.py

Run the categorized suite with:
  python -m pytest -q
