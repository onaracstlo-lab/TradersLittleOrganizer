TLO Source and Utilities Bundle v455

Public application version: v1.6 Build 455
Source bundle label: v455

Build 455 summary
- Starts from the verified v1.6 Build 454 application source bundle.
- Removes stale `unidentifiedShows.txt` entries when the same path is processed again and successfully resolved.
- Preserves untouched prior unresolved entries and any path that remains unresolved in the current run.
- Preserves encounter order in `unidentifiedShows.txt` and `artistsNotInDatabase.txt`; neither file is alphabetically sorted.
- Retains case-insensitive de-duplication for artists and path de-duplication for unidentified shows.
- Trims the Corrupt files dropdown from width 20 to width 18 so it is only slightly wider than the compact baseline.
- Updates the manual, requirements, tests, and packaging metadata to v1.6 Build 455.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Archives Build 454 change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v455.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v455.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v455.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 454.

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
