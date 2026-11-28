# Build 743 execution

Cumulative follow-up for W1–W16; see detailed dispositions including limitations.

# TLO Build 739 Deep Review Remediation

**Source baseline:** v1.7 Build 741. **Build process:** v169 (unchanged).

## Execution plan and disposition

1. Build 742: address artist safety, accent matching, preview parity, operation locks and non-Latin output. Add real-catalog and CLI regressions.
2. Build 743: cumulative follow-up for recovery provenance/copy safety, duplicate cleanup reporting, configuration/GUI consistency, CLI behavior, and reviewed documentation contradictions.
3. Run the local application suite, targeted regressions, local Ruff and source hygiene for each iteration. Validate with the unchanged v169 release-readiness verifier, test companion process, and independently hash and verify each complete flat source archive. Hosted CI, signing, and native installer acceptance remain mandatory.

| Finding | Focus | Build | Disposition / limitation | Evidence |
|---|---|---|---|---|
| W1 | Artist attribution | 742 | Addressed for reproduced dated-show/container cases; root-limited generic path and primary-pattern lookups. Existing tags suppress ancestor-only generic matches. Other metadata heuristics retained. | Real catalog helper and full Inventory CLI regression |
| W2 | Accent matching | 742 | Addressed: query-side folding and compressed lookup; auxiliary matcher fallback; collision-safe exact-cache check. | Six shipped-catalog names and BJÖRK auxiliary query |
| W3 | Recovery originals in copied show | 743 | Addressed: same-volume holding outside show where possible; recursive work-tree exclusions for Tag Copy/Copy Requests and verification; Copy/Delete refuses nested recovery/work data. | Disc-level retention, real verified tag-copy and request-copy helpers, destructive refusal |
| W4 | Recovery provenance | 743 | Addressed for successful retention: run-scoped holder and relative names; durable CSV log and repair total; report scans both types. Inaccessible log/holder retains original bytes and shows warning; log may be unavailable on I/O failure. | Recorded keeper/held/copy paths and original-byte assertion |
| W5 | Dry Run rename mismatch | 742 | Addressed lexical rename-guard mismatch and ancestor-only warning. Preview remains provisional where real runtime corruption or destination conditions differ. | CLI preview versus actual rename safety rule |
| W6 | Operation lock | 742 | Addressed at public GUI Tag, CLI Tag and duplicate-cleanup entry points. Library helpers called directly by third-party code remain caller-managed. | Held-lock CLI subprocess test for both media tools |
| W7 | Stale bootlist after relocation | 743 | Mitigated: explicit moved-count/re-inventory warning and significant-change approval note. No automatic deletion of existing inventory rows; re-inventory required. | Existing move/log suite; warning source inspection |
| W8 | Main startup error invisible | 743 | Implemented GUI configuration error dialog with stderr fallback. | Native/windowed confirmation pending |
| W9 | Copy Requests default Yes | 743 | Implemented default-No for five consequential confirmations. | Source/lint and existing GUI contracts; display acceptance pending |
| W10 | Non-Latin bare-date bootlist | 742 | Addressed for artists whose ASCII representation is empty; blank Show/unidentified rather than bare date, existing mutation guard retained. | Explicit non-Latin postprocess regression |
| W11 | Explicit bracketed label | 743 | Addressed: unlabelled new roots prefer proposed name; registry identity remains authoritative, mismatches reported. | New unlabeled-root registration test; existing storage identity suite |
| W12 | Clipboard and generic result status | 743 | Implemented first-line 120-character preload and no automatic path query; status gives count. | Source/lint; native GUI acceptance pending |
| W13 | Conflicting home overrides | 743 | Addressed: disagreeing explicit and hidden aliases fail; no silent override; hidden alias alone still works. | Shared resolver plus legacy search/research/duplicate tests |
| W14 | CLI convention drift | 743 | Addressed listed home aliases, config error codes, read-only research, Tag and duplicate previews. Duplicate preview deliberately lists candidates only (actual FLAC integrity gates still apply). | CLI help/preview and no persistent writes tests |
| W15 | Conflicting active docs | 742/743 | Corrected reviewed radio/artist lookup wording, public tag example, home precedence, recovery/reporting, CLI and current release markers. Existing historical requirements and evidence retained separately. | Document version tests, source hygiene, v169 readiness, rendered requirements |
| W16 | Missing behavior coverage | 742/743 | Added targeted behavioral tests and made accent check mandatory. Native display/platform tests remain required. | Build 742 and 743 behavior tests; full local regression |

## Explicitly unchanged / pending

- No authoritative catalog edits: Saint Paul/St. Paul, NYC and region-name content require a separate catalog update. All three supplied SQLite masters are preserved byte-for-byte.
- Existing review-732 deferred refactoring, historical requirement atomization and native GUI/MSI/UNC acceptance remain deferred, not declared fixed by this review.
- No release has been published or promoted. These are complete source packages for your existing signed build pipeline, not Windows MSI or portable binary distributions.
- Local Python 3.12.14, pytest 9.2.0, Ruff 0.17.6 differ from pinned CI versions (Python 3.13.16, pytest 9.1.1, Ruff 0.16.10). No pinned or signed acceptance is claimed. Native Windows/display-only/FLAC encoder tests are skipped here; process-pool crash reproducer failed with local Unix-domain socket permission error and was deselected only in subsequent local runs. The test remains in every source bundle.
