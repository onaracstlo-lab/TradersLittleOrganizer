# TLO Build 726 / GitHub Build Process v168

**Status: local source candidate, not a production release or native build attestation.**

## Scope and tests

| Test stage | Result |
|---|---|
| Original Build 725 full application suite | 3,046 passed; 7 skipped |
| Original standalone venue matcher | 21 passed (70 subtests) |
| Integrated Build 726 full application run before final corrective patch | 3,062 passed; 3 failed; 7 skipped |
| Targeted rerun after all three fixes, including documentation and venue matching | 52 passed |
| Final new venue integration and packaging suite (includes two newly added tests) | 21 passed |
| Final Build Process v168 local suite | 192 passed; 14 skipped |
| Application source-document metadata and AST test import-use hygiene | passed (not Ruff) |

The three original candidate failures were two valid regional spelling flips (Calvin Theatre and Lincoln Theater) and two stale RTF metadata fields caught by one test. All affected tests were rerun successfully after correction; the entire application suite was **not** rerun from scratch after the corrective patch and the last two packaging tests. No previous folder-name expectations were weakened. The legacy tests were checked as written; many use isolated database fixtures, so they do not establish behavior with the real venue catalog on every input. The separate paired CSV reports every changed name in the 17 deliberately paired real-catalog tests, with the city DB held constant; it does not claim exhaustive instrumentation of every internal name emitted by the legacy suite. Five changed, twelve unchanged. Two rejected changes were kept out of the final implementation.

The application suite skipped six native Windows tests and the unavailable pinned Ruff check. Process skips are platform/tool dependent. Native Windows/Linux/macOS GitHub Actions, real MSI upgrade, signing, release publication, and scans are not attested. Both requirements DOCX files rendered successfully (108 and 29 pages); final page-by-page full-resolution visual review was not completed. This is a source package, not an installer.

## Decisions and limitations

- Full-span, context-supported matches only. No arbitrary substring/fuzzy truncation. Preserve raw compliant suffixes, artist/date, existing source selection, numbered rooms and historical venue names. Preserve source spelling for sole theatre/theater or centre/center differences. A recognized venue can be retained verbatim when the catalog display is unsafe. Existing casing behavior can still affect acronyms not on TLO's existing allowlist.
- Keep venues.txt and all prior non-catalog location/venue/online fallbacks. The catalog is optional at runtime, but required in complete/database-inclusive releases. Four managed database files: artists.sqlite, venues.txt, cities.sqlite, venues.sqlite. Database-free update ZIPs remain supported.
- The supplied venue SQLite is unchanged: 70,215 name rows and 107 location rows; quick_check ok; SHA-256 e4be8ba05cab94dd8159f381ff4db883aa0fe118e08a0866deb1aafbc5260bdc. City SQLite is byte-identical to Build 725.
- Source bundle has the original zero-byte artists.sqlite placeholder and does not contain the real venues.txt. Copy the supplied venues.sqlite into ArtistDB-Master next to the existing three physical masters before invoking the build. Use your existing real artists.sqlite and venues.txt. Do not replace a live inventory or promote this source candidate as production.
- No user music files were accessed or mutated. Historical logs can support read-only projection of already selected venue fields, but cannot reproduce original media tags, setlists, filesystem structures, duplicate actions, source precedence, online responses or blank-venue recovery. A projected change is not a verified real-world rename.
- Recommendation: run normal native CI, then test inventory-only against copies or a small non-destructive fixture set. Keep rename/tag/delete operations off while inspecting differences.
