TLO Source and Utilities Bundle v375

Public application version: v1.4 Build 375
Source bundle label: v375

Build 375 summary
- Corrects weak path-derived venue/location fragments before they can contaminate the final Show Name.
- A path tail such as "04 05.Reidsville NC" now retains Reidsville, NC and discards the numeric day/track debris rather than storing Venue=04 and City=05.Reidsville.
- Higher-confidence selected-setlist venue/location metadata may replace only weaker path_part evidence; strong eTreeDB and other non-path evidence remain protected.
- Location is rebuilt after any correction so the Show Name uses the final venue/location values.
- Public application version remains v1.4; bundle/build number advances to 375.
- GitHub Build Process v067 remains recommended/required; no packaging dependency changed in Build 375.

Current documentation files:
- TLO_Inventory_User_Manual_v375.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v375.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v375.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 370.

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
