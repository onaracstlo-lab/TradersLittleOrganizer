# TLO Build 696: Windows recovery and native regression diagnostics

## Executed changes
- F2: Replace unsafe Windows `os.kill(pid, 0)` staging recovery probe with Win32 OpenProcess / GetExitCodeProcess, conservatively treating unknown owners as active. Linux owner checks remain unchanged.
- GitHub Actions run 44439995201: its Windows pytest job failed **before signing**; signing diagnostics were misleading. Build Process v144 uses `pytest -x --tb=short -ra`, and runs signing diagnostics only after telemetry initialization. Actual failed test identity was unavailable in the truncated provided log.
- Build 696 contains all source files, requirements, RTF manual, current catalog, regression fixtures and manifest. No historical ZIP overwritten.

## Open Build 694 review items
F1 (damaged unset-MD5), N3 (Album rename idempotence), F3 (city with trailing qualifiers), F4 (legitimate renamed date formats), F5 (accent Search), F6 (rename summary per run), S1-S7, L9 Windows lock-owner and collection consolidation Reverse remain to be addressed in independent increments. F2 native Windows test remains pending until hosted CI runs.

## Release status
Source release candidate only; native Windows pytest, packaged FFmpeg, MSI, scans, signatures, macOS/Linux builds and publication are not attested here.
