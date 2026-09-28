TLO Source and Utilities Bundle v510

Public application version: v1.7 Build 510
Source bundle label: v510

Build 510 summary
- Corrects Ruff F541 in tests/behavior/test_build465_cross_platform_collection_recovery.py by removing an unnecessary f-string prefix from a raw Windows path literal.
- No application/runtime behavior changes from Build 509.
- Carries forward all Build 509 review-remediation behavior, including deleteReplacedFolders.bat generation and the related safety fixes.

Current documentation files:
- TLO_Inventory_User_Manual_v510.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v510.docx: current consolidated TLO requirements specification.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v510.txt: changes introduced by this release build plus carried-forward recent history.
- old-change-logs.zip: archived historical TLO change notes and superseded verification/checksum artifacts.
- BUILD_VERIFICATION_v510.txt: local verification results for this source build.
- SHA256SUMS_v510.txt: SHA-256 manifest for all bundle files except the manifest itself.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- The GitHub Build Process remains independently versioned and distributed as its own separate package. The current process supplied with this work remains v094; Build 510 does not change that process.

Primary applications:
- tlo-ggi.py: main Inventory GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI.
