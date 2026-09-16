TLO Source and Utilities Bundle v470

Public application version: v1.6 Build 470
Source bundle label: v470

Build 470 summary
- Stops normal unidentifiedShows.txt creation/update status from being misclassified as an Unidentified show warning in the GUI completion summary.
- A zero-unidentified-shows result is informational and does not increase the warning count or appear in View Issues.
- Real unidentified-show conditions continue to be reported.
- Carries forward all established Build 469 and earlier inventory, tagging, MP3, corruption, collection, logging, reverse-action, GUI Tag, setlist.fm-key, Max Workers, and packaging behavior unless superseded above.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.

Current documentation files:
- TLO_Inventory_User_Manual_v470.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v470.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v470.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 469.

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
