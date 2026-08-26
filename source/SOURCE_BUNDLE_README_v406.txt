TLO Source and Utilities Bundle v406

Public application version: v1.4 Build 406
Source bundle label: v406

Build 406 summary
- Advances the build from 405 to make the packaged regression suite deterministic across Linux environments with and without a functioning Trash backend.
- Runtime application behavior is unchanged from Build 405.
- Five historical tests that exercise inventory orchestration rather than corruption handling now explicitly neutralize corruption classification for their placeholder .flac byte fixtures.
- The tests do not disable Trash/Recycle Bin; dedicated corruption tests continue to cover destructive safety behavior.
- Added Build 406 checks that constrain this neutralization to the intended five tests.
- Build 405 remains the cancellation log-token safety and CI GUI coverage release and is archived in old-change-logs.zip.
- Public application version remains v1.4.
- GitHub Build Process v071 remains independently versioned and unchanged.

Current documentation files:
- TLO_Inventory_User_Manual_v406.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v406.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v406.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 405.

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
