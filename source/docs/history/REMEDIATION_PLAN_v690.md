# TLO Build 690 — incremental backlog remediation

Complete Build 689 source baseline retained; Build Process v143 unchanged. This separate source build addresses **L1** and **L2** only. The city catalog never parses a new date: it matches the exact source date span already selected by the inventory parser. Artist and complete date must be established independently, and conflicting or existing geography must not be overwritten. The parser treats Mars/Juli as ambiguous in month-only positions and when used month-first after a potential artist prefix; year-first and day-first dates remain accepted. Spaced-dash date ranges cannot produce cross-date hybrid candidates.

New executable tests: `tests/behavior/test_build690_date_city_safety.py` (9 checks). Other prior regressions remain. Name/structure/exact-size duplicate identity is unchanged, as are the Build 688 unset-MD5 rules and the Build 689 extended tokens/iterative tree scanner.

## Still open after Build 690

**L5** cross-device Add Shows verified copy/move publication; **L6** orphaned partial staging recovery; **L7** Search error presentation; **L9** Windows native lock-owner details; **L10** low-priority hygiene; **T3/T4** incremental behavioral coverage and replacement of weak source-inspection-only tests. Consolidation Reverse support remains a separately documented non-reversibility limitation. **L3/L8** remain accepted-design. Actual Windows, hosted CI, signing and Ruff lint are required before release acceptance. No older ZIPs are repurposed or modified.
