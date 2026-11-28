# Build 740 remediation evidence correction

Correct source-owned remediation evidence: match the packaged build number, keep the exact 25 Build 681 review dispositions, and preserve STORAGE736 and RENAME737 in supplemental_findings. Source hygiene now rejects stale identity, invalid/missing dispositions and contaminated finding namespaces. The independently versioned Process v169 gate is unchanged.

The existing Build 732 review open items remain unchanged. Prior Build 739 remediation follows for historical context:

# Build 739 remediation follow-up

Baseline: Build 738 tested safety candidate; findings from independent Build 732 review.

- B5: auxiliary artist variants and compressed matching; city-region guidance.
- B7: recorded MD5 compatibility and retain verified originals on the same volume; preserve existing rollback safeguards.
- B6/R10: allow empty alias records with valid artist and terms tables; remove redundant tagger exception/rethrow.
- U1/U4/R1: auxiliary database radio group, status label and reusable matches window; shared TLOHome precedence and GUI argument errors.
- U3: existing explicit upgraded-access preference and CLI option suffice; duplicate secret optional; reject mismatched legacy values.
- D5: deduplicate exact historic lines; archive retired CSV-era integration and migration notes.
- CI: fail when Tkinter is absent under CI; hosted v169 already checks Tk availability.

Deferred: Main GUI radio/layout redesign (U1/U2), packaging icon changes (U4), broad naming and internal module/refactoring (D7/U5/R3–R8/R11), complete historical requirements atomization and test mapping (D2), full native acceptance (including Windows MSI share-mode behavior, UNC testing, GUI checks). Prior historical incident matrices and compatibility entry point retained for existing consumers.
