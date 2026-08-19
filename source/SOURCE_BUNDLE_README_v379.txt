TLO Source and Utilities Bundle v379

Public application version: v1.4 Build 379
Source bundle label: v379

Build 379 summary
- Rejects Exact Audio Copy (EAC) extraction logs, TOC tables, and comparable numeric timestamp/sector tables as track-title sources.
- Adds a conservative numbered-title plausibility check so a clean 1..N technical table cannot outrank real song-list evidence.
- Retains explicit local Songs:/Tracks: blocks as recognized local song-list evidence even when their title count differs from the audio-file count.
- Reports that mismatch without forcing or truncating the local song list onto the files.
- Preserves normal precedence for genuinely valid numbered song lists.
- Includes a Foghat/EAC regression matching the reported five-song/four-FLAC info-file structure.
- Public application version remains v1.4; bundle/build number advances to 379.
- GitHub Build Process v067 remains recommended/required; no packaging dependency changed in Build 379.

Current documentation files:
- TLO_Inventory_User_Manual_v379.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v379.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v379.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 378.

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
