# Build 735 / GitHub Build Process v169

Resolve the PowerShell case-insensitive HOME automatic-variable collision in the Windows MSI installation smoke test and opt-in acceptance diagnostics. Keep all signing, native install/uninstall and database/shortcut acceptance gates.

Build 734 run 46074831272 built and signed the MSI but failed before native install acceptance. Native release acceptance for Build 735 is pending; see current release notes, regression report and verification. Prior status is in docs/history/CURRENT_STATUS_through_v734.md.

All Build 734 Reverse and documentation changes remain. All three supplied SQLite catalogs remain unchanged; authoritative ArtistDB-Master staging includes venues.txt.

Local application regression: 3173 passed, 39 skipped, 1 deselected, 1 warning, 8 subtests passed in 82.80s (0:01:22). Build process v169 regression: 194 passed, 14 skipped in 2.26s. Native checks pending.
