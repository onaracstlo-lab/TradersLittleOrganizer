TLO Source and Utilities Bundle v476

Public application version: v1.7 Build 476
Source bundle label: v476

Build 476 summary
- Restores semicolons as the separator between multiple Path(s) entries.
- Commas are ordinary path/directive characters and do not require quotes.
- Matching single or double quotes remain accepted.
- Native-Windows Path(s) drag/drop appends multiple items with semicolons and does not auto-quote comma-bearing paths.
- Carries forward all established Build 475 and earlier inventory, tagging, collection, Manual Updates, update, signing/distribution, and GUI behavior unless superseded above.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.

Current documentation files:
- TLO_Inventory_User_Manual_v476.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v476.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v476.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 475.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- In particular, the bundle does not contain Run-TLO-GitHub-Build.ps1, Create-TLOArtifactSigningMetadata.ps1, any TLO_GitHub_Build_Process_Requirements_v*.docx, or any TLO_GitHub_Build_Process_v*.zip.
- The GitHub Build Process is independently versioned and distributed as its own separate package.

Primary applications:
- tlo-ggi.py: main Inventory GUI, including direct main-window Tag, Add New Shows/Updater, and Manual Tweaks/Manual Updates.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI; operation type is inferred from TLO logs.
