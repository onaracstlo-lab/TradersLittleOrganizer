# TLO v1.7 Build 717 — source candidate (NOT production-ready)

Companion GitHub Build Process **v159**.

**Retained Build 716 CI staging fix:** local Build 715 halted after its wheel-pin verifier generated tlo_version.cpython-314.pyc within the temporary source snapshot. Build 716 disabled this bytecode creation, and process v158 also invokes local source Python checks with -B. Prior Build 715 Pygments/Ruff pin corrections and mandatory pip --require-hashes remain in force. CI run 44971626768 was the earlier Build 714 dependency-lock failure. Build 717 retains verified MSI handoff path continuity and Windows Installer source diagnostics; the standalone Build 685 updater cannot be retrofitted. Build 717 retains Build 712 detailed read-only CLI preview and a preflight for colliding Show/ALBUM names in multi-root mutating runs, safe linked Manual Tweaks `--batch N` undo, Windows private undo-key ACLs, strict MSI signer-certificate continuity and a Windows native acceptance script. All original audio is preserved; undo never duplicates media payloads.

**Unverified/remaining:** Win11 standard-user C:\.tlo installation and ACL acceptance; actual MSI update/signing/rotation; mapped-drive and UNC mutation/recovery tests; hosted Windows/Linux/macOS CI; full pin-locked Ruff; remaining free-form location ambiguity, later-inventory selective undo, GUI control regrouping, uncommon tag/frame types and requirements-addenda consolidation. Source preflight is not native release attestation.

Read `REMEDIATION_PLAN_v717.md` for the exact disposition and `REGRESSION_RESULTS_v717.txt` for measured test results. Every correction uses a new ZIP and build number; do not overwrite prior packages.

Build 713 fixed hosted CI fixture portability and the Windows byte-locked-file test assumption; these remain in Build 717. Build 715 corrected the Build 714 Pygments/Ruff dependency-lock typos; Build 716 corrected the subsequent local bytecode-contamination error. Full native signing and CI gates remain required.

**Retained Build 716 local staging remediation:** Run 715 failed before GitHub upload because the wheel verifier imported tlo_version without -B, leaving __pycache__/tlo_version.cpython-314.pyc in the prepared tree. Build 716 and Process v158 guard against source-local bytecode generation. Native CI/signing not attested.

**Build 717 / process v159:** Restores literal non-attested release-verification report fields required by retained Build 532–708 contract tests and prevents regression with a mandatory local/CI readiness preflight; this responds to hosted run 45067649844. Native acceptance remains pending.

**Local Build 717 validation:** separate app behavior (2,663 passed, 7 skipped), contracts/unit/integration (289 passed), process v159 (182 passed, 13 skipped), source hygiene/readiness passed. Native and Ruff remain required.
