TLO Source and Utilities Bundle v423

Public application version: v1.5 Build 423
Source bundle label: v423

Build 423 summary
- Keeps the public application version at v1.5 and advances the application build from 422 to 423.
- Removes the complete TLO GitHub Build Process ZIP from the TLO source bundle.
- Adds the current Run-TLO-GitHub-Build.ps1 directly to the TLO source bundle root.
- Adds the matching TLO_GitHub_Build_Process_Requirements_v075.docx directly to the TLO source bundle root.
- The GitHub Build Process remains independently versioned; its complete current package is TLO_GitHub_Build_Process_v075.zip and remains a separate ZIP.
- GitHub Build Process v075 renames the primary runner from 03-Run-TLO-GitHub-Build.ps1 to Run-TLO-GitHub-Build.ps1 and revises its requirements baseline to treat one-time setup outcomes as assumptions.
- Build 422 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v423.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v423.docx: current TLO requirements/development document.
- TLO_GitHub_Build_Process_Requirements_v075.docx: current GitHub build-process requirements baseline.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v423.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 422.

Included GitHub build artifacts:
- Run-TLO-GitHub-Build.ps1: current primary GitHub build/release orchestration script.
- TLO_GitHub_Build_Process_Requirements_v075.docx: requirements for the current GitHub build process.

The full TLO_GitHub_Build_Process_v075.zip is intentionally not embedded here. The source-bundle copy of Run-TLO-GitHub-Build.ps1 is the current runner for reference/convenience; the complete GitHub build-process ZIP remains the runnable package because the runner uses support files distributed with that package.

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
