TLO Source and Utilities Bundle v325

This bundle contains the source files and utility scripts for Traders Little Organizer (TLO).

Current version
---------------
- Source bundle label: v325
- Public application version: v1.1 Build 325
- Internal source code version: v325

Build 325 summary
-----------------
v325 removes the editable TLOHome input rows from both GUI applications:
- tlo-ggi.py Inventory GUI
- tlo-gsi.py Search GUI

TLOHome resolution is unchanged and remains launch-time only:
1. --myTLO, when supplied, wins first.
2. --TLOHome is next.
3. The TLOHome environment variable is used last.

The resolved TLOHome is used for inventory configuration, search, Add Shows, Tag, FAQ, and GitHub update settings for the whole app session. To change TLOHome, relaunch the app with a different shortcut, command-line argument, or environment variable value.

Key included files
------------------
- TLO_Inventory_User_Manual_v325.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v325.docx: current requirements/development document.
- TLO-FAQ.txt: FAQ used by the Inventory GUI Help menu.
- test_tlo_requirements.py: regression tests.
- tlo-ggi.py: Inventory GUI.
- tlo-gsi.py: Search GUI.
- tlo-gi.py: command-line inventory entry point.
- tlo-tag.py: standalone tagger entry point.
- tlo_github_updates.py: GitHub update checking and download-only updater support.

Validation
----------
- Python compile check passed for all Python source files.
- Regression test suite passed: 416 passed.
