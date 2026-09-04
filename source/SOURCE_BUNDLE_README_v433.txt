TLO Source and Utilities Bundle v433

Public application version: v1.5 Build 433
Source bundle label: v433

Build 433 summary
- Starts from the verified v1.5 Build 432 source baseline.
- Extracts corruption decisions into directly testable, fail-closed assessment and mutation stages.
- Consolidates current application requirements and introduces stable IDs for high-risk safety requirements.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Keeps public application version v1.5 and advances the application build from 432 to 433.
- Archives Build 432 change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v433.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v433.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v433.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 432.

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
