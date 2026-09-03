TLO Source and Utilities Bundle v426

Public application version: v1.5 Build 426
Source bundle label: v426

Build 426 summary
- Starts from the verified v1.5 Build 425 source baseline.
- Adds a non-compliant Date Artist Venue Location path pattern for date-first show folders.
- Requires the Artist to be the longest unique Artist DB match anchored immediately after the leading date.
- Requires a complete Venue plus City and Region/Country after removing the Artist; date-first Artist-plus-location-only text is rejected.
- Resolves 1997-04-05 Genesis Old Pub London England as Genesis 1997-04-05 Old Pub London, England.
- Rejects 1990-07-10 Palace Melbourne Australia under the new pattern because no venue remains after Palace is removed.
- Keeps public application version v1.5 and advances the application build from 425 to 426.
- Retains the current Run-TLO-GitHub-Build.ps1 and matching TLO_GitHub_Build_Process_Requirements_v075.docx directly at the source-bundle root.
- The GitHub Build Process remains independently versioned; its complete current package is TLO_GitHub_Build_Process_v075.zip and remains a separate ZIP.
- Build 425 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v426.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v426.docx: current TLO requirements/development document.
- TLO_GitHub_Build_Process_Requirements_v075.docx: current GitHub build-process requirements baseline.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v426.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 425.

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
