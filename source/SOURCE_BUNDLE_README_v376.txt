TLO Source and Utilities Bundle v376

Public application version: v1.4 Build 376
Source bundle label: v376

Build 376 summary
- Accepts 19xx-xx-xx and 20xx-xx-xx as legitimate century-known partial dates in the canonical Inventory parser.
- Compliant folders such as "Duke Ellington 19xx-xx-xx Danish Radio" now resolve Artist, Date, and trailing Album/Show text directly from the folder name.
- Keeps 1xxx-xx-xx, 2xxx-xx-xx, and century-known partial years with later known month/day components invalid.
- Research inherits the same canonical date parsing.
- Public application version remains v1.4; bundle/build number advances to 376.
- GitHub Build Process v067 remains recommended/required; no packaging dependency changed in Build 376.

Current documentation files:
- TLO_Inventory_User_Manual_v376.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v376.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v376.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 375.

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
