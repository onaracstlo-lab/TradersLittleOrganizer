TLO Source and Utilities Bundle v512

Public application version: v1.7 Build 512
Source bundle label: v512

Build 512 summary
- Renames the main GUI title bar to TLO Main GUI and the bold heading to Traders Little Organizer™ Main.
- Sets automatic Max Workers from the selected Performance Mode: gentle 1, balanced up to 2, fast up to CPU count, extreme up to min(4 x CPU count, 64).
- Selecting a different Performance Mode resets Max Workers to that mode's automatic ceiling; manual positive ceilings remain supported afterward.
- Copy Request direct paths ending in * expand once at request creation. c:\TLO* selects matching top-level directories; c:\TLO\* selects immediate child directories without copying c:\TLO itself.
- Wildcard expansions are persisted with the Copy Request so later passes do not re-expand them.
- Carries forward Build 511 mixed Path(s)/.txt aggregation and all Build 510/509 fixes.

Current documentation files:
- TLO_Inventory_User_Manual_v512.rtf: current end-user manual.
- TLO_Inventory_Requirements_Working_v512.docx: current consolidated TLO requirements specification.
- TLO-FAQ.txt: current frequently asked questions.
- CHANGES_v512.txt: changes introduced by this release build plus carried-forward recent history.
- old-change-logs.zip: archived historical TLO change notes and superseded verification/checksum artifacts.
- BUILD_VERIFICATION_v512.txt: local verification results for this source build.
- SHA256SUMS_v512.txt: SHA-256 manifest for all bundle files except the manifest itself.

GitHub Build Process separation:
- No GitHub Build Process artifact is included in this source bundle.
- The GitHub Build Process remains independently versioned and distributed as its own separate package. The current process supplied with this work is v095; Build 512 does not change that process.

Primary applications:
- tlo-ggi.py: Main GUI.
- tlo-gi.py: inventory CLI.
- tlo-tag.py: standalone tagger CLI.
- tlo-gsi.py: collection search.
- tlo-research.py: comp/meta log Research CLI.
- tlo-reverse.py: standalone folder-operation reversal CLI.
