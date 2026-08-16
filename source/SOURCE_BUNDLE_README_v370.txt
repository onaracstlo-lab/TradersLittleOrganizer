TLO Source and Utilities Bundle v370

Public application version: v1.3 Build 370
Source bundle label: v370

Build 370 summary
- Updates tlo-deleteDupes so copies are compared with one another as well as with unsuffixed folders.
- Forms content-equivalence clusters from same-parent candidate folders and keeps one representative per identical cluster.
- Prefers an unsuffixed keeper when available; otherwise keeps the lowest-numbered copy.
- If X differs from identical X (copy2) and X (copy3), X and copy2 remain while copy3 moves to duplicates.
- Applies FLAC repair independently within each identical content cluster.
- Extends deleteDupesMismatches.txt to record concise copy-to-copy mismatches as well as other candidate mismatches.
- Preserves Build 369 Research CLI/GUI behavior and all prior inventory/tagging/search behavior.
- GitHub Build Process v066 is recommended/required for Build 370 release packaging.

Current documentation files:
- TLO_Inventory_User_Manual_v370.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v370.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v370.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 369.

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
