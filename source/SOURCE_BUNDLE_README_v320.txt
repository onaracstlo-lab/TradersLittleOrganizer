TLO Source and Utilities Bundle v320

This source bundle contains the TLO Inventory source tree and companion build utilities.

Important files:
- tlo-ggi.py: main inventory GUI.
- tlo-gi.py: command-line inventory entry point.
- tlo-tag.py: standalone tagger entry point.
- tlo-gsi.py: search GUI.
- createWindowsDist.ps1: Windows distribution helper.
- createLinuxDist.sh: generic Linux distribution helper.
- createMacOSDist.sh: macOS distribution helper.
- TLO-FAQ.txt: FAQ displayed from the main GUI hamburger menu.
- TLO_Inventory_User_Manual_v320.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v320.docx: current requirements/development document.

Bundle notes:
- Source bundle label: v320
- Public application version: v1.0 Build 320
- Internal source code version: v320

v320 adds packaged Windows .ico and macOS .icns icon assets so native builds can pass platform icon files directly to PyInstaller without repeated build-time icon conversion.

Packaged icon assets:
- icons/tlo-inventory-icon.png/.ico/.icns
- icons/tlo-search-icon.png/.ico/.icns
- icons/tlo-tag-icon.png/.ico/.icns
