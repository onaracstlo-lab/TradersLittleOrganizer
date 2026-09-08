TLO Source and Utilities Bundle v448

Public application version: v1.6 Build 448
Source bundle label: v448

Build 448 summary
- Starts from the verified v1.6 Build 447 application source bundle.
- Removes the confusing Thorough Setlist Matching Info line when neither etreeDB nor setlist.fm is enabled.
- When online lookup sources are enabled, Thorough Info simply names the enabled source(s); normal setlist.fm access still warns about the 600-ms / 1,400-call limits.
- Wraps the visible Tag Copy/Delete Original checkbox label to two lines, tightens checkbox-column gaps, and pulls the final checkbox column farther left.
- Narrows Search Path and Slam entry widths from 74 to 66 characters, reducing the natural main Inventory window width to about 1107 px in the same Tk/Xvfb environment.
- Preserves checkbox ordering/grid coordinates, lookup behavior, corruption behavior, tagging behavior, and CLI semantics.
- Updates the current main-window figure, manual, requirements, tests, and packaging metadata to v1.6 Build 448.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Archives Build 447 change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v448.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v448.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v448.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 447.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- In particular, the bundle does not contain Run-TLO-GitHub-Build.ps1, Create-TLOArtifactSigningMetadata.ps1, any TLO_GitHub_Build_Process_Requirements_v*.docx, or any TLO_GitHub_Build_Process_v*.zip.
- The GitHub Build Process is independently versioned and distributed as its own separate package.

Primary applications:
- tlo-ggi.py: main Inventory GUI (also hosts embedded Tagger and Add Shows/Updater windows).
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-deleteDupes.py: duplicate-folder analysis/holding-area cleanup utility.
- search-artist-db.py: Artist DB search utility.

Compatibility/source utility:
- setlistFM.py: thin command-line wrapper around production tlo_setlistfm_lookup; uses TLOHome rate-limit/quota state as Inventory.

Application build/release helpers:
- createWindowsDist.ps1
- createLinuxDist.sh
- createMacOSDist.sh
- scan_release_artifacts.py

Run the GitHub-compatible regression suite with:
  python -m pytest -q test_tlo_requirements.py

Run the categorized suite with:
  python -m pytest -q
