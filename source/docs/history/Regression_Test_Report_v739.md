# Build 739 source regression

TLO v1.7 Build 739 — NOT RELEASE-ATTESTED
Source regression (Linux, Python 3.12.14, pytest 9.2.0): 3234 passed, 39 skipped, 1 deselected, 2 warnings, 8 subtests passed in 91.18s (0:01:31)
Companion Build Process v169: 194 passed, 14 skipped, 1 warning in 2.02s
Local Ruff: PASS (ruff 0.17.6); hosted pinned toolchain remains mandatory.
Six additional Build 739 regression cases; current requirements and catalog contracts passed.
Full suite excludes test_process_pool_crash_retains_completed_groups (restricted environment). 39 skips reflect unavailable Tk display, FLAC fixture encoder and native Windows-only behavior. Two warnings: pytest AnyIO deprecation and intentional duplicate ZIP test.
DOCX (115 pages) and RTF (39 pages) rendered; selected changed pages visually inspected, not every page.
All three supplied SQLite masters verified byte-for-byte identical to Build 737. Hosted v169 stages all four authoritative masters, including venues.txt from ArtistDB-Master.
Native Windows/macOS/WSL, signed binaries, MSI install/uninstall/upgrade, UNC share and GUI acceptance NOT ATTESTED. Source bundle only.

See REMEDIATION_PLAN_v739.md for remaining work.
