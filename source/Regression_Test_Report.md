# Regression results

TLO v1.7 Build 743 — NOT RELEASE-ATTESTED

Final cumulative local full application regression: 3270 passed, 39 skipped, 1 deselected, 2 warnings, 8 subtests passed in 124.71s. Focused follow-up: 102 passed, 2 display skips; new follow-up tests: 11 passed. Raw logs in docs/validation.

Companion Process v169 local regression: 194 passed, 14 skipped, 1 warning in 2.25s. Unmodified v169 readiness verifier: PASS. Source hygiene: PASS. Local Ruff 0.17.6: PASS. Local toolchain Python 3.12.14 / pytest 9.2.0 differs from required pinned CI toolchain.

The one process-pool crash test failed before remediation on this environment because Unix-domain socket creation is restricted (PermissionError / EOFError); it is locally deselected subsequently, unchanged and required in applicable native CI. The remaining skips concern graphical display, native Windows and fixture FLAC encoder availability. Native Windows/Linux/macOS, pinned lint, scanning, signing, MSI installation/uninstallation and release acceptance remain mandatory.

## Documentation
115 rendered DOCX pages; 26 pixel-identical to Build 741 and 89 changed due to text reflow and version updates. Changed-page overview inspected, selected substantive pages inspected at full resolution. No redesign; native Word/RTF display not attested.
