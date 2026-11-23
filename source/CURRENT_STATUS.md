# TLO v1.7 Build 721 — source candidate (NOT production)

Build 721 / Process v163: The Build 720 native Windows/Linux/macOS pipeline assembled and hash-bound local release artifacts, but public source publication failed in three attempts when Windows Git could not write loose objects under C:\TLO-GitHub-Build. The release helper now uses packed shallow Git fetch and short per-user temporary working directories, with controlled fallback. Signed source commits, verified annotated tags, immutable production releases and SHA-256/asset signing remain mandatory. Application inventory/tagging functionality is unchanged. Native Windows publication acceptance is pending.

**Verified locally:** 3,015 application passes, 7 skips; 190 process passes, 14 skips; six independent behavior shards green; ready/hygiene checks pass. Native Windows publication is not verified.

**Retained functionality:** Build 719 mixed-case city/venue display fix, Build 720 Ruff F841 correction, no new inventory/tag semantics.

---

### Earlier build context (archival)

Build 721: removed unused wholly_upper assignment, preserving Build 719 display normalization; Ruff CI and native acceptance pending.

**Retained Build 719 display remediation:** compliant/path-only String2 is not split into city/venue fields. Final display normalization fixes uppercase city fragments embedded in raw mixed-case venue text (e.g., Calvin Theatre NORTHAMPTON, MA), retains terminal US state codes, and keeps the original path/setlist/evidence. Build 721 local application 3,017 passed, 7 skipped; process 188 passed, 13 skipped. Native release acceptance pending.

Retained Build 719: Compliant/path-only String2 retains the full venue+city tail; its display normalization corrects embedded uppercase place words and terminal region codes only. No source file, artist, tag evidence, or lookup precedence is changed.

Retained Build 718 (2026-11-22): Apply conservative proper capitalization only to detected all-uppercase venue/city/location output at the final inventory metadata boundary; retain exact source case and intentional mixed case. Tests cover setlist headers and no-setlist folders. Hosted native CI pending.

# TLO v1.7 Build 721 — source candidate (NOT production-ready)

Companion GitHub Build Process **v163**.

**Retained Build 716 CI staging fix:** local Build 715 halted after its wheel-pin verifier generated tlo_version.cpython-314.pyc within the temporary source snapshot. Build 716 disabled this bytecode creation, and process v158 also invokes local source Python checks with -B. Prior Build 715 Pygments/Ruff pin corrections and mandatory pip --require-hashes remain in force. CI run 44971626768 was the earlier Build 714 dependency-lock failure. Build 721 retains verified MSI handoff path continuity and Windows Installer source diagnostics; the standalone Build 685 updater cannot be retrofitted. Build 721 retains Build 712 detailed read-only CLI preview and a preflight for colliding Show/ALBUM names in multi-root mutating runs, safe linked Manual Tweaks `--batch N` undo, Windows private undo-key ACLs, strict MSI signer-certificate continuity and a Windows native acceptance script. All original audio is preserved; undo never duplicates media payloads.

**Unverified/remaining:** Win11 standard-user C:\.tlo installation and ACL acceptance; actual MSI update/signing/rotation; mapped-drive and UNC mutation/recovery tests; hosted Windows/Linux/macOS CI; full pin-locked Ruff; remaining free-form location ambiguity, later-inventory selective undo, GUI control regrouping, uncommon tag/frame types and requirements-addenda consolidation. Source preflight is not native release attestation.

Read `REMEDIATION_PLAN_v721.md` for the exact disposition and `REGRESSION_RESULTS_v721.txt` for measured test results. Every correction uses a new ZIP and build number; do not overwrite prior packages.

Build 713 fixed hosted CI fixture portability and the Windows byte-locked-file test assumption; these remain in Build 721. Build 715 corrected the Build 714 Pygments/Ruff dependency-lock typos; Build 716 corrected the subsequent local bytecode-contamination error. Full native signing and CI gates remain required.

**Retained Build 716 local staging remediation:** Run 715 failed before GitHub upload because the wheel verifier imported tlo_version without -B, leaving __pycache__/tlo_version.cpython-314.pyc in the prepared tree. Build 716 and Process v158 guard against source-local bytecode generation. Native CI/signing not attested.

**Retained Build 717 / process v159:** Restored non-attested verification-report contracts following run 45067649844. The gate remains mandatory in Build 721 / process v163. Native acceptance remains pending.

**Local Build 721 validation:** see versioned REGRESSION_RESULTS_v721.txt for exact source-suite totals; source hygiene/readiness passed. Native and Ruff remain required.
