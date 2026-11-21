# Traders Little Organizer v1.7 Build 700 — Independent Source Review

**Review date:** 2026-11-18  
**Input:** `music_inventory_flat_bundle_v700.zip`  
**Review type:** Independent, read-only inspection of the supplied source bundle, selected runtime probes, document checks, archive verification, and threat-oriented code review. **No original files were modified.**

## Executive summary

**Recommendation: Do not promote Build 700 as a production release until the two priority-1 trust-boundary defects below have been addressed and regression-tested.** The source contains meaningful defensive measures (signed-update hashes, download-host limits, no-overwrite publication, symlink checks in several transfer paths, atomic file writes), but those protections are not consistently applied to Copy Requests path reconstruction or staged-move recovery.

The principal findings are:

1. **P1 / Security and correctness:** Copy Requests can read/copy a directory outside the selected volume root using `..` in a stored path **or a symlinked ancestor**, despite checking that the final folder is not itself a symlink. **Both variants were reproduced.**
2. **P1 / Security and data movement:** A fabricated same-volume staging recovery journal can direct a restore to an unrelated absolute path outside the selected staging area. **Reproduced with an actual non-overwriting directory move in an isolated temporary tree.**
3. **P2 / Correctness:** A legacy full UNC path stored alongside a UNC volume label is reconstructed with the server/share duplicated. **Reproduced.**
4. **P2 / User experience:** The Windows per-user MSI defaults to `C:\.tlo`; a non-admin user may lack permission to create it, and installation-time writability confirmation is not apparent in the generator. **Native Windows risk; not reproduced here.**
5. **P2 / Clarity:** The FAQ describes TLOHome as containing the installed applications and says the user must set it manually, contradicting the documented MSI flow.
6. **P2 / Packaging clarity:** The source bundle describes itself as complete, but its bundled `artists.sqlite` is a **zero-byte placeholder** and `TLO_DBs/venues.txt` is absent. This is an intentional build-pipeline convention, but it is not prominently distinguished from a runnable distribution.
7. **P3 / Conciseness and duplication:** Active root-level material includes about **10,657 lines of change history**, many earlier remediation plans, and old build-process notes. This makes it harder to find the current requirements and outstanding work.

**Independent checks that passed:** ZIP CRC (`testzip()`), 484-of-484 manifest entries and SHA-256 hashes, no duplicate ZIP member names, syntax parsing of 408 Python files, all 408 files through the supplied AST unused-import audit, and byte-for-byte agreement between the distributed INI and its embedded default template. These checks do **not** resolve the findings or replace native release testing.

## Scope, method, and limitations

- Reviewed the extracted **485-entry** archive (~17.5 MB uncompressed), including runtime Python, PowerShell scripts, WiX generator, updater, CLI and GUI paths, requirements DOCX text, user-manual RTF text, FAQ, source notes, remediation plans, and selected tests.
- Traced user-controlled and persisted filesystem paths through Copy Requests, UNC helpers, staged recovery, and install/update functions. Probed suspicious paths using **temporary mock folders only**; no actual show or user inventory was touched.
- Used the existing tests as background only; new issues were found by reading the implementation and separately exercising its behavior.
- **Not performed:** full GUI interaction, native Windows 11 tests, WiX compilation or install/uninstall, release signing verification, actual network/GitHub release validation, real external UNC shares, full regression suite, or final visual inspection of the entire DOCX/RTF layout. The full source bundle does not contain a complete standalone build-process repository.
- **Native Ruff not available in this environment:** `python -m ruff --version` failed. `tools/verify_release_gates.py` correctly blocked at the mandatory Ruff step. The supplied Build 700 verification file itself identifies native CI, signing, and MSI as pending.

### Findings table

| ID | Priority | Category | Finding | Confidence |
|---|---|---|---|---|
| SEC-01 | **P1** | Security / Copy Requests | Volume-root escape through `..` and symlink ancestors | **Reproduced** |
| SEC-02 | **P1** | Security / Recovery | Unauthenticated recovery-journal destination | **Reproduced** |
| BUG-01 | **P2** | Correctness / UNC | Legacy full UNC path reconstructed incorrectly | **Reproduced** |
| UX-01 | **P2** | Windows MSI | Default data directory may not be writable | Code-based, Windows verification needed |
| DOC-01 | **P2** | Documentation | Outdated TLOHome startup and application-location instructions | **Confirmed in text** |
| PKG-01 | **P2** | Packaging / onboarding | Source candidate looks more runnable than it is | **Confirmed in archive** |
| DOC-02 | **P3** | Documentation / duplication | History and remediation artifacts overwhelm the current material | **Measured** |
| REL-01 | **P2 gate** | Release assurance | Native lint, MSI, signing, and hosted CI are not yet attested | **Confirmed by supplied evidence / local gate** |

## Detailed findings and recommendations

### SEC-01 — Copy Requests can escape a mapped volume root (**P1; reproduced**)

**Where:** `tlo_copy_requests.py:909–942` (`_physical_paths_for_volume_stored`), `:950–1015` (`source_status_for_show`), `:1037–1066` (direct volume paths). Relevant tree scan: `:1382–1395`.

**Evidence:** The non-UNC branch strips leading separators and then calls `os.path.normpath(os.path.join(root, ...))`, without rejecting `..` segments or enforcing that the canonical candidate remains below the mapped root. `source_status_for_show` subsequently accepts an existing directory if the **leaf** is not a symlink; it does not reject a symlink elsewhere in the path.

**Independent reproduction:** With a temporary volume root of `<temp>/drive`, stored path `../private` resolved to `<temp>/private`, outside `drive`. The complete `source_status_for_show()` call accepted that outside folder as the source candidate. Separately, `<temp>/drive/alias` was a symlink to `<temp>/outside`; stored path `/alias/show` was accepted even though its real destination was outside the volume. The leaf `/alias/show` was not itself a symlink, so the leaf-only check did not catch it.

**Impact:** A malformed, edited, or malicious inventory `VolumePath` or `[Volume]` request can cause Copy Requests to select the wrong folder and potentially copy files unrelated to the intended volume. On multi-user or removable-media setups this crosses an intended selection/trust boundary. This does **not** establish remote code execution; the demonstrated consequence is unauthorized or incorrect source selection.

**Recommendations:**

- Reject `..` path components **before** joining volume-relative paths; reject Windows drive syntax, UNC syntax, and malformed rooted input in this branch.
- Resolve both the approved volume root and candidate using filesystem-aware canonical paths; require `os.path.commonpath([candidate_real, root_real]) == root_real` (using Windows-normalized case semantics where appropriate). A lexical check alone does not prevent symlink-ancestor escape.
- Use the same guard for bootlist rows, explicit `[Volume]` requests, and redundancy replicas; preserve the separately intentional native-absolute-path mode only after an explicit, documented trust decision.
- Run the containment check again at the point of opening/copying files to narrow race exposure; prefer descriptors/handles or otherwise document residual TOCTOU risk.

**Acceptance tests:** Reject `[VOLUME] ../peer`, `[VOLUME] ..\\peer`, nested `a/../../peer`, and symlink/junction ancestor escapes; accept ordinary nested paths and separately approved native absolute paths. Run on Windows shares/drives and Linux/WSL, including redundant-volume selection. The test should verify **no outside data is read or copied**, not just returned string shapes.

### SEC-02 — Recovery trusts a fabricated journal's absolute source path (**P1; reproduced**)

**Where:** `tlo_staging_recovery.py:43–68` (journal writer), `:136–161` (`_journal_data`), `:164–213` (recovery). `tlo_tag_lib.py:3230–3263` performs the actual no-replace move. Compare the stronger registered-journal design described for sibling collection recovery in `TLO-FAQ.txt`.

**Evidence:** A file named `.tlo-move-<32 lowercase hex>.json` with the expected format, stage suffix, destination parent, local hostname, and an inactive PID is accepted. The journal's `source` may be **any absolute path**; the restore destination is not tied to an independently protected issuance registry, original source root, or cryptographic/authenticated ownership proof. The record is opened without a file-size limit. Preventing overwrite is useful, but does not validate the *destination*.

**Independent reproduction:** Created a fake journal and a dummy `.tlo-partial-...` directory inside a temporary selected staging directory. Set `source` to a **different** temporary directory's nonexisting path, `target` to a plausible sibling, `host` to the current host, and `pid` to an inactive PID. Dry run returned `would_restore=1`; actual recovery returned `restored=1`, removed the staged folder, and created the folder at the unrelated destination.

**Impact:** If an adversary or untrusted package can place or alter a matching journal and staged folder in a directory the user later recovers, TLO will perform a user-authorized but **journal-directed** move outside that directory. Risk depends on write access to the selected staging location; no privilege escalation was demonstrated. Oversized journal input is a separate potential denial-of-service vector.

**Recommendations:**

- Add an independently recorded registry of journal nonces and their immutable source/stage/target values under a controlled `TLOHome` location (akin to sibling recovery), or another integrity-bound issuance mechanism.
- Bind source to the actual recorded move and to an explicitly approved source root; reject arbitrary absolute destinations, including paths reached through symlinked parents. Never infer legitimate issuance solely from the JSON file's contents.
- Enforce a small journal size limit (e.g., tens of KiB), strict field schema, and file-type/ownership/permissions checks suitable for Windows and POSIX.
- Keep the explicit preview and no-overwrite guarantees. State source, destination, and recovery trust status plainly before any mutation.

**Acceptance tests:** Forged journal, edited source path, mismatched nonce, foreign host, PID reuse, missing journal registry, oversized JSON, symlinked parent, target collision, and valid interrupted move. Confirm no mutation for every untrusted case and successful recovery for an authentic journal.

### BUG-01 — Legacy UNC source path is appended twice (**P2; reproduced**)

**Where:** `tlo_unc.py:67–81` and `tlo_copy_requests.py:918–923`.

**Evidence:** The function comments that legacy rows can store a fully qualified UNC path, but the implementation always strips leading backslashes and joins the remainder to the UNC volume root. With volume `UNC:ONARACS/Music` and stored `\\ONARACS\Music\Band\Show`, the result was `\\ONARACS\Music\ONARACS\Music\Band\Show`, not the original share path.

**Impact:** Some legacy or manually edited inventory rows can be marked missing even when their network share is connected. This is particularly confusing during Copy Requests, where a broken path resembles a missing backup drive.

**Recommendation:** Detect a fully qualified stored UNC path, compare its server/share to the volume label case-insensitively, and return the normalized path **only if** it belongs to that share. Reject a different share and traversal; otherwise use the existing share-relative path logic. Add mixed-case and forward-slash regression cases. If legacy absolute UNC rows were never officially supported, remove the contradictory comment and instead provide a clear migration warning.

### UX-01 — Per-user MSI default may fail at the Windows root (**P2; unverified platform risk**)

**Where:** `msi/generate_wix.py:141–161` (default `C:\.tlo`); `tlo_msi_install_mode.py:217–233`, `:268–318` (first-run validation and fallback).

**Evidence:** The installer is per-user but defaults data creation to the root of C:, where non-admin users frequently lack create-directory permission. The Python startup path probes writability and prompts for another location, which is a useful fallback, but there is no clearly visible installation-time permissions check in the provided WiX generator. The user's chosen default is intentionally `C:\.tlo`; the issue is the untested failure experience, not a recommendation to silently change the preference.

**Impact:** A user may complete a successful MSI and encounter a blocking data-folder prompt on first launch, with an apparent inconsistency between the selected install path and working application setup.

**Recommendation:** Retain `C:\.tlo` as the initial choice if required, but validate creation/writability during installation and provide an unmistakable alternative such as a user-profile data directory before finish; preserve an existing configured TLOHome. Verify per-user install, fresh Windows 11 standard-user account, UAC-disabled/no-admin path, upgrade, uninstall and repair.

### DOC-01 — FAQ contradicts the MSI installation model (**P2; confirmed**)

**Where:** `TLO-FAQ.txt:10–14`, compared with `SOURCE_BUNDLE_README_v700.txt:40–55` and `TLO_Inventory_User_Manual_v700.rtf` (installation section), plus `msi/generate_wix.py:171–173`.

**Evidence:** The FAQ answers **“Do I need to define TLOHome before I start? Yes”** and describes TLOHome as the root for applications, databases, logs and inventory. Under the MSI, executables live in `%LOCALAPPDATA%\Programs\Traders Little Organizer`, while a selected TLOHome holds user data, and the installer persists its configuration. The FAQ's required-file answer also lists only `artists.sqlite` and `venues.txt`, omitting the now-required `cities.csv` for current complete installations.

**Impact:** New Windows users may unnecessarily edit environment variables, move application files into TLOHome, or overlook a missing city database.

**Recommendation:** Replace the two answers with a Windows-MSI-first explanation: **the installer sets TLOHome; portable installs and command-line launches may require configuration**. List the three current managed databases and clearly differentiate source-only placeholders from a complete install. Make the RTF overview consistent: its statement that the Search app runs after a distribution is *extracted into TLOHome* should apply only to portable ZIP installations.

### PKG-01 — Source bundle contains a database placeholder, not a runnable full installation (**P2; confirmed**)

**Where:** ZIP `TLO_DBs/artists.sqlite` (**0 bytes**), missing `TLO_DBs/venues.txt`; `SOURCE_BUNDLE_README_v700.txt:1–13`, `:56–65`; `TLO_RELEASE_REMEDIATION.json` finding `L8` explicitly calls the empty database intentional.

**Evidence:** The README describes a **“complete source bundle”** containing reference data; source-only runs nevertheless require master database injection by the separate build process. The root-level `cities.csv` and `TLO_DBs/cities.csv` are currently byte-identical, which also leaves the purpose of the two copies unclear to casual readers.

**Impact:** A developer or tester who extracts this ZIP and tries to launch directly may encounter confusing database failures, mistaking intentional source staging for a defective application release.

**Recommendation:** Add a prominent **“SOURCE CANDIDATE — NOT A RUNNABLE DISTRIBUTION”** statement at the top of the README. Describe the required ArtistDB-Master files, where they enter the build, why `artists.sqlite` is empty, and how to run a source smoke test with fixtures. Label `cities.csv` at the ZIP root as a build input versus its staged runtime copy, or remove the redundant copy only after verifying its build-process consumers.

### DOC-02 — Root-level release documentation is not concise (**P3; confirmed**)

**Where:** `CHANGES_v700.txt` (10,657 lines / ~915 KB), `SOURCE_BUNDLE_HISTORY.txt` (257 lines), root `REMEDIATION_PLAN_v688.md` through `v700.md`, historical `BUILD_PROCESS_*_v645/v649.txt`, and `docs/history/`.

**Evidence:** Current changelog starts with Build 700 but contains numerous historical records, repeated **“HISTORICAL CHANGE RECORDS”** banners, and more than one Build 688 section. The source history itself warns that old instructions are historical and points to older `v685` filenames. Current root remediation files coexist with archived remediation plans, multiplying potential starting points.

**Impact:** Harder to identify the current unresolved defects and release criteria; stale URLs/build versions in a historical document can be mistaken for active operational guidance. No claim is made that all history should be deleted—preserving provenance is valuable.

**Recommendation:** Keep one short `README.md` / `CURRENT_STATUS.md` with build, install modes, current release status, current docs, and open issues. Retain full history under `docs/history/` with an index. Use a short current changelog containing new-build changes and a link to historical material, unless source-distribution obligations require the full historical file. Archive obsolete build integration notes that no longer govern Build Process v144, but retain a discoverable link. Avoid duplicating progress narration in requirements, current remediation plan, and release notes.

### REL-01 — Build 700 is not release-attested (**P2 release gate, not a discovered code vulnerability**)

**Where:** `BUILD_VERIFICATION_v700.txt`, `REGRESSION_RESULTS_v700.txt`, `RELEASE_NOTES_v700.txt`, `REMEDIATION_PLAN_v700.md`, and the source's `tools/verify_release_gates.py`.

**Evidence:** Supplied evidence explicitly says native Ruff, hosted GitHub Actions, signing, MSI and native-Windows acceptance have not run or have not been attested. Independent local run: `python tools/audit_unused_imports.py --root .` passed for 408 files; `python tools/check_release_hygiene.py --source-root . --build-number 700` passed; `python tools/verify_release_gates.py` blocked because Ruff is unavailable.

**Impact:** Source tests and a valid ZIP do not demonstrate that release binaries are correctly packaged, signed, installed, upgradable, usable on Windows, or free of new native-only failures.

**Recommendation:** Treat a new, uniquely versioned remedial build as a source candidate until mandatory native Ruff, full hosted CI, artifact signature and package verification, Windows 11 MSI install/upgrade/uninstall, per-user TLOHome selection, and both safety regressions above pass. Do not overwrite or relabel the Build 700 ZIP.

## What is working well

- Whole-ZIP signed digest verification and signed-asset metadata bindings precede normal update acceptance (`tlo_github_updates.py`). Downloads are bounded and publish through a temporary filename with a no-overwrite policy.
- Update package checking rejects traversal paths, duplicated names, many Windows-unsafe names, symlink members, and extreme decompression ratios; protected user-data paths are checked for update ZIPs.
- Several destructive operations already use staging, journaling, SHA-256 verification, and atomic publication instead of copy-then-delete in place.
- CSV formula escaping, bounded network metadata reads, and explicit Windows helper executable paths are present in the source.
- The build reports clearly mark missing native attestation rather than incorrectly claiming a production-ready release.

These positives should be retained while fixing the inconsistent boundaries identified above.

## Proposed remediation order and acceptance checklist

1. **Next build, first:** Fix **SEC-01** in one shared volume-path-resolution guard and add security-focused integration tests including actual copying of isolated fixtures. Eliminate both traversal and symlink-ancestor cases.
2. **Same build:** Fix **SEC-02** with independently bound recovery records, bounded journal reads, and a thorough crash/recovery matrix. Verify authentic recovery still works and that an untrusted staging tree cannot redirect a move.
3. **Same build or subsequent focused build:** Fix **BUG-01** legacy UNC path reconstruction and add realistic UNC/drive/WSL test cases; native Windows UNC share verification is essential.
4. **Documentation-only pass:** Reconcile **DOC-01** and **PKG-01**, then create one concise current entry point for release status and usage. Keep historical files accessible but visually separated from current instructions.
5. **Platform acceptance:** Exercise **UX-01** with an ordinary non-admin Windows 11 profile and a fresh MSI, followed by upgrade, repair and uninstall; confirm user data remains intact.
6. **Release gate:** Run native Ruff over source **and tests**, full hosted platform builds, signature verification and smoke tests, release archive scan, and all current regression groups. Publish a *new* build ZIP/package; never replace previously delivered versions.

## Suggested minimum independent regression scenarios

| Scenario | Expected result |
|---|---|
| Volume-relative `../neighbor` bootlist row | Refused before source enumeration |
| Volume-relative `a/../../neighbor` request | Refused; no outside files read/copied |
| Parent symlink/junction inside mapped volume | Refused when it points outside authorized root |
| Valid volume-relative nested folder | Located and copied as before |
| Forged `.tlo-move-*.json` in staging root | Clear conflict; no move |
| Valid orphaned same-volume staged move | Preview then restore without overwrite |
| Oversized/modified/foreign recovery journal | Refused without reading an unbounded payload or moving files |
| Stored same-share absolute UNC path | Reconstructed once, not duplicated |
| Stored different-share absolute UNC path | Refused; no cross-share copying |
| Fresh Windows 11 standard-user MSI setup | Selectable, writable data folder with helpful messages |
| Current FAQ and manual installation instructions | Correct for MSI and ZIP without requiring unnecessary variables |
| Complete source ZIP opened by a developer | Clear explanation of master DB inputs and source-versus-binary limitations |

## Final disposition

**Build 700 is suitable for continued controlled source testing, not yet for production promotion.** The two demonstrated filesystem trust-boundary issues should be remediated before release. The remainder is a manageable mix of UNC compatibility, Windows setup validation, and documentation/packaging improvements. The existing test counts are encouraging but did not cover the two reproduced defects; acceptance must include the negative-path scenarios above and native-platform validation.
