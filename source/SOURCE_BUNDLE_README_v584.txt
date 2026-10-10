TLO Source and Utilities Bundle v584

Public application version: v1.7 Build 584
Source bundle label: v584

Build 584 summary
- Application runtime behavior remains the same as hosted Build 583; the native
  Windows, Linux and macOS platform jobs all succeeded in Build 583.
- The Build 583 release assembly found an incorrect exclusion of the required
  THIRD_PARTY/FFmpeg LGPL corresponding-source directory under Windows onedir.
- Paired GitHub Build Process v116 fixes Python assembly and PowerShell ZIP
  validation, tests all 8 release ZIP variants with realistic legal assets,
  and verifies source provenance. Nothing bypasses signing, lint, or scans.
- This source build bumps the identity and current documentation consistently;
  Build 584 hosted compilation, signing and publishing are not yet attested.

Current documentation files:
- TLO_Inventory_User_Manual_v584.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v584.docx: current consolidated TLO requirements specification.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v584.txt: changes introduced by this release build plus carried-forward recent history.
- old-change-logs.zip: archived historical TLO change notes and superseded verification/checksum artifacts.
- DEAD_CODE_REVIEW_v564.txt: retained Build 564 dead-code review and removal rationale.
- VERSION_CONSOLIDATION_v565.txt: Historical version/test-churn consolidation record.
- BUILD_VERIFICATION_v584.txt: local verification results for this source build.
- SHA256SUMS_v584.txt: SHA-256 manifest for all bundle files except the manifest itself.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- The GitHub Build Process remains independently versioned and distributed as its own separate package. Use GitHub Build Process v116 for native release validation of Build 584.

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

See CHANGES_v584.txt and BUILD_VERIFICATION_v584.txt for the build-specific scope and validation record.

FFmpeg redistribution: Build native LGPL FFmpeg from pinned official source; include corresponding source and license under apps/<platform>/THIRD_PARTY/FFmpeg.
