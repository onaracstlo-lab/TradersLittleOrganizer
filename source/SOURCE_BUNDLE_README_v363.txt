TLO Source and Utilities Bundle v363

Public application version: v1.3 Build 363
Source bundle label: v363

Build 363 summary
- Adds tlo-deleteDupes.py as a console main for safely cleaning structurally duplicate copy-suffixed directories.
- Requires one fully qualified Input Path and uses the same --TLOHome, hidden --myTLO compatibility argument, and TLOHome environment-variable resolution logic as the other mains.
- Searches recursively for sibling directories ending in (copyN) or (copy N), case-insensitively.
- Moves only a copy-suffixed folder whose unsuffixed sibling has the same complete relative directory structure, relative file names, and file sizes. Empty nested directories are part of the comparison.
- The duplicate-cleanup comparison intentionally does not hash file bytes or use timestamps/ownership/permissions.
- Uses send2trash so matching copy folders go to the platform Recycle Bin/Trash rather than being permanently deleted. The unsuffixed original is never moved.
- Appends every successfully trashed copy folder's full original path to TLOHome/deletedDirs.txt.
- Ctrl-C stops further work, closes the log through normal unwinding, and returns status 130.
- Adds tlo-deleteDupes to Windows onefile/onedir, Linux, and macOS distributions.
- Advances the GitHub build process to v056 to install/package send2trash and validate the new executable in release assets.

Current documentation files:
- TLO_Inventory_User_Manual_v363.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v363.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v363.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 362.

Test layout:
- pytest.ini: registered markers and categorized discovery configuration.
- test_tlo_requirements.py: Build Process v056 compatibility entry point.
- tests/unit: isolated option, metadata, and log-output tests.
- tests/behavior: executable application, transfer, duplicate-cleanup, and GUI regression tests.
- tests/integration: filesystem and multi-module workflow scenarios.
- tests/contracts: source, documentation, packaging, and release-content assertions.

Recommended build process bundle: TLO_GitHub_Build_Process_v056.zip.

Source bundle notes:
- The source bundle is intended for controlled builds and development.
- Use the numbered distribution scripts for local packaging or the recommended GitHub build process for platform artifacts.
- SHA256SUMS_v363.txt records hashes for the files in this source bundle.

Validation status:
- 595 tests pass with GUI display support.
- 593 tests pass and 2 GUI behavior tests skip explicitly without a graphical display.
- The Build Process v056 compatibility entry point passes all 595 tests under xvfb-run.
- See CHANGES_v363.txt for the complete Build 363 validation summary.
