TLO Source and Utilities Bundle v414

Public application version: v1.4 Build 414
Source bundle label: v414

Build 414 summary
- Generic path artist scanning rejects an embedded Artist DB phrase when that occurrence is only the trailing city of a longer City, State/Region/Country location suffix; an exact artist directory with the same name remains eligible.
- Structured unlabeled headers may contain Artist / room-or-hall / named Venue / Location / Date without shifting the room/hall into the artist slot.
- Collaboration headers such as Chick Corea and Herbie Hancock are accepted when every component independently resolves uniquely in the Artist DB; unresolved or ambiguous components contribute no artist candidate.
- A single exact-count consecutive bare-number block is treated as track positions with Unknown Titles; the numeric values are never written as song titles.
- The reported Chick Corea and Herbie Hancock 2015-04-10 Kennedy Center case now resolves the collaboration artist, Kennedy Center venue, Washington, DC location, and eleven Unknown song titles.
- Public application version remains v1.4.
- GitHub Build Process v071 remains independently versioned and unchanged; its runtime build-number handling already supports Build 414.
- Build 413 change notes are archived in old-change-logs.zip.

Current documentation files:
- TLO_Inventory_User_Manual_v414.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v414.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v414.txt: changes introduced by this build.
- old-change-logs.zip: archived historical change notes through Build 413.

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
