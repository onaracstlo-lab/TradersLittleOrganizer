TLO Source and Utilities Bundle v487

Public application version: v1.7 Build 487
Source bundle label: v487

Build 487 summary
- Adds ordered Redundancy Groups for equivalent replica volumes used by persistent Copy Requests.
- A = B = C means A has highest source precedence and C the lowest.
- Redundancy group members can be volume labels or currently accessible paths; path inputs with spaces do not require quotes.
- Backup/equivalent volumes do not need separate bootlist inventory rows.
- Carries forward all Build 486 Copy Request menu placement, Build 485 persistent Copy Requests, Build 484 checkbox text, Build 483 setlist.fm-upgrade gating, Build 481 security hardening, and prior stabilization behavior.

Current documentation files:
- TLO_Inventory_User_Manual_v487.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v487.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v487.txt: changes introduced by this release build.
- old-change-logs.zip: archived historical TLO change notes through Build 486.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- In particular, the bundle does not contain Run-TLO-GitHub-Build.ps1, Create-TLOArtifactSigningMetadata.ps1, any TLO_GitHub_Build_Process_Requirements_v*.docx, or any TLO_GitHub_Build_Process_v*.zip.
- The GitHub Build Process is independently versioned and distributed as its own separate package.

Primary applications:
- tlo-ggi.py: main Inventory GUI, including direct Tag, Add New Shows/Updater, Manual Tweaks/Manual Updates, Research, persistent Copy Requests, and Redundancy Groups accessed from the upper-right hamburger menu.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI; operation type is inferred from TLO logs.
