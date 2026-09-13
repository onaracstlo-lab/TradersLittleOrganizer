TLO Source and Utilities Bundle v458

Public application version: v1.6 Build 458
Source bundle label: v458

Build 458 summary
- Continues from the verified v1.6 Build 457 application source bundle.
- Hardens the GUI GitHub updater to select only exact official platform/layout release ZIPs.
- Prefers the exact matching UPDATE package and falls back only to the exact matching COMPLETE package; generic/source ZIPs and cross-layout Windows packages are never selected.
- Distinguishes Windows hybrid/onefile from Windows onedir by the installed TLOHome/runtime layout.
- After SHA-256 verification, validates the ZIP manifest without extraction for package kind, build, platform/layout, and database declaration/content agreement.
- Correctly handles update-only releases, complete-only releases, releases with both package kinds, normal updates without databases, and explicit database-refresh updates.
- Reports whether a downloaded update contains TLO_DBs/artists.sqlite and TLO_DBs/venues.txt so the user knows those master files will be replaced when the package is applied.
- Preserves download-only behavior: TLO does not extract, execute, install, replace, or delete files during update checking.
- Updates the User Manual, FAQ, requirements, tests, and packaging metadata to v1.6 Build 458.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Archives historical change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v458.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v458.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v458.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 457.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- In particular, the bundle does not contain Run-TLO-GitHub-Build.ps1, Create-TLOArtifactSigningMetadata.ps1, any TLO_GitHub_Build_Process_Requirements_v*.docx, or any TLO_GitHub_Build_Process_v*.zip.
- The GitHub Build Process is independently versioned and distributed as its own separate package.
- Build Process v087 adds complete-only/update-only generation and optional database inclusion in UPDATE packages; it is distributed separately from this source bundle.

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
