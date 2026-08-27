TLO Source and Utilities Bundle v413

Public application version: v1.4 Build 413
Source bundle label: v413

Build 413 summary
- Valid date-prefixed broadcast/show subsection headings with trailing context are treated as non-title boundaries rather than numbered tracks.
- Calendar validation is required before a numeric date-prefixed contextual line is promoted to a boundary.
- A provisional forward numbering jump is discarded when the next numbered row resumes the exact expected sequence; the reported 01-07, 30.10.1948, 08 case therefore keeps 08 as track 8.
- Confirmed large numbering gaps remain supported when later numbering reinforces them, such as 01, 02, 30, 31.
- A narrow lost-newline repair removes an attached dated subsection heading after an apostrophe-style duration without discarding the preceding song row.
- The reported Tadd Dameron Royal Roost 1948 case now selects all 14 numbered songs in order and never uses the 30.10.1948 broadcast heading as a title.
- Public application version remains v1.4.
- GitHub Build Process v071 remains independently versioned and unchanged; its runtime build-number handling already supports Build 413.
- Build 412 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v413.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v413.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v413.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 412.

Primary applications:
- tlo-ggi.py: main Inventory GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-deleteDupes.py: duplicate-folder analysis/holding-area cleanup utility.
- search-artist-db.py: Artist DB search utility.

Compatibility/source utility:
- setlistFM.py: thin command-line wrapper around production tlo_setlistfm_lookup; uses TLOHome rate-limit/quota state.

Build/release helpers:
- createWindowsDist.ps1
- createLinuxDist.sh
- createMacOSDist.sh
- scan_release_artifacts.py

Run the GitHub-compatible regression suite with:
  python -m pytest -q test_tlo_requirements.py

Run the categorized suite with:
  python -m pytest -q
