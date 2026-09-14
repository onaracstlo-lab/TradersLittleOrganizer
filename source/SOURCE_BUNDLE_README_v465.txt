TLO Source and Utilities Bundle v465

Public application version: v1.6 Build 465
Source bundle label: v465

Build 465 summary
- Fixes automatic recovery after a forced Quit interrupts sibling-collection aggregation when the completed recovery container occupies the same pathname as an original collection member.
- Moves that outer recovery container aside before restoring journaled member folders, so duplicated-path cases can roll back safely and Inventory can continue.
- Reports successful recovery in the console and expands failure diagnostics to show the exact recovery container, journal, planned final folder, and original/staged state for every member.
- Fails closed on unreadable recovery journals and orphaned .tlo-collection-* temporary folders instead of traversing them.
- Updates the late-stage Quit warning to explain that forced exit can interrupt a collection move and that the next normal Inventory run attempts journal-based rollback.
- Keeps Build 463 Path(s), checkbox-alignment, and native-Windows cumulative drag/drop behavior unchanged.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle; companion process v089 remains current because packaging behavior is unchanged.
- Archives historical change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v465.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v465.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v465.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 463.

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
