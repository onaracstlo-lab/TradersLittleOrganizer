TLO Source and Utilities Bundle v453

Public application version: v1.6 Build 453
Source bundle label: v453

Build 453 summary
- Starts from the verified v1.6 Build 452 application source bundle.
- Keeps the main checkbox logical grid but prevents the wrapped Tag Copy/Delete Original label from pushing Thorough Setlist Matching down.
- Gives etreeDB, setlist.fm, setlist.fm upgrade, and Thorough Setlist Matching the same compact vertical row increment in the first checkbox column.
- Reflows Corruption Handling into one fully horizontal label/control strip beneath the checkbox options.
- Places each corruption label immediately beside its control; the threshold value and % remain one compact unit.
- Preserves Build 452 first-open screen fitting so the initial visible main window is bounded by the current display.
- Preserves inventory, lookup, tagging, corruption-policy, and CLI semantics.
- Updates the manual, requirements, tests, screenshot, and packaging metadata to v1.6 Build 453.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Archives Build 452 change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v453.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v453.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v453.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 452.

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
