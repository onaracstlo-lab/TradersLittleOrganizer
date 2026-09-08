TLO Source and Utilities Bundle v446

Public application version: v1.6 Build 446
Source bundle label: v446

Build 446 summary
- Starts from the verified v1.6 Build 445 application source bundle.
- Moves the main Inventory checkbox block slightly left and reduces horizontal gaps between checkbox columns without changing the existing checkbox grid.
- Narrows Search Path and Slam entry widths from 92 to 86 so the natural main Inventory window is modestly narrower.
- Preserves the Build 445 compact Corruption Handling group and all corruption/CLI/runtime semantics.
- Updates the current main-window figure, manual, requirements, tests, and packaging metadata to v1.6 Build 446.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Archives Build 445 change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v446.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v446.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v446.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 445.

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
