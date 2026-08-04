TLO Source and Utilities Bundle v359

Public application version: v1.3 Build 359
Source bundle label: v359

Build 359 summary
- Same-partition Tag Copy/Delete Original transfers are direct directory moves with no source-size totaling or post-move file-size comparison.
- Cross-partition Tag Copy/Delete Original transfers retain capacity preflight and per-file size verification before deleting the original.
- Tag Copy always verifies the copied relative-file map and file sizes, including copies made on the same partition.
- Advances the public application version to v1.3 and the source bundle to Build 359.
- Adds six focused behavioral regression tests for copy/move capacity and verification rules.

Current documentation files:
- TLO_Inventory_User_Manual_v359.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v359.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v359.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 358.

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
- SHA256SUMS_v359.txt records hashes for the files in this source bundle.

Validation status:
- 544 tests pass with GUI display support.
- 542 tests pass and 2 GUI tests skip explicitly without a display.
- Python compilation, local shell-script syntax, rendered-document inspection, and checksum verification are release gates for this bundle.
