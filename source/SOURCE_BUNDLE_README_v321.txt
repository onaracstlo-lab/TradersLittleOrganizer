TLO Source and Utilities Bundle v321

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
- TLO_Inventory_User_Manual_v321.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v321.docx: current requirements/development document.

Bundle notes:
- Source bundle label: v321
- Public application version: v1.0 Build 321
- Internal source code version: v321

v321 rebuilds the packaged Windows .ico assets as DIB/BMP-based multi-image ICO files and strengthens Windows EXE icon verification so GitHub-built executables must contain the exact packaged custom icons.

Packaged icon assets:
- icons/tlo-inventory-icon.png/.ico/.icns
- icons/tlo-search-icon.png/.ico/.icns
- icons/tlo-tag-icon.png/.ico/.icns
