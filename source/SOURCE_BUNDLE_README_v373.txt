TLO Source and Utilities Bundle v373

Public application version: v1.4 Build 373
Source bundle label: v373

Build 373 summary
- Non-compliant artist-tag resolution rejects unmatched numeric-only track identifiers and date-like ARTIST/ALBUMARTIST values instead of deferring them as artist fallbacks; later sampled tag values remain eligible.
- DB-backed numeric artist names remain valid.
- Path artist fallback now tries exact components, simple Last, First reversal, then the longest Artist-DB-backed phrase embedded in a descriptive path component.
- The selected setlist filename may provide an artist-only DB-backed fallback after path and explicit setlist-content artist evidence fail, but it is never used for date, venue, or location metadata.
- The Duke Ellington / Ellington, Duke failure pattern is covered by regression tests.
- Public application version remains v1.4; bundle/build number advances to 373.
- GitHub Build Process v067 remains recommended/required; no packaging dependency changed in Build 373.

Current documentation files:
- TLO_Inventory_User_Manual_v373.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v373.docx: current requirements/development document.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v373.txt: release changes and preserved behavior.
- old-change-logs.zip: archived historical change notes through Build 370.

Primary applications:
- tlo-ggi.py: main Inventory GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-deleteDupes.py: duplicate-folder analysis/holding-area cleanup utility.
- search-artist-db.py: Artist DB search utility.

Research implementation:
- tlo_research_lib.py provides the shared CLI/GUI Research engine.
- Research date recognition delegates to the canonical Inventory date parser in tlo_phase23_v2.py so date behavior stays synchronized.

Build/release helpers:
- createWindowsDist.ps1
- createLinuxDist.sh
- createMacOSDist.sh
- scan_release_artifacts.py

Run the regression suite with:
  python -m pytest -q test_tlo_requirements.py
