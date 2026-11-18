# TLO v1.7 Build 682 — Conservative Remediation Plan and Execution Record

Baseline: application Build 681 deep review (2026-11-17), GitHub Build Process v141.
Outputs: new, independently numbered application source Build 682 and GitHub Build Process v142. Older ZIPs must remain unchanged.

## Release rule for every subsequent build

1. Assign the next unused application build number and a fresh ZIP filename; increment the separately versioned build process only when it changes. Never reuse or overwrite a prior archive.
2. Make the application source snapshot complete: programs, required build assets, source manifests, requirements, User Manual, test suite, and honest verification report. The master Artist DB is injected by the native build process; the source archive's placeholder DB does not constitute a runnable release.
3. Revise the normative requirements and the user-facing manual for behavior changed in that build. Review stale current-version text, command-line examples, filenames, removed programs, and current processes. Keep historical descriptions in clearly labeled history, not in current operating directions.
4. Execute regression tests, static checks, representative end-to-end flows, and the platform-specific CI tests. A passing source test is not evidence that an MSI installs, an EXE is signed, or macOS packaging succeeds.
5. Do not publish or promote a release if mandatory CI, package integrity, malware scan, signature verification, or available cross-platform acceptance gates fail. The process's `Verify-TLOReleaseReadiness.py` gate checks documentation content and explicit review-finding dispositions before build work; it does not substitute for runtime or native CI tests.
6. Record every deferred finding with a rationale. Do not label a deferred item fixed, and do not force unrelated low-risk refactors into safety-fix builds.

## Executed in Build 682

**Safety first (completed in source, with executable regressions):** H1 damaged FLACs can no longer be accepted solely on FFmpeg's null-decode exit code; H2 unset STREAMINFO MD5 is *unverifiable*, not proof of corruption; H3 Reverse history is archived before reinventory overwrites token logs. Also fixed M1 GUI human-answer timeout/close-is-Skip, M6 lossy CSV decoding, T1 pytest bytecode pollution, and T2 real-FLAC coverage.

**Explicitly deferred:** M2/M3 folder-name preservation/idempotency, M4/M5 Search View/expression fixes, M7 crash-replay semantics, M8 token expansion, and remaining L/T improvements. L3 name-and-exact-size duplicate identity is deliberately unchanged. L8 empty source Artist DB remains a documented build-process placeholder. The authoritative item-by-item list is `TLO_RELEASE_REMEDIATION.json`.

**Documentation (updated):** current Build 682 requirements DOCX, user manual RTF, and requirements catalog. Build Process v142 has its own updated requirements DOCX. The current documents were rendered and reviewed for layout and prior-build text, and current PowerShell examples were corrected to Build 682.

**Local tests:** The uninterrupted application pytest run passed: **2,747 passed, 6 skipped, 1 warning**; the same files also passed in nine isolated groups. Build-process v142 suite: **155 passed and 13 skipped**. An earlier short-limit attempt was interrupted; the subsequent uninterrupted run completed in 97.87 seconds. Ruff was unavailable locally. Platform-specific skipped tests, native Windows/macOS installers, signing, hosted GitHub Actions and release publication are **not attested** by these local results.

## Next conservative increments

- First prioritize non-lossy Rename Compliantly (M2) with date/city/source-qualifier fixtures, then idempotency (M3), with no renames when identification is uncertain.
- Separately address Search View identity (M4) and expression parsing (M5), then parallel crash replay (M7), each with end-to-end tests.
- Handle M8 and L/T improvements only when independently testable. Maintain the existing name+size duplicate identification contract unless explicitly changed by product requirements.

**Promotion status:** source and process ZIPs are local build inputs, not signed/native GitHub release artifacts. A hosted build must independently pass its required gates before publication or manual promotion.
