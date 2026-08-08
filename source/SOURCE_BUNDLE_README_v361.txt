TLO Source and Utilities Bundle v361

Public application version: v1.3 Build 361
Source bundle label: v361

Build 361 summary
- Fixes non-compliant commercial-release names so a leading (YYYY) or bare YYYY release year is recognized only when it is exactly one four-digit 19xx/20xx component followed by Artist - Album.
- Commercial-release years are not assigned to DATE and are omitted from Artist - Album show names.
- Removes one redundant resolved-artist prefix from album tails, so Rod Stewart - Rod Stewart - Camouflage becomes Rod Stewart - Camouflage.
- Ensures Tag Copy and Copy/Delete Original operate on the complete identified folder tree, including nested non-music files and empty subfolders.
- Real copies verify relative file paths, file sizes, and descendant directory structure. Same-partition Copy/Delete Original remains a size-free directory rename/move.
- Adds behavioral regression tests for commercial-release parsing and complete recursive transfers.

Current documentation files:
- TLO_Inventory_User_Manual_v361.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v361.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v361.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 360.

Test layout:
- pytest.ini: registered markers and categorized discovery configuration.
- test_tlo_requirements.py: Build Process v054 compatibility entry point.
- tests/unit: isolated option, metadata, and log-output tests.
- tests/behavior: executable application, transfer, and GUI regression tests.
- tests/integration: filesystem and multi-module workflow scenarios.
- tests/contracts: source, documentation, packaging, and release-content assertions.

Recommended build process bundle: TLO_GitHub_Build_Process_v054.zip.

Source bundle notes:
- The source bundle is intended for controlled builds and development.
- Use the numbered distribution scripts for local packaging or the recommended GitHub build process for platform artifacts.
- SHA256SUMS_v361.txt records hashes for the files in this source bundle.

Validation status:
- 567 tests pass with GUI display support.
- 565 tests pass and 2 GUI tests skip explicitly without a display using the Build Process v054 compatibility entry point.
- Python compilation, requirements DOCX render inspection, manual RTF round-trip/render inspection, and checksum verification passed.
