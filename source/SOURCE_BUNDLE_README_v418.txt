TLO Source and Utilities Bundle v418

Public application version: v1.4 Build 418
Source bundle label: v418

Build 418 summary
- Terminal Band/Group/All-Star-family fallback still identifies a base artist only after the complete candidate misses in the Artist DB.
- After a unique base match, TLO restores the stripped terminal text and uses that expanded name as the performance artist instead of discarding the performance-specific suffix.
- Restored performance artist names that are not full Artist DB matches are persisted in TLOHome/artistsNotInDatabase.txt for later database review.
- Full-name-first, terminal-only, unique-base-match, and duplicate-suffix safeguards remain in force.
- Public application version remains v1.4.
- GitHub Build Process v073 remains independently versioned and unchanged by Build 418.
- Build 417 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v418.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v418.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v418.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 417.

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
