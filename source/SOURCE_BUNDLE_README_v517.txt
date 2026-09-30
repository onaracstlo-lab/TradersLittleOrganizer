TLO Source and Utilities Bundle v517

Public application version: v1.7 Build 517
Source bundle label: v517

Build 517 summary
- Removes accidental temporary/scratch requirements DOCX files from the source bundle.
- Adds regression coverage requiring exactly one current requirements DOCX in the source root and rejecting scratch/temp requirements artifacts.
- Carries forward Build 516 update-check ordering, Build 515 search/setlist filename alignment, and the Build 513 independently signed update trust model.

Update-signing trust anchor
- tlo_update_trust.py intentionally contains an empty update-signing trust anchor in the source bundle.
- Run-TLO-GitHub-Build.ps1 v098 requires the locally generated public-key JSON and injects that public key into the transient source snapshot before executable builds.
- The private update-signing key must never be added to this bundle or GitHub.

Current documentation files:
- TLO_Inventory_User_Manual_v517.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v517.docx: current consolidated TLO requirements specification.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v517.txt: changes introduced by this release build plus carried-forward recent history.
- old-change-logs.zip: archived historical TLO change notes and superseded verification/checksum artifacts.
- BUILD_VERIFICATION_v517.txt: local verification results for this source build.
- SHA256SUMS_v517.txt: SHA-256 manifest for all bundle files except the manifest itself.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- The GitHub Build Process remains independently versioned and distributed as its own separate package. The current process supplied with this work is v098; Build 517 does not change that process.

Primary applications:
- tlo-ggi.py: Main GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI.
