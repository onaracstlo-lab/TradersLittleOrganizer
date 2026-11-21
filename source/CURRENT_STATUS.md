# TLO v1.7 Build 713 — source candidate (NOT production-ready)

Companion GitHub Build Process **v155**. Build 713 retains Build 712 detailed read-only CLI preview and a preflight for colliding Show/ALBUM names in multi-root mutating runs, safe linked Manual Tweaks `--batch N` undo, Windows private undo-key ACLs, strict MSI signer-certificate continuity and a Windows native acceptance script. All original audio is preserved; undo never duplicates media payloads.

**Unverified/remaining:** Win11 standard-user C:\.tlo installation and ACL acceptance; actual MSI update/signing/rotation; mapped-drive and UNC mutation/recovery tests; hosted Windows/Linux/macOS CI; full pin-locked Ruff; remaining free-form location ambiguity, later-inventory selective undo, GUI control regrouping, uncommon tag/frame types and requirements-addenda consolidation. Source preflight is not native release attestation.

Read `REMEDIATION_PLAN_v713.md` for the exact disposition and `REGRESSION_RESULTS_v713.txt` for measured test results. Every correction uses a new ZIP and build number; do not overwrite prior packages.

Build 713 specifically fixes hosted CI test fixture portability (8 checksum-pinned synthetic audio samples) and the Windows byte-locked-file read assumption in the Copy Requests test. Full native signing and CI gates remain required.
