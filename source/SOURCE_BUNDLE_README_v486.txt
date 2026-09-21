TLO Source and Utilities Bundle v486

Public application version: v1.7 Build 486
Source bundle label: v486

Build 486 summary
- Moves Copy Requests from the main Inventory action button row to the upper-right hamburger menu.
- The persistent Copy Requests manager and all Build 485 Copy Request functionality are unchanged.
- No other GUI layout, spacing, control order, button behavior, option behavior, or checkbox behavior changes.
- Carries forward all Build 485 Copy Requests functionality, Build 484 checkbox text, Build 483 setlist.fm-upgrade gating, Build 481 security hardening, and prior stabilization behavior.

Current documentation files:
- TLO_Inventory_User_Manual_v486.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v486.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v486.txt: changes introduced by this release build.
- old-change-logs.zip: archived historical TLO change notes through Build 485.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- In particular, the bundle does not contain Run-TLO-GitHub-Build.ps1, Create-TLOArtifactSigningMetadata.ps1, any TLO_GitHub_Build_Process_Requirements_v*.docx, or any TLO_GitHub_Build_Process_v*.zip.
- The GitHub Build Process is independently versioned and distributed as its own separate package.

Primary applications:
- tlo-ggi.py: main Inventory GUI, including direct Tag, Add New Shows/Updater, Manual Tweaks/Manual Updates, Research, and persistent Copy Requests accessed from the upper-right hamburger menu.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI; operation type is inferred from TLO logs.
