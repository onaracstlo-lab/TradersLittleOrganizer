TLO Source and Utilities Bundle v493

Public application version: v1.7 Build 493
Source bundle label: v493

Build 493 summary
- Preserves Build 492's uppercase region-code protections as the default.
- Cautiously accepts exact lowercase state/province abbreviations in non-compliant path-derived location fragments when that fragment is consistently lowercase.
- Mixed-case protected codes remain rejected.
- Common/word-like codes require a comma before the code or both venue and city, with noise-word safeguards retained.
- Setlist/free-form parsing remains uppercase-only for protected codes; Compliant mode is unchanged.
- Carries forward all Build 492 and earlier behavior except for this narrow lowercase-path relaxation.

Current documentation files:
- TLO_Inventory_User_Manual_v493.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v493.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v493.txt: changes introduced by this release build.
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
