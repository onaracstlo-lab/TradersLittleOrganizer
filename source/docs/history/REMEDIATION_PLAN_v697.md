# Build 697 — FLAC safety remediation (F1)

## Fix
Build 694 deep review verified that FFmpeg can return zero for an incomplete FLAC when the stored MD5 and total sample count are both unset. Stop treating such decoder results as verified complete. When both fields are zero, the Deep Audio Check returns UNVERIFIABLE, retains the file and suppresses mutations. Real codec diagnostics on success also prevent a positive verdict. A non-access tag-write failure is still corruption; tag-only mode remains unchanged. The stricter deleteDupes rule remains.

## Tests
Real pipe-produced FLACs, truncation and bit-flip fixtures, known-total unset-MD5 compatibility, and tag-only mode. Native FFmpeg 9.0.2 behavior still needs hosted validation.

## Outstanding
N3 Album idempotence, F3 city lost before qualifiers, F4 date/transliteration guard, F5 accent Search, F6 cross-volume summary counts, S1-S7, L9 Windows lock owner, collection consolidation reversal and targeted wider test coverage remain deferred. Build Process v144 is unchanged.

## Remaining backlog — next independent increments

1. **Build 698 (non-destructive metadata/search corrections):** F3 city before qualifier, F5 accent-neutral search, F6 run-scoped rename counts. Preserve existing duplicate and audio rules. Tests require actual inventory/tag/search and two-volume logging fixtures.
2. **Build 699 (rename idempotency and guard):** N3 stable ALBUM, Show and folder across rename/tag-only/re-inventory; F4 legitimate short dates, ordinal dates and transliterations. Skip when identification remains uncertain. Five-run fixtures and release tests mandatory.
3. **Later optional low-risk increments:** S1 non-UTF-8 user-friendly path; S2 malformed search close parenthesis; S3 unknown title spelling; S4 tagger log search-path header; S5 recovery dry-run count; S6 provisional duplicate preview; S7 Add Shows error wording. Test each as behavior rather than source inspection alone.
4. **Native/platform acceptance:** L9 Windows lock-owner display and any outstanding platform-specific installer, MSI, signed packaging, hosted FFmpeg. Only native Windows can attest Windows API behavior. Collection-consolidation reversal requires a separate conservative safety design; no automatic reversal without journal evidence.

Each new source build must have a unique immutable filename, full contents, current requirements/manual/catalog, new regression tests, release records, SHA256 and native lint/gates when available. No unverified finding is to be silently marked fixed.
