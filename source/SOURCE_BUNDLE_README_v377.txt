TLO Source and Utilities Bundle v377

Public application version: v1.4 Build 377
Source bundle label: v377

Build 377 summary
- Adds a horizontal scrollbar along the bottom of the Inventory GUI Research results box while retaining vertical scrolling.
- Keeps Research results non-wrapping so long log/metadata lines can be inspected horizontally.
- Makes Search the active/default action in the Research input dialog.
- Pressing Enter anywhere while the Research input dialog has focus runs Search, rather than requiring focus to remain in the text-entry control.
- Public application version remains v1.4; bundle/build number advances to 377.
- GitHub Build Process v067 remains recommended/required; no packaging dependency changed in Build 377.

Current documentation files:
- TLO_Inventory_User_Manual_v377.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v377.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v377.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 376.

Primary applications:
- tlo-ggi.py: main Inventory GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-deleteDupes.py: duplicate-folder analysis/holding-area cleanup utility.
- search-artist-db.py: Artist DB search utility.

Build/release helpers:
- createWindowsDist.ps1
- createLinuxDist.sh
- createMacOSDist.sh
- scan_release_artifacts.py

Run the regression suite with:
  python -m pytest -q test_tlo_requirements.py
