TLO Source and Utilities Bundle v463

Public application version: v1.6 Build 463
Source bundle label: v463

Build 463 summary
- Renames the visible main Inventory Search Path label to Path(s); Search Path semantics and the --search-path CLI option are unchanged.
- Vertically centers one-line checkbox indicators with their labels so checkbox text no longer appears slightly lower than the indicator.
- Keeps the two wrapped checkbox labels aligned to their first text line instead of centering their indicator between both lines.
- Corrects Build 462 cumulative native-Windows Path(s) drag/drop while preserving Build 461 required Search Path/control-file behavior and all other existing inventory/tagging rules.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle; companion process v089 remains current because packaging behavior is unchanged.
- Archives historical change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v463.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v463.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v463.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 462.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- In particular, the bundle does not contain Run-TLO-GitHub-Build.ps1, Create-TLOArtifactSigningMetadata.ps1, any TLO_GitHub_Build_Process_Requirements_v*.docx, or any TLO_GitHub_Build_Process_v*.zip.
- The GitHub Build Process is independently versioned and distributed as its own separate package.
- GitHub Build Process v089 is the current companion process baseline; it retains v088 parser safety and v087 package-selection/database-update behavior while changing COMPLETE-package toBeInventoried.txt/README text to template-only semantics.

Primary applications:
- tlo-ggi.py: main Inventory GUI (also hosts embedded Tagger and Add Shows/Updater windows).
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI; operation type is inferred from TLO logs.
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
