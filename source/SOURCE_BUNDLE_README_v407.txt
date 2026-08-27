TLO Source and Utilities Bundle v407

Public application version: v1.4 Build 407
Source bundle label: v407

Build 407 summary
- Extends the existing terminal Band Artist DB fallback to terminal All Star/All Stars variants, including All-Star, All-Stars, AllStar, and AllStars spellings, case-insensitively.
- The complete potential artist name is always searched first. Suffix stripping is only a secondary no-match fallback and is accepted only when the shorter form resolves to exactly one Artist DB master.
- Keeps the Research input Search button as the active/default action whenever the Research dialog is active; Return and keypad Enter invoke Search from anywhere in that dialog.
- Research results remain read-only and now support Ctrl-A select-all at the window level.
- Research results add a Search button; Ctrl-F invokes the same action. The find dialog contains Search for:, Forward/Backwards mutually exclusive direction controls (Forward by default), repeated directional searching, and wraparound.
- Added Build 407 regression coverage for All-Star suffix variants, exact-name precedence, ambiguity protection, Research select-all, search controls, direction, and wraparound.
- Public application version remains v1.4.
- GitHub Build Process v071 remains independently versioned and unchanged; its runtime build-number handling already supports Build 407.
- Build 406 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v407.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v407.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v407.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 406.

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
