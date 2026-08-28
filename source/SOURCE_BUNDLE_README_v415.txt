TLO Source and Utilities Bundle v415

Public application version: v1.4 Build 415
Source bundle label: v415

Build 415 summary
- Tag Copy/Delete Original treats its destination parent as an append container rather than a broad re-inventory scope.
- Existing bootlist/setlist entries elsewhere under that destination parent are preserved.
- Only a prior row whose complete destination Volume+Path exactly matches a show path produced by the current Copy/Delete run may be replaced.
- Normal direct re-inventory behavior for explicitly inventoried trees is unchanged.
- Public application version remains v1.4.
- GitHub Build Process v071 remains independently versioned and unchanged; its runtime build-number handling already supports Build 415.
- Build 414 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v415.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v415.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v415.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 414.

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
