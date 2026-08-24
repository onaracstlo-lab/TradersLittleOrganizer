TLO Source and Utilities Bundle v394

Public application version: v1.4 Build 394
Source bundle label: v394

Build 394 summary
- Hardened five legacy inventory regression tests that use intentionally invalid FLAC placeholder bytes.
- Those tests now explicitly set acceptable corruption % to 100 because they test copy/delete, rename, tagging, and unidentified-show behavior rather than corruption removal.
- This removes Linux-environment dependence on whether `gio trash` succeeds during synthetic tests.
- Runtime application behavior is unchanged from Build 393.
- Public application version remains v1.4.
- GitHub Build Process v067 remains recommended/required; no packaging dependency changed.

Current documentation files:
- TLO_Inventory_User_Manual_v394.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v394.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v394.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through the immediately preceding build.

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
