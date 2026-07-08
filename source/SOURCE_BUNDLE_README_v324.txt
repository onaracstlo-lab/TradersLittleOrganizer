TLO Source and Utilities Bundle v324

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
- TLO_Inventory_User_Manual_v324.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v324.docx: current requirements/development document.

Bundle notes:
- Source bundle label: v324
- Public application version: v1.1 Build 324
- Internal source code version: v324

v324 fixes Add Shows incremental tagging so Tag in Place is honored for both normal readyForXfer processing and duplicate-resolution processing. Add Shows still ignores Tag Copy and does not create a second copy destination outside the readyForXfer/dups/staged workflow.

Packaged icon assets:
- icons/tlo-inventory-icon.png/.ico/.icns
- icons/tlo-search-icon.png/.ico/.icns
- icons/tlo-tag-icon.png/.ico/.icns


Update/download behavior:
- Check for updates downloads newer GitHub Release ZIP assets to the user's Downloads folder only.
- Auto update state is stored in TLOHome/update-settings.json and is honored by both the Inventory GUI and Search GUI at startup.
- TLO never unzips, installs, runs, or replaces files automatically.
- Platform-specific update ZIPs are preferred; when unavailable, the matching platform-specific complete ZIP is preferred before any generic fallback.
