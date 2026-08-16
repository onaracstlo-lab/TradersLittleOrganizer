TLO Source and Utilities Bundle v369

Public application version: v1.3 Build 369
Source bundle label: v369

Build 369 summary
- Adds tlo-research.py and shared tlo_research_lib.py for field-aware lookup of meta*.log records and correlated comp*.log paths.
- Adds a Research button to the main Inventory GUI with an input dialog and separate text-results window.
- Research accepts an artist followed by a date, a venue, or a date.
- tlo-research uses shared TLOHome precedence: --myTLO, --TLOHome, then TLOHome environment variable.
- Adds tlo-research to all platform distributions and Windows shared-onedir packaging.
- Preserves Build 368 duplicate-cleanup mismatch logging and all prior behavior.
- GitHub Build Process v066 is recommended/required for Build 369 release packaging.

Current documentation files:
- TLO_Inventory_User_Manual_v369.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v369.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v369.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 368.

Primary applications:
- tlo-ggi.py: main Inventory GUI, including Research.
- tlo-gi.py: inventory CLI.
- tlo-gsi.py: collection Search GUI.
- tlo-research.py: log Research CLI.
- tlo-tag.py: standalone tagger.
- tlo-deleteDupes.py: duplicate-folder cleanup utility.
- search-artist-db.py: artist database search utility.

Test layout:
- pytest.ini: registered markers and categorized discovery configuration.
- test_tlo_requirements.py: Build Process compatibility entry point.
- tests/unit: isolated option, metadata, and log-output tests.
- tests/behavior: executable application, transfer, duplicate-cleanup/FLAC-repair, Research, and GUI regression tests.
- tests/integration: filesystem and multi-module workflow scenarios.
- tests/contracts: source, documentation, packaging, FAQ, and release-content assertions.

Recommended build process bundle: TLO_GitHub_Build_Process_v066.zip.
