TLO Source and Utilities Bundle v367

Public application version: v1.3 Build 367
Source bundle label: v367

Build 367 summary
- Changes tlo-deleteDupes disposal from Recycle Bin/Trash to a folder named duplicates at the root of the partition/filesystem containing the Input Path.
- Creates the partition-root duplicates folder when needed and moves qualifying duplicates as complete directory trees.
- Excludes the holding folder from duplicate discovery when the search includes the partition root.
- Preserves existing destination entries; name collisions use a (moved N) suffix rather than overwriting.
- Preserves Build 366 duplicate identification, alphabetical-master rules, recursive name/structure/size comparison, FLAC validation and repair, deletedDirs.txt logging, and Ctrl-C cleanup.
- Removes the tlo-deleteDupes send2trash runtime/package dependency; imageio-ffmpeg remains required for FLAC decode validation.
- GitHub Build Process v058 is recommended for Build 367.

Current documentation files:
- TLO_Inventory_User_Manual_v367.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v367.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v367.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 366.

Test layout:
- pytest.ini: registered markers and categorized discovery configuration.
- test_tlo_requirements.py: Build Process compatibility entry point.
- tests/unit: isolated option, metadata, and log-output tests.
- tests/behavior: executable application, transfer, duplicate-cleanup/FLAC-repair, and GUI regression tests.
- tests/integration: filesystem and multi-module workflow scenarios.
- tests/contracts: source, documentation, packaging, FAQ, and release-content assertions.

Recommended build process bundle: TLO_GitHub_Build_Process_v058.zip.

Source bundle notes:
- The source bundle is intended for controlled builds and development.
- Use the numbered distribution scripts for local packaging or the recommended GitHub build process for platform artifacts.
- SHA256SUMS_v367.txt records hashes for the files in this source bundle.

Build 367 validation:
- 636 tests passed through the GitHub CI compatibility entry point with a virtual display.
- 634 tests passed and 2 GUI tests skipped without a display.
- Requirements and User Manual renders were visually inspected.
- The packaged SHA256SUMS_v367.txt manifest is verified after clean extraction.
