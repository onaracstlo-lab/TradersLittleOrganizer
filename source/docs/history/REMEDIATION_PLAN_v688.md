# TLO v685 deep-review remediation — Build 688 execution and pending work

## Scope and release discipline

Build 688 starts from the *entire* Build 687 source snapshot and preserves prior fixes. It addresses N6 (unset-MD5 treatment during Deep Audio Check and tagging), N7 (read-only sibling collection preview), N14 (POSIX filenames with invalid UTF-8 bytes), and N16 (duplicate keeper validation messaging). Changes are localized to media verification, inventory discovery, Dry Run preview, and relevant reports. Name-plus-size duplicate discovery is **unchanged**. Prior ZIPs are not overwritten. GitHub Build Process v143 is unchanged.

Every source build must have a complete manifest, updated current-version requirements, User Manual, requirements catalog, release notes, change record, remediation dispositions and executable regressions. `python -m pytest` (without special environment variables), Python compilation, import-lint (including tests), stale-current-reference audit, documentation rendering, ZIP integrity and SHA-256 verification form the local checks. Native Windows/msi, Linux/macOS build, signing, Ruff, malware scanning and publication remain separate hosted acceptance gates.

## MD5 philosophy and safety boundary

**Tagging capability and FLAC audio integrity are different tests.** A FLAC STREAMINFO MD5 of all zeroes means **the encoder did not store a checksum**, not that a temporary tag is unwritable or the audio is broken. TLO continues to run its reversible tag-save/read/restore probe before deep decoding. A non-resource tag-write failure is classified as corrupt and stops that file (existing policy). A filesystem lock, access failure or inability to restore a probe is inconclusive—not permission to delete a file.

Where the temporary tag probe succeeds and a full FFmpeg decode plus available sample-count check succeeds, TLO now records `DEEP_AUDIO_CHECK_MD5_UNSET` as **decode-only / not MD5-authenticated**, and permits normal tagging. That is *not* a proof of full integrity: without the stored MD5, undetected altered samples remain possible. A decoding or sample-count failure still counts as corruption; cancellation, timeouts or missing validators are unverifiable and halt subsequent mutations. No file may be deleted merely because its MD5 is absent.

Duplicate cleanup deliberately has a **stricter** rule: when the keeper FLAC has no stored MD5 it cannot be conclusively checked for bit rot, so the entire cluster is preserved and the user is shown the exact pathname and reason. A separately backed-up checksum-bearing re-encode can be compared, but TLO never silently treats it as identical.

## Build 688 findings

| Finding | Status | Test/evidence |
|---|---|---|
| N6 unset-MD5 unexplained / normal tagging skipped | Fixed; tag test and decoder outcomes separated | `test_build688_audio_preview_paths.py::test_unset_md5_is_taggable_decode_only_not_corrupt` and `::test_missing_md5_tag_write_failure_remains_corruption` |
| N7 Dry Run mispredicts sibling consolidation | Fixed with explicit consolidation plan and provisional group notice; TLO Reverse non-reversibility remains documented | `::test_preview_sibling_collection_is_read_only_and_named` |
| N14 Linux non-UTF-8 path silently omitted | Fixed as explicit unidentified ASCII hex path, no console logging traceback; no mutation during Dry Run | `::test_invalid_utf8_folder_is_explicitly_unidentified` |
| N16 deleteDupes vague/incorrect unavailable message | Fixed with pathname and precise unset-MD5 cause; duplicate is preserved | `::test_missing_md5_dupes_skips_with_file_specific_reason` |

## Remaining backlog

M8, L1, L2, L4–L7, L9, L10, T3, T4 from Build 681 remain deferred for later small builds. N7 includes a documented non-reversible consolidation limitation; implementing Reverse for sibling consolidation is separate work and not silently claimed here. All existing fixed findings from Builds 682–687 remain in `TLO_RELEASE_REMEDIATION.json`; L3 (name and exact size as duplicate identity) remains accepted by user design.

## Platform caveats

Local tests can run on Linux with system FFmpeg. Production Full Audio Check and duplicate validation must additionally be exercised using the packaged FFmpeg, and MSI, Windows path controls, signatures, and hosted GitHub pre-release publication must pass separately. Do not promote pre-release to Latest automatically.
