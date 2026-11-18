# Phase 1 — Application correctness and Windows helper hardening

TLO v1.7 Build 670; companion build process v135 (unchanged).

- Protect uniquely DB-matched artist aliases when interpreting *partial month/year* date tokens. Full dates and French/German/Italian support are retained.
- Resolve PowerShell and Windows Installer under the trusted OS API-reported System32 location, never the working-directory/PATH search order.
- Avoid unnecessary MSI-home registry writes and environment-change broadcasts.
- Stop assigning to the PowerShell automatic `$args` variable in the MSI update worker.
- Remove the duplicated Italian/French `novembre` dictionary entry and enable all Pyflakes `F` checks in Ruff config.
- Add Build 670 behavior regression tests; adjust older tests that enforced weaker legacy behavior.

Verification: focused contracts passed (156); source suite exercised in nine bounded groups. Earlier unpatched attempts identified outdated tests/report metadata and were corrected. Native Windows and macOS installer tests remain GitHub Actions acceptance gates. Full in-one-process suite not attested locally.
