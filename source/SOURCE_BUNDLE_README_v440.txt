TLO Source and Utilities Bundle v440

Public application version: v1.5 Build 440
Source bundle label: v440

Build 440 summary
- Starts from the latest verified TLO application-source baseline, v1.5 Build 433.
- Defers embedded FLAC ARTIST identity until stronger path and selected-setlist evidence have had the opportunity to resolve the group.
- Gives coherent structural/path/setlist dates precedence over incompatible embedded DATE tags while preserving those tag conflicts in diagnostics.
- Accepts dotted textual dates such as Jan. 28, 1990 and dotted US state forms such as Charleston, W.V. in selected setlist metadata.
- Prevents unresolved conflicted records with blank SHOW_NAME from synthesizing phantom xxxx-xx-xx bootlist identities.
- Restores requested Tag Copy/Delete Original behavior for recoverable hard cases: copy, verify, then delete the source.
- Adds an exact Taj Mahal / foreign Van Morrison-tag regression covering identity, date, venue/location, bootlist safety, and forced cross-filesystem copy/delete behavior.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Keeps public application version v1.5 and advances the application build to 440.
- Archives Build 433 change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v440.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v440.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v440.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 433.

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
