TLO Source and Utilities Bundle v461

Public application version: v1.6 Build 461
Source bundle label: v461

Build 461 summary
- Makes Search Path the required Full Inventory input; TLOHome/toBeInventoried.txt is no longer consumed automatically.
- Search Path accepts semicolon-separated entries. Direct entries use the established inventory-control grammar with optional [Volume], --$slam, --$copy, and --$copy-delete directives.
- Any Search Path entry ending in a .txt file is parsed using the former toBeInventoried.txt line/file rules, regardless of filename.
- Preserves the separate Slam field for direct-path compatibility while rejecting ambiguous separate directives when a .txt control file is used.
- Removes "(optional/override)" from the main-window Search Path label and reduces the Slam box from width 66 to width 33.
- Keeps toBeInventoried.txt in COMPLETE distributions as an example/template only through companion GitHub Build Process v089.
- Preserves Build 460 guarded Artist + Place + Date + technical-suffix handling, Build 459 Tag controls, and Build 458 updater package behavior.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.
- Archives historical change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v461.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v461.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v461.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 460.

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
