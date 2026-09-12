TLO Source and Utilities Bundle v456

Public application version: v1.6 Build 456
Source bundle label: v456

Build 456 summary
- Continues from the verified v1.6 Build 455 application source bundle.
- Removes Reverse Copy/Delete + Rename from the main Inventory GUI.
- Adds tlo-reverse, a standalone folder-only reversal CLI driven by TLO success logs.
- Infers Rename Compliantly, Tag Copy, and Tag Copy/Delete Original from authoritative source -> destination mappings; no required operation-type flag.
- Supports Copy/Delete whether Rename Compliantly was enabled or not, plus rename-only and retained-original Tag Copy reversal.
- Refuses ambiguous multi-run selection, overwrite conflicts, and changed Tag Copy file sets; adds --log and --dry-run.
- Never changes or attempts to reverse audio tags.
- Packages tlo-reverse on Windows, Linux, and macOS.
- Updates the User Manual, FAQ, requirements, tests, and packaging metadata to v1.6 Build 456.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Archives historical change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v456.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v456.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v456.txt: changes introduced by this build.
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
