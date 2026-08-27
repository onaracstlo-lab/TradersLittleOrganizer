TLO Source and Utilities Bundle v411

Public application version: v1.4 Build 411
Source bundle label: v411

Build 411 summary
- Track-list selection now uses audio-file count as primary evidence before padding a short numbered candidate with Unknown titles.
- Exact-count numbered and unnumbered candidates can be positively reinforced by corresponding audio filenames and existing Title tags; non-matches are neutral and never subtract confidence.
- Short numbered collector notes embedded in prose can be distinguished from an equal-count contiguous song block even when external corroboration is unavailable.
- The reported Cramps 1984-06-25 case now selects all 17 real song titles instead of the three numbered processing notes.
- Public application version remains v1.4.
- GitHub Build Process v071 remains independently versioned and unchanged; its runtime build-number handling already supports Build 411.
- Build 410 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v411.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v411.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v411.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 410.

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
