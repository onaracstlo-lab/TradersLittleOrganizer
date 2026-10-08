TLO Source and Utilities Bundle v570

Public application version: v1.7 Build 570
Source bundle label: v570

Build 570 summary
- Update the historical signing-security test to validate both the source
  Windows build script and the alternate, safely generated script used by
  GitHub Build Process v111. Reject missing signer and verification controls.
- The test now validates security invariants, rather than obsolete exact
  Windows PowerShell variable names, with negative-mutation coverage.
- No production behavior changed. Build Process v111 remains unchanged.
- GitHub Actions run 37843682180 reported this one remaining Linux test error.

Current documentation files:
- TLO_Inventory_User_Manual_v570.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v570.docx: current consolidated TLO requirements specification.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v570.txt: changes introduced by this release build plus carried-forward recent history.
- old-change-logs.zip: archived historical TLO change notes and superseded verification/checksum artifacts.
- DEAD_CODE_REVIEW_v564.txt: retained Build 564 dead-code review and removal rationale.
- VERSION_CONSOLIDATION_v565.txt: Historical version/test-churn consolidation record.
- BUILD_VERIFICATION_v570.txt: local verification results for this source build.
- SHA256SUMS_v570.txt: SHA-256 manifest for all bundle files except the manifest itself.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- The GitHub Build Process remains independently versioned and distributed as its own separate package. Use the separate GitHub Build Process v111 package for this build.

Primary applications:
- tlo-main.py: Main GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagging CLI.
- tlo-search.py: collection search.
- tlo-research.py: Research application.
- tlo-reverse.py: reverse supported inventory/tagging operations.
- tlo-deleteDupes.py: duplicate comparison/repair utility.
- search-artist-db.py: artist database helper.
- setlistFM.py: setlist.fm helper.

Build and release utilities:
- createWindowsDist.ps1
- createLinuxDist.sh
- createMacOSDist.sh
- prepare_ffmpeg.py
- verify_build_environment.py
- audit_build_requirements.py
- requirements-audit.txt
- scan_release_artifacts.py

See CHANGES_v570.txt and BUILD_VERIFICATION_v570.txt for the build-specific scope and validation record.
