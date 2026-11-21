# Build 698 — Non-destructive city and Search correction

## Implemented
- F3: Preserve a city verified by the external catalog when terminal technical qualifiers would otherwise hide it. Existing path/network geography is not replaced; no city inferred for unknown artists. Original qualifier is not deleted.
- F5: Normalize Latin accents and legacy transliterations for queries and stored Search text identically; leave non-Latin scripts intact.
- Carry forward full prior source, the historical change record, tests, requirements, User Manual and catalog. Companion Build Process v144 unchanged.

## Deferred and next
Build 699 will focus on remaining N3 ALBUM/Show/folder idempotence and F4 legitimate two-digit/foreign date and special Latin rename exemptions, without allowing uncertain renames. F6 run-scoped rename summary, S1-S7 messaging fixes, L9 Windows owner lock display, additional T3/T4 tests, and safe collection consolidation reversal remain open. Native Windows acceptance for Build 696 recovery and bundled FFmpeg for Build 697 are still pending.
