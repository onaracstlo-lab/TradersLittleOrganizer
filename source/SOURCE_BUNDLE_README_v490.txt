TLO Source and Utilities Bundle v490

Public application version: v1.7 Build 490
Source bundle label: v490

Build 490 summary
- Extends only the existing guarded non-compliant Artist + Place + Date fallback.
- A direct, unique Artist DB prefix plus a valid existing date may recover intervening venue/location text when the post-date tail is fully recognized.
- Recognized tails remain narrow: existing media/source technical tokens, the literal SDB compatibility spelling, or one existing terminal performance qualifier such as Set 1.
- Existing Artist Date ... interpretations retain precedence; ordinary title-like tails still do not activate the fallback.
- Compliant mode is unchanged.
- Carries forward Build 489 Help > About contact email, Build 488 Redundancy Groups Close wording, Build 487 ordered Redundancy Groups, Build 486 Copy Request menu placement, Build 485 persistent Copy Requests, and all prior behavior.

Current documentation files:
- TLO_Inventory_User_Manual_v490.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v490.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v490.txt: changes introduced by this release build.
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
