TLO Source and Utilities Bundle v467

Public application version: v1.6 Build 467
Source bundle label: v467

Build 467 summary
- Adds first-class MP3 tagging through the same shared tagging pipeline used for FLAC.
- Validates MP3 audio explicitly for corruption handling and includes MP3 files in the same file/folder corruption percentages and policies as FLAC.
- Adds the far-right two-line Delete extra tags checkbox and --delete-extra-tags CLI option.
- When selected, tag writes retain only Artist, Album, Track Number, and Track Title; unrelated metadata and embedded tag artwork are removed where supported.
- Preserves established tag metadata when Delete extra tags is off and retains no-op tag-write behavior when the requested final metadata already matches.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle; companion process v089 remains current because packaging behavior is unchanged.
- Archives historical change notes in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v467.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v467.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v467.txt: changes introduced by this build.
- old-change-logs.zip: archived historical TLO change notes through Build 466.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- In particular, the bundle does not contain Run-TLO-GitHub-Build.ps1, Create-TLOArtifactSigningMetadata.ps1, any TLO_GitHub_Build_Process_Requirements_v*.docx, or any TLO_GitHub_Build_Process_v*.zip.
- The GitHub Build Process is independently versioned and distributed as its own separate package.
- GitHub Build Process v089 is the current companion process baseline.

Primary applications:
- tlo-ggi.py: main Inventory GUI (also hosts embedded Tagger and Add Shows/Updater windows).
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI; operation type is inferred from TLO logs.
