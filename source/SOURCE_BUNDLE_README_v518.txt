TLO Source and Utilities Bundle v518

Public application version: v1.7 Build 518
Source bundle label: v518

Build 518 summary
- Replaces the packaged inventory-app icon artwork with the supplied TLO Main icon while preserving the existing tlo-inventory-icon asset names.
- Regenerates the required packaged inventory icon resources as PNG, Windows ICO, and macOS ICNS files.
- Includes the supplied source artwork as icons/tlo-main-icon.png for traceability alongside the compatibility-preserved tlo-inventory-icon assets.
- Carries forward Build 517 source-publication hygiene, Build 516 update-check ordering, Build 515 search/setlist filename alignment, and the Build 513 independently signed update trust model.

Update-signing trust anchor
- tlo_update_trust.py intentionally contains an empty update-signing trust anchor in the source bundle.
- Run-TLO-GitHub-Build.ps1 v098 requires the locally generated public-key JSON and injects that public key into the transient source snapshot before executable builds.
- The private update-signing key must never be added to this bundle or GitHub.

Current documentation files:
- TLO_Inventory_User_Manual_v518.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v518.docx: current consolidated TLO requirements specification.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v518.txt: changes introduced by this release build plus carried-forward recent history.
- old-change-logs.zip: archived historical TLO change notes and superseded verification/checksum artifacts.
- BUILD_VERIFICATION_v518.txt: local verification results for this source build.
- SHA256SUMS_v518.txt: SHA-256 manifest for all bundle files except the manifest itself.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- The GitHub Build Process remains independently versioned and distributed as its own separate package. The current process supplied with this work is v098; Build 518 does not change that process.

Primary applications:
- tlo-ggi.py: Main GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI.
