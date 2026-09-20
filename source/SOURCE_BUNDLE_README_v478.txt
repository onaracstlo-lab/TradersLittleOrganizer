TLO Source and Utilities Bundle v478

Public application version: v1.7 Build 478
Source bundle label: v478

Build 478 summary
- Adds a default-on Update Tags checkbox to Manual Updates. Checked saves tag each corrected folder before finalizing its inventory identity; unchecked saves leave tags unchanged.
- Applies Update Tags to normal folder corrections, already manually changed unidentified-show recovery, and .txt Manual Updates batches.
- Fixes Manual Updates New Name drag/drop so one dropped folder is accepted without depending on Original already containing a folder; New Name remains disabled for .txt batches.
- Treats apostrophes/single quotes as ordinary Path(s) text while retaining semicolons as separators and optional matching double quotes.
- Allows authoritative online venue/location evidence to improve case-only spelling used by Rename Compliantly without overriding genuinely different path metadata.
- Carries forward all established Build 476 and earlier inventory, tagging, collection, update, signing/distribution, and GUI behavior unless superseded above. Build 477 was an intermediate patch and is incorporated here.
- Keeps the GitHub Build Process strictly separate from the TLO application source bundle.

Current documentation files:
- TLO_Inventory_User_Manual_v478.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v478.docx: current TLO requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v478.txt: changes introduced by this complete build, including the intermediate Build 477 fixes.
- old-change-logs.zip: archived historical TLO change notes through Build 476.

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
