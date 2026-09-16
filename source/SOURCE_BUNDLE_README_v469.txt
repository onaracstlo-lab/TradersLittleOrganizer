TLO Source and Utilities Bundle v469

Public application version: v1.6 Build 469
Source bundle label: v469

Build 469 summary
- Removes the separate GUI Tag window and runs GUI Tag directly from the main Path(s), Slam, tag mode, and current main-window settings.
- Greys/disables folder-removal controls when Corrupt files is Keep and report and makes the effective folder policy Never.
- Disables/unchecks setlist.fm and setlist.fm upgrade when SETLISTFM_API_KEY is unavailable.
- Treats Max Workers as an independent ceiling; Performance Mode and runtime rules may use fewer workers.
- Fixes real horizontal scrolling in the completion View Issues window.
- Demotes successful tag-parser branch decisions from warnings to informational output while retaining consequential warnings/errors.
- Adds Build 469 regression tests and carries forward all established Build 468 and earlier inventory, tagging, MP3, corruption, collection, logging, reverse-action, and packaging behavior unless superseded above.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.

Current documentation files:
- TLO_Inventory_User_Manual_v469.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v469.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v469.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 468.

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
