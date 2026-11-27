TLO v1.7 Build 732 — NOT RELEASE-ATTESTED
Companion process v169.
Undated Artist - Album records write only String2 as the Album tag regardless of Artist in Album; lossless separator spacing is normalized for compliant renames. Main Search submenu opens Inventory, Artist, Cities or Venues with the clipboard query. searchAuxDBs searches the three installed SQLite catalogs read-only.
Build 731 date-conflict and earlier safety behavior retained.
Native Windows/Linux/macOS builds, MSI upgrade, signing and hosted tests are not attested.
The three supplied SQLite catalogs pass quick_check and are included unchanged. Legacy venues.txt is absent; retain normal ArtistDB-Master staging.

Completed: album tagging shared builder; conservative dash rename guard and actual inventory/Add Shows renames; clipboard launcher; auxiliary read-only SQL catalog lookups; executable build, package and shortcut reconciliation; current version and documentation tests.

TLO v1.7 Build 732 — NOT RELEASE-ATTESTED
Companion GitHub Build Process v169.
Local source regression: 3,139 passed, 37 skipped, 1 deselected (81.43 seconds; Python 3.12 / pytest 9.2.0). Eight subtests passed. The deselected existing process-pool crash test failed before reaching application logic because this environment denies UNIX socket creation; keep it enabled in native CI. Skips include absent Tk display, native Windows tests and missing standalone FLAC encoder.
Focused application/shortcut regression with pinned pytest 9.1.1: 26 passed, 1 skipped (Tk display required).
MSI source/packaging targeted regressions: 13 passed.
Pinned Ruff 0.16.10: application tree passed. Document hygiene and release readiness checks passed.
Real audio smoke: generated FLAC and MP3, wrote and reread Artist=Allman Brothers Band and Album=Eat a Peach with Artist in Album enabled.
Real database quick_check: all three passed (49,545 artist records / 120,421 terms; 12,051 cities; 70,215 venue name records). Supplied catalogs included byte-for-byte. Legacy venues.txt remains an external required ArtistDB-Master input.
Native MSI generated shortcut and install/uninstall assertions added. Native Windows/macOS/Linux build, hosted full tests, display interaction, signing and MSI upgrade have NOT been executed/attested here.
The old search-artist-db executable is not included in new payloads. Manual overlay ZIP upgrades may leave an already-installed obsolete executable or .app; remove only that old application after upgrading, not TLOHome or databases.
