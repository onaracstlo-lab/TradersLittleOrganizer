TLO Source and Utilities Bundle v378

Public application version: v1.4 Build 378
Source bundle label: v378

Build 378 summary
- Defers short no-space-date artist abbreviations until stronger artist evidence has been exhausted.
- A full DB-backed artist elsewhere in the path, selected-setlist evidence, usable audio tags, and other structured artist sources now outrank the short abbreviation.
- The abbreviation-bearing path component is excluded from ordinary subdirectory artist matching so it cannot be promoted early through a second path.
- Uses the abbreviation only as the final local fallback and records it as low-confidence last-resort evidence.
- When enabled and an exact date is available, eTreeDB/setlist.fm artist-date lookup is attempted after the fallback as an additional confirmation.
- Public application version remains v1.4; bundle/build number advances to 378.
- GitHub Build Process v067 remains recommended/required; no packaging dependency changed in Build 378.

Current documentation files:
- TLO_Inventory_User_Manual_v378.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v378.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v378.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 377.

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
