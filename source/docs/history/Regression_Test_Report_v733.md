# Build 733 source-candidate regression report

TLO v1.7 Build 733 — NOT RELEASE-ATTESTED
Companion GitHub Build Process v169 (unchanged).
Build 732 GitHub run 46069821802: Linux 4 failures (3129 passed, 44 skipped); Windows stopped at its first failure (2169 passed, 71 skipped). The attached log contains no macOS failure report.
Root cause: a partial legacy catalog venue match (Crossroads) was treated as contradictory to the complete folder/header venue (Crossroads KC); native Windows path reconstruction dropped the drive root, breaking exact shorthand folder identity checks. The full legacy-catalog failure was reproduced locally with the supplied catalogs and a temporary venues.txt fixture containing Crossroads.
Corrections: retain physical drive/UNC/WSL paths in evidence; allow a catalog-derived fragment to expand only when the complete remote venue is independently present in the full folder tail and unlabeled setlist header, no explicit/independent place contradicts it, and a unique performance wins. No first-hit guessing or mutation on unresolved dates.
Focused date/shorthand tests: 36 passed, 8 subtests passed (includes 4 simulated Windows/UNC/WSL/POSIX path cases, all 8 date-conflict cases rerun with a deterministic legacy venue fixture, and 2 negative guards for explicit venue or unrelated longer name).
Original focused tests with actual SQLite catalogs plus temporary legacy venues.txt fixture: 22 passed, 8 subtests passed. Fixture removed from deliverable.
Full local application regression (Python 3.12, pinned pytest 9.1.1): 3153 passed, 37 skipped, 1 deselected, 1 warning, 8 subtests passed in 80.88s (0:01:20).
One existing process-pool crash test was deselected because local sandbox prevents required UNIX socket creation; it remains enabled in GitHub CI. Native Windows tests and graphical tests may skip locally.
Pinned Ruff 0.16.10: all checks passed. Local source hygiene and process release-readiness gates passed.
Unmodified Build Process v169: 194 passed, 14 skipped.
All three supplied SQLite catalogs remain byte-identical. No actual legacy venues.txt master was supplied; normal ArtistDB-Master staging remains required.
Build 732 auxiliary database search, album tag, folder rename spacing, and shortcut/package changes remain intact. No native Windows/macOS/Linux packaging, hosted CI, MSI upgrade or signing acceptance is claimed for Build 733.
