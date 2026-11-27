# Build 734 documentation audit

## Current documentation
- Manual (RTF): Main Search/Reverse, affirmative default-No confirmation, one literal path, selected TLOHome, Dry Run/audit, existing CLI recovery modes, current installation and safe cleanup behavior. Removed obsolete developer-release troubleshooting from the end-user workflow.
- FAQ: current Reverse, preview audit exception, auxiliary database search and master staging; distinguished immediate GUI recycling from permanent deferred cleanup.
- Requirements (DOCX): corrected Main checkbox-grid descriptions and current menu/Reverse contracts, locking and exit behavior, and updated obsolete cleanup requirements. Existing table structure, identifiers and section hierarchy were retained.
- Requirements catalog (CSV): preserved 1,078 stable requirement IDs; repaired 732 paragraph locators, synchronized 23 paragraph texts, verified 293 table rows and updated 24 supplemental locator labels. The new XML/CSV contract verifies each direct paragraph and table reference against its normative text and detects duplicate IDs.
- Source README and current status: current package/build instructions, entry points, installation ownership, data prerequisites and native release gates. Current reports no longer present earlier tests as acceptance of the current build.
- Release notes, changelog, source pointer, remediation metadata, third-party notices and checksum manifest: synchronized Build 734 and unchanged Build Process v169. Archived previous README, status and Build 733 report evidence in docs/history; no historical test result was relabeled.
- Windows cleanup: the separately executed, guarded old-folder batch uses permanent rmdir /s /q; it is not a Recycle Bin operation and cannot be undone. Immediate Delete New/Keep Old uses the Recycle Bin. Old generated batches are not silently rewritten.

## Verification
The specification rendered to 114 pages and manual to 39 pages. Changed sections were visually checked, and both documents retain their original formats. The catalog integrity and current guidance tests passed. See REGRESSION_RESULTS_v734.txt for local test results and native-test limitations. No claim of native acceptance.
