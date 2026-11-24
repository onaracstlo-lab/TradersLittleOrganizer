# Build 725 / GitHub Build Process v167 — SQLite city matching

The supplied cities.sqlite and match_city.py are integrated read-only into folder and selected-setlist location handling. A known state/province/country can support high-confidence typo correction and multiword city boundaries; exact aliases retain source spelling. Unknown/ambiguous cities use the existing positional/region/online fallbacks. The SQLite master ships externally in TLO_DBs and is MSI-managed on Windows. Existing Build 723 behavior is retained. Windows/macOS hosted build, installer-signing and native runtime acceptance are NOT ATTESTED by these local tests.

## Current Build 725 source verification

- Application: **3,039 passed, 7 skipped** across 337 modules in 13 isolated source suites; 4 warnings.
- GitHub Build Process v167: **194 passed, 14 skipped**.
- SQLite matcher remains external/read-only. The fallback CSV, region/state/country positioning, venue and existing network/setlist sources are retained.
- Current Requirements DOCX and Manual RTF metadata, source-release pointer, requirements catalog, third-party notices and remediation build identity have been corrected.
- Native Ruff, Windows installer/signing, runtime Windows acceptance and hosted CI remain **NOT ATTESTED**.

## Retained prior findings and gates

## Historical Build 723 document and source audit — pre-release candidate

The current build restores guarded permanent rmdir in the reusable Windows deferred cleanup template, adds Add Shows progress and automatic duplicate review, and retains manual resume. Earlier recycle-only batch documentation is superseded. Native Windows release remains NOT ATTESTED.

## Historical TLO v1.7 Build 723 — documentation and source audit

**Historical Build 723 status:** The older source candidate was not signed or hosted-CI-attested; its companion was Process v165.

## Current correction

Build 723 changes the deferred Windows `deleteReplacedFolders.bat` template to **permanent `rmdir /s /q`**, guarded by an exact current volume-label check, safe rooted folder validation and reparse-point rejection. No batch deletion undo or recycling mechanism is generated. This script may be reused for other inventory copies after verifying each target drive and label. The separate GUI **Delete New / Keep Old** operation retains its Windows Recycle Bin implementation (and the Build 722 default-registry fix).

Add New Shows displays per-folder execution status, progress totals and staged/duplicate/held/error counts. Once Process New Shows finishes, it automatically launches review for existing/new pending folders in `dups`. The **Process Potential Duplicate/Upgrades** button remains; quitting without a resolution retains the candidate for later review. Original new-show source processing and artist metadata rules are unchanged.

## Evidence verified locally

- Application behavior: **2,733 passed, 7 skipped, 3 warnings** across **284 modules** in 13 independently completed shards.
- Application contracts/unit/integration: **295 passed**; combined unique application **3,028 passed, 7 skipped**.
- Build-process suite: **194 passed, 14 skipped**.
- Release hygiene and 25-disposition source readiness: passed before packaging.
- All 435 application Python files parsed without syntax errors, no compiled artifacts found; Ruff lint is local-unattested and mandatory pinned Ruff, native cmd.exe operations and hosted CI remain release gates.
- Historical Build 723 carried Requirements DOCX and RTF manual, catalogs, changelog, README, release notes, verification and manifests; Build 725 provides newly versioned counterparts and Process v167.

## Remaining acceptance

Native Windows 11 confirmation of the immediate GUI Recycle Bin path and the independent deferred rmdir batch on labeled/unlabeled volumes; pinned Ruff 0.16.10; native Windows/Linux/macOS GitHub Actions; package signing/scanning and release publication **remain NOT ATTESTED**. Retained earlier MSI, wheel-lock, packed Git-publication, tag-undo, and capitalization fixes require their ordinary native release gates. Prior released ZIPs have not been modified.
