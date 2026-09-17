TLO Source and Utilities Bundle v471

Public application version: v1.6 Build 471
Source bundle label: v471

Build 471 summary
- Fixes Rename Compliantly so capitalization-only differences are real renames instead of being suppressed by Windows case-folded path comparison.
- Applies canonical artist capitalization to physical folder names in Full Inventory/GUI or standalone Tag and Add Shows.
- Uses a temporary sibling hop when a case-insensitive filesystem reports the differently-cased target as the same directory entry, avoiding false alternate/copy collision suffixes.
- Carries forward all established Build 470 and earlier inventory, tagging, MP3, corruption, collection, logging, reverse-action, GUI Tag, setlist.fm-key, Max Workers, and packaging behavior unless superseded above.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.

Current documentation files:
- TLO_Inventory_User_Manual_v471.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v471.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v471.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 470.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- In particular, the bundle does not contain Run-TLO-GitHub-Build.ps1, Create-TLOArtifactSigningMetadata.ps1, any TLO_GitHub_Build_Process_Requirements_v*.docx, or any TLO_GitHub_Build_Process_v*.zip.
- The GitHub Build Process is independently versioned and distributed as its own separate package.

Primary applications:
- tlo-ggi.py: main Inventory GUI, including direct main-window Tag and the Add Shows/Updater window.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI; operation type is inferred from TLO logs.
