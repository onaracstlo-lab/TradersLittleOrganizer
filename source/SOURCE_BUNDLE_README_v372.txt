TLO Source and Utilities Bundle v372

Public application version: v1.4 Build 372
Source bundle label: v372

Build 372 summary
- Research now accepts every date representation recognized by the canonical TLO Inventory date parser.
- This includes x-placeholder forms such as xxxx-xx-xx and 202x-xx-xx, textual-month dates, compact dates, slash dates, supported ranges, and other Inventory-supported date forms.
- Standalone four-digit 19xx/20xx years remain valid Research date inputs.
- Research normalizes input dates before matching metadata and preserves every valid canonical interpretation of an ambiguous raw date form.
- The public application version advances to v1.4; bundle/build number is 372.
- GitHub Build Process v066 remains recommended/required; no packaging dependency changed in Build 372.

Current documentation files:
- TLO_Inventory_User_Manual_v372.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v372.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v372.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 370.

Primary applications:
- tlo-ggi.py: main Inventory GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-deleteDupes.py: duplicate-folder analysis/holding-area cleanup utility.
- search-artist-db.py: Artist DB search utility.

Research implementation:
- tlo_research_lib.py provides the shared CLI/GUI Research engine.
- Research date recognition delegates to the canonical Inventory date parser in tlo_phase23_v2.py so date behavior stays synchronized.

Build/release helpers:
- createWindowsDist.ps1
- createLinuxDist.sh
- createMacOSDist.sh
- scan_release_artifacts.py

Run the regression suite with:
  python -m pytest -q test_tlo_requirements.py
