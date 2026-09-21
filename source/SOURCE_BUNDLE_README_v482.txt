TLO Source and Utilities Bundle v482

Public application version: v1.7 Build 482
Source bundle label: v482

Build 482 summary
- Corrects the Manual Updates regression fixtures that caused GitHub Actions Linux tests to fail when the runner exposed a nonblank filesystem volume label.
- Test bootlist rows now use the same canonical [Volume] rootless-path VolumePath representation produced by Full Inventory.
- Keeps the Build 479+ cross-volume Manual Updates safety rule unchanged; no runtime application behavior is relaxed.
- Carries forward all Build 481 cybersecurity hardening unchanged.
- Makes no GitHub Build Process or release-signing changes.

Current documentation files:
- TLO_Inventory_User_Manual_v482.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v482.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v482.txt: changes introduced by this release build.
- old-change-logs.zip: archived historical TLO change notes through Build 481.

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
