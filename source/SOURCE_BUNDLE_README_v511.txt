TLO Source and Utilities Bundle v511

Public application version: v1.7 Build 511
Source bundle label: v511

Build 511 summary
- Changes New Copy Request input from Request File to Path(s).
- Path(s) uses the main GUI semicolon/optional-double-quote rules and repeated native-Windows drag/drop append behavior.
- Direct paths/volumes, ordinary request text, and .txt request-list files may be mixed in one expression.
- .txt list files are expanded once at request creation using blank/#/REM comment filtering; the resulting ordered aggregate is persisted so later Copy Request passes do not depend on the source files.
- Carries forward all Build 510/509 fixes, including the Ruff F541 correction and deleteReplacedFolders.bat/review-remediation behavior.

Current documentation files:
- TLO_Inventory_User_Manual_v511.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v511.docx: current consolidated TLO requirements specification.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v511.txt: changes introduced by this release build plus carried-forward recent history.
- old-change-logs.zip: archived historical TLO change notes and superseded verification/checksum artifacts.
- BUILD_VERIFICATION_v511.txt: local verification results for this source build.
- SHA256SUMS_v511.txt: SHA-256 manifest for all bundle files except the manifest itself.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- The GitHub Build Process remains independently versioned and distributed as its own separate package. The current process supplied with this work is v095; Build 511 does not change that process.

Primary applications:
- tlo-ggi.py: main Inventory GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI.
