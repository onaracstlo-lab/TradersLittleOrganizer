# TLO Inventory v1.7 Build 700: Deep Review Report

**Bundle reviewed:** `music_inventory_flat_bundle_v700.zip` (all 484 entries in `SHA256SUMS_v700.txt` match)
**Baseline:** Build 694 and my report on it
**Review date:** 2026-11-18
**Environment:** Linux, Python 3.12 + Tk under Xvfb, mutagen, system FFmpeg 6.1.1, libFLAC 1.4.3 CLI, Ruff 0.16.10 (the pinned version)
**Scope note:** As requested, how duplicates are *identified* is out of scope.

---

## Contents

1. Method
2. Release gate and lint
3. Status of the v694 findings
4. Summary of new findings
5. Findings
6. Test suite
7. Checked and found sound
8. Limits
9. Appendix: minimal reproductions

---

## 1. Method

Neither the bundled tests nor my earlier reports were used as evidence. Each v694 item was re-run against v700, and the review also covered behaviour the earlier reports never touched.

- **Diff.** Every source file was compared between v694 and v700. Only eight runtime files changed, and the changes are small: `tlo_staging_recovery`, `tlo_flac_fingerprint`, `tlo_corruption`, `tlo_phase23_v2`, `tlo_postprocess`, `tlo-search`, `tlo-reverse` and `tlo_version`. Each change was read in full and then exercised.
- **Before/after runs.** About 16 synthetic collections built from real FLAC files were run through `tlo-gi.py`, `tlo-tag.py`, `tlo-reverse.py` and the Search back-end. Several collections were run on **both v694 and v700** so that output differences could be attributed to the new code. One set of 30 typical "Venue, City, ST" folder names was diffed show by show.
- **Areas never covered by an earlier report:**
  - Copy Requests end to end: parse, evaluate, copy, second pass, reports.
  - Manual Tweaks: batch rename with bootlist, setlist and tag updates.
  - Non-Latin artists.
  - Re-inventory of folders that Rename Compliantly had already renamed.
- **Damaged audio.** Pipe-encoded FLACs (both the MD5 and the total sample count unset), truncated and bit-flipped copies of them, and MD5-bearing copies were passed through the verifier, and through a full inventory with Deep Audio Check on.
- **Gates.** I ran pinned Ruff, `tools/verify_release_gates.py` (under Xvfb), a plain headless `pytest`, and the new `tools/audit_unused_imports.py` against an injected unused import.

**Verified** means I reproduced the behaviour by running code. **Code-read** means it comes from inspection only.

---

## 2. Release gate and lint

**G1 (the v694 F401 failure) is fixed. Verified.**

- **Ruff:** pinned Ruff 0.16.10 with the bundle's `ruff.toml` reports *All checks passed* on the pristine tree.
- **Release gate:** `tools/verify_release_gates.py` passes end to end. Ruff is clean, pytest gives **2,845 passed, 6 skipped** in 65 seconds under Xvfb, and the requirements DOCX metadata check passes. The output ends `RELEASE SOURCE CHECKS PASSED (native signing NOT ATTESTED)`.
- **New audit tool:** `tools/audit_unused_imports.py --root .` scans all 408 Python files. It **does** catch a real unused import: I inserted `import zipfile` into `tlo_cities.py` and it failed with exit 1, naming the file and line. This closes the hole that let G1 through.

**Process notes (no defect):**

- **Ruff is still not run where the build is made.** `BUILD_VERIFICATION_v700.txt` still says "Ruff lint: not attested locally (Ruff 0.16.10 unavailable)". The AST audit is a good backstop, but if that environment can install Ruff with pip (`pip install ruff==0.16.10`), the record could say "passed" instead of "not attested".
- **The stall is environment-specific.** The same record says the full uninterrupted suite "stalls in this Linux runtime". Here the complete suite ran uninterrupted in about one minute, both headless and under Xvfb.

---

## 3. Status of the v694 findings

| v694 item | My result on v700 |
|---|---|
| G1 Unused `import csv` fails Ruff | **Fixed** (see §2). |
| F1 Deep Audio Check passes damaged unset-MD5 FLACs | **Fixed for safety.** Truncated and bit-flipped files are no longer passed, tagged or trusted. Damage in MD5-bearing files is still caught as `FingerprintCorrupt`. The fix has a UX cost for *intact* pipe-encoded files (**V3**). |
| F2 Staging recovery unusable on Windows | **Fixed** (code-read, plus a simulated Win32 API). The `OpenProcess`/`GetExitCodeProcess` probe returns False only for `ERROR_INVALID_PARAMETER` and treats everything else as alive. Linux dry-run and restore were re-verified. Residual guidance gap: **V6**. Native Windows was not tested. |
| F3 City dropped before a trailing qualifier | **Mostly fixed.** 15 of my 20 cases keep the city, including `(SBD)`, `(24-96)`, `(set 2)`, `(Early Show)`, `[24-96]`, `[Matrix]` and stacked `(SBD) (24-96)`. Residuals: **V5**. |
| F4 Rename guard refuses legitimate renames | **Open**, as the v696–v700 plans say. Two-digit years, `8. Mai`, `1er avril`, `ø` and `æ` are still refused. The shnid case is still correctly protected. |
| F5 Search accent-sensitive | **Fixed for Search.** Björk/Bjork, Røyksopp/Royksopp, Æther/AEther, Straßenjungs/Strassenjungs, Köln/Koln and Motörhead/Motorhead all match in both directions against a real bootlist. Copy Requests still has the problem (**V1**), and non-Latin folding is broader than documented (S11). |
| F6 `summary.log` rename line not run-scoped | **Fixed.** Re-verified across two volumes: a run without Rename Compliantly no longer reports another volume's counts. |
| N3 ALBUM/Show churn across runs | **Fixed for the reported case.** My five-run sequence (rename + tag ×3, tag-only, plain) now keeps the folder, ALBUM and Show identical. The fix has side effects: **V4**. |
| S1 Non-UTF-8 entry hex-only; "0 unresolved" | Open (unchanged). |
| S2 Unbalanced `)` silently returns nothing | **Fixed.** It now raises "Unexpected closing parenthesis in search expression." |
| S3 `title=unknown` lowercase | Open (unchanged). |
| S4 Tagger log header `search path: []` | Open (unchanged). |
| S5 Recovery dry-run omits count | **Fixed.** The output reads `Recovery records: 1; restored: 0; would restore: 1; conflicts: 0`. |
| S6 Provisional Dry Run item | Open (`tlo_ux` unchanged). |
| S7 Raw `shutil.Error` text from Add Shows | Open (`tlo_inventory_update` unchanged). |

---

## 4. Summary of new findings

V1, V2 and the V4 root cause predate v700. V1 and V2 are present in v694 too, and I missed both in the v694 review.

| # | Severity | Finding | Status |
|---|---|---|---|
| V1 | **High** if the Artist DB lacks ASCII aliases | Rename Compliantly writes ASCII folder names that TLO's own artist matcher cannot resolve. On the **next inventory those shows drop out of `bootlist.csv`** and go to `unidentifiedShows.txt`. A Copy Request for `Björk` also matches nothing. | Verified on v694 and v700 |
| V2 | **Medium** | Non-Latin artists (Cyrillic, Japanese and so on) are identified and then erased by the ASCII-only output step. The Show becomes just the date, and **tagging overwrites correct existing ARTIST/TITLE tags with `Unknown`** and ALBUM with the bare date. | Verified on v694 and v700 |
| V3 | Medium–Low | Side effect of the F1 fix: with Deep Audio Check on, **every intact pipe-encoded show is silently left untagged and unrenamed**. There is no console line, the rename summary says "0 skipped", TAG_SUMMARY counts each folder twice, and damaged and intact files get the same reason. | Verified |
| V4 | Low | Side effects of the N3 fix: a free-standing comma (`Hall , Cornell`) now survives into Show and ALBUM and **mis-splits venue and city**. Comma retention also varies with how many words the city has. About a third of my 30 "Venue, City, ST" folders get a **different Show and ALBUM on the first v700 re-inventory**. | Verified |
| V5 | Low | F3 residuals: "Venue City" without a region still loses both, and some suffix styles still hide the city (`Berlin 24-96`, `Berlin - SBD`, `Berlin.SBD`, `[FLAC16]`). The User Manual overstates the coverage. | Verified |
| V6 | Low | F2 residual: recovery fails closed when a PID is reused, which is common on Windows after a reboot. The conflict message does not say which condition fired or how to finish the move by hand. | Code-read |
| S8–S11 | Nit | A lock file containing the hostname is left in the Copy Request destination; Manual Tweaks renames are not reversible and accept Windows-invalid names off Windows; verifier wording; non-Latin search folding (§5.7). | Verified |

---

## 5. Findings

### V1. Renamed ASCII folders are no longer identified, and their shows vanish from the bootlist (High, conditional)

**Verified** with a synthetic Artist DB whose masters are the accented names:

1. **Run 1:** Full Inventory with Rename Compliantly. `Björk 2007-08-20 Paris` became `Bjork …`, and likewise `Sigur Rós` became `Sigur Ros`, `Motörhead` became `Motorhead` and `Mötley Crüe` became `Motley Crue`. The bootlist had 8 rows.
2. **Run 2:** a plain re-inventory of the same volume. The console said `re-inventory reconciliation: previous 8 | … | unresolved omitted 4 | new rows 4 | net -4`. The four renamed shows were **removed from `bootlist.csv`** and listed in `unidentifiedShows.txt`. `Strassenjungs 1980-01-01 Koln` also lost its city, because its artist (`Straßenjungs` in the DB) no longer resolved.
3. **v694:** the same two-run sequence with `Björk` and `Motörhead` left an empty bootlist after run 2, so this is not new in v700.

**Root cause.** Two pieces of code are inconsistent:
- **Output side:** the names TLO writes are ASCII-folded by `standard_ascii_text` (`tlo_text_utils.py:59`, applied to every field at `tlo_phase23_v2.py:5144–5152`).
- **Matching side:** artist matching is an exact casefold lookup (`tlo_artist_db.py:272`, `exact_map[term.casefold()]`). `lookup_artist_master_with_status('Bjork')` returns `no_match` when the DB holds `Björk`.

So TLO can rename a folder into a form it can no longer recognise.

**Second symptom: Copy Requests.** A request line `Björk` resolves to the DB master `Björk`. Inventoried shows are stored as `Bjork …`, and `Bjork` has no DB match, so the two keys differ and the item is reported under **UNMATCHED REQUEST ITEMS**. Typing `Bjork` works. F5 fixed exactly this mismatch for Search but not for Copy Requests.

**Severity depends on the real `artists.sqlite`.** The bundle ships a 0-byte placeholder. If the production DB carries an ASCII alias for every accented artist, this does not happen. If it carries only accented masters, every compliant rename of such an artist removes the show from the catalogue on the next inventory. Search, View and Copy Requests then cannot see it.

**Fix:**
- In `load_artist_matcher`, also index `standard_ascii_text(term).casefold()` for every master, alias and term. Then any name TLO writes can always be read back.
- Use the same key in `_artist_key` for Copy Requests.
- As a safety net, when a re-inventory would drop a row that was previously identified, keep the old row and flag it rather than deleting it.

### V2. Non-Latin artists are erased, and tagging overwrites correct tags (Medium)

**Verified on v694 and v700.** The artist DB contains `Кино`, `Аквариум` and `ゆらゆら帝国`.

| Folder | Bootlist Show | Tags after `--tag-during-inventory` |
|---|---|---|
| `Кино 1990-06-24 Москва` (pre-tagged `ARTIST=Кино`, `TITLE=Группа крови`) | `1990-06-24` | `artist=Unknown`, `album=1990-06-24`, `title=Unknown` |
| `Аквариум 1990-06-24 Ленинград` | `1990-06-24` | `artist=Unknown`, `album=1990-06-24` |
| `ゆらゆら帝国 2009-06-24 東京` | `2009-06-24` | `artist=Unknown`, `album=2009-06-24` |

The metadata log shows that the artist **was** identified (`EVIDENCE_ARTIST: Кино | path pattern | 70`). The field-normalisation step then turned it into an empty string. The existing ARTIST tag is logged as `########` and discarded as "punctuation-only". Because the record is not treated as unidentified, tagging proceeds and replaces good user metadata with `Unknown`.

Two different bands on the same date get the same Show (`1990-06-24`). Setlists are kept apart only by the `(alt1)` suffix, and neither show is listed in `unidentifiedShows.txt` or `artistsNotInDatabase.txt`.

The manual says "non-Latin artist or location words are preserved" (User Manual, Rename Compliantly notes). That holds for the folder name, which the rename guard protects, but not for the Show or the tags.

**Fix** (any of these, in order of preference):
1. Allow Unicode in tags. Vorbis comments are UTF-8, so ASCII-only output need only apply to folder names.
2. If ASCII conversion empties an identified artist or title, treat the folder as unidentified: skip tagging, keep the existing tags and list it in `unidentifiedShows.txt`.
3. At minimum, never replace a non-empty existing tag with `Unknown`.

### V3. The F1 fix silently skips intact pipe-encoded shows under Deep Audio Check (Medium–Low)

**Verified.** The test folders held FLACs encoded through a pipe, so both the MD5 and the total sample count are unset. Some were intact, some damaged. The run used `--deep-audio-check --tag-during-inventory --corrupt-files delete --corrupt-folders all`:

- **Safety is now correct:** nothing was tagged or trashed, and both folders were logged as `CORRUPTION_UNVERIFIABLE`.
- **The console says nothing.** v694 printed a "Deep Audio Check: … unset MD5" line. v700 prints nothing about these folders; the reason appears only in `conf*.log`, `tage*.txt` and `summary.log`.
- **Rename Compliantly is skipped too, and miscounted.** A folder `Phish 1997.11.29 Worcester` holding one intact pipe-encoded file was not renamed, yet the console said **`Rename Compliantly: 0 renamed, 0 skipped`**. Without Deep Audio Check the same folder is renamed.
- **TAG_SUMMARY double-counts.** Two folders produced `folders=4 … skipped_folders=2 file_errors=2` (v694: `folders=2`). The unverifiable branch counts the folder at `tlo_phase23_v2.py:8375–8378`, and the later "not tag-ready" branch at `:8487–8489` counts it again as an error.
- **Damaged and intact files look identical.** The verifier raises a specific reason for the truncated file ("decoder reported damaged/omitted frames"). `tlo_corruption._deep_audio_stream_status` discards it (`:345–346`, `except FingerprintUnverifiable: return None`), and `:419–432` rebuilds a generic header-based reason. A file with real decoder errors is therefore described exactly like a perfectly good pipe-encoded file. When the MD5 is unset but the sample count is known, the reason falls back to "checker unavailable, cancelled, timed out, or access failed", which is wrong.
- **No remedy is offered.** The messages do not say how to proceed, for example by re-encoding with `flac` so that STREAMINFO is written, or by tagging without Deep Audio Check. The verifier text also ends oddly: "…even if tagging succeeds".

**Fix:**
- Emit one console line per affected folder (or a counted summary) naming the reason and the remedy.
- Count rename skips caused by unverifiable folders.
- Drop the second `groups/errors` increment.
- Carry the verifier's exception text through to the log instead of rebuilding a generic reason.

### V4. Side effects of the N3 comma change (Low)

The fix at `tlo_phase23_v2.py:3999–4005` slices `raw_tokens = left.split()` using a count taken from `tokens`. But `tokens` drops comma-only tokens. **Verified:**

**(a) Spaced commas.** This is a regression versus v694:

| Folder | v694 Show | v700 Show | v700 parsed venue / city |
|---|---|---|---|
| `GD 1977-05-09 Barton Hall , Cornell University Ithaca, NY` | `…Barton Hall Cornell University Ithaca, NY` | `…Barton Hall , Cornell University Ithaca, NY` | `Barton Hall , Cornell` / `University Ithaca` |
| `Wilco 2004-06-01 Club Bonafide , Upstairs Room New York, NY` | `…Club Bonafide Upstairs Room New York, NY` | `…Club Bonafide , Upstairs Room New York, NY` | `Club Bonafide , Upstairs` / `Room New York` |

**(b) Inconsistent output.** The underlying split treats the last word as the city plus a few prefixes, and it is wrong for most multi-word cities in both versions: `Cow Palace Daly` / `City`, `Club Metro St.` / `Paul`, `Riverport Amphitheater Maryland` / `Heights`. v694 hid this by dropping all commas. v700 keeps the commas that fall inside the mis-split "venue". The result:
- `Cow Palace, Daly City, CA`, `Club Metro, St. Paul, MN` and `Fillmore West, San Francisco, CA` keep their comma.
- `Madison Square Garden, New York, NY`, `Massey Hall, Toronto, ON` and `Barton Hall, Cornell University, Ithaca, NY` lose it, the last becoming `…Cornell University Ithaca, NY`.

**(c) One-time churn on upgrade.** In my 30-folder set, **10 Shows differ** between v694 and v700. With tagging on, those ALBUM tags are rewritten once. Folders are not renamed, because the guard refuses punctuation-only changes.

**Fix:**
- Build the venue/city split from character offsets in `left` rather than by re-splitting, or keep `tokens` and `raw_tokens` aligned by filtering both the same way.
- Better: choose the longest suffix of `left` that is a `cities.csv` city or alias (the catalog has 7,228 entries, including Daly City, St. Paul and Maryland Heights) before falling back to the last word.
- Mention the one-time Show/ALBUM change in the release notes.

### V5. F3 residuals; the manual overstates (Low)

**Verified** (plain Full Inventory):

- **Venue before an unqualified city still loses both,** with or without a qualifier: `Wilco 1987-05-22 Metro Chicago` gives `Wilco 1987-05-22`, and `… Tempodrom Berlin (SBD)` gives `… (SBD)`. This also happens on v694.
- **Some suffix styles still hide the city:**
  - `Berlin 24-96` gives no city.
  - `Berlin - SBD` gives no city.
  - `Berlin.SBD` gives no city.
  - `Berlin [FLAC16]` gives no city.
  - The bracket regex at `:5114` only accepts `NN-NN(N)`, `SBD`, `AUD`, `matrix`, `set N` and `disc N`.
- **The catalogue has gaps.** `cities.csv` has no `Buffalo` row, so `Grateful Dead 1977-05-09 Buffalo` becomes `Grateful Dead 1977-05-09`. An unknown trailing city word is dropped from the Show rather than kept as raw text.
- **Bracket qualifiers are removed from the Show** (`Berlin [24-96]` becomes `…Berlin`), while parenthesised ones are kept. This is pre-existing and may be intended, but it is not documented.

The User Manual says the city is retained when followed by "an SBD, AUD, disc, set or sample-rate qualifier". That is true only for the parenthesised and listed bracket forms.

### V6. Recovery fails closed on PID reuse, without guidance (Low, code-read)

The F2 fix is correct and safe. On Windows, PIDs are recycled quickly, so after a reboot the recorded PID often belongs to an unrelated process. Recovery then reports `RECOVERY_CONFLICT … Recorded worker is active or its remote status is unknown` (`tlo_staging_recovery.py:185`). The message:
- does not say whether the host or the PID check fired;
- does not show the PID;
- does not say how to finish the move by hand (for example "close TLO, then rename `<stage>` back to `<source>`").

**Fix:** split the message by condition and print the stage and source paths. Also record the process creation time in the journal, so a reused PID can be told apart from the original worker.

### 5.7 Smaller issues (nits; all verified)

- **S8. Copy Requests lock file.** After a completed pass, the destination keeps `.tlo-lock-copy-destination.lock` holding `{"hostname": …, "pid": …, "request_id": …}`. If the destination is a drive being sent to another trader, that file travels with it. Clear the payload, or delete the file on a clean release.
- **S9. Manual Tweaks.**
  - Batch renames are not written to `folderOperations.log`, so `tlo-reverse` cannot undo a typo. The manual does not say so.
  - New names are checked for `<>:"|?*` only when `os.name == "nt"` (`tlo_manual_updates.py:58`). On Linux or macOS, `Worcester?` was accepted for a folder that may later be used on Windows.
- **S10. Verifier wording.** The verifier says "…cannot establish audio completeness, even if tagging succeeds". It reads better as "…; tagging and renaming skipped under Deep Audio Check".
- **S11. Non-Latin search folding.** `normalize_search_text` strips *all* combining marks after NFKD, which over-matches in non-Latin scripts: `Мой` matches `Мои`, `ёж` matches `еж`, and Devanagari vowel signs and Greek tonos are removed. It never misses a match, but the code comment and manual say non-Latin scripts are preserved. Limit the stripping to Latin letters.

---

## 6. Test suite

- **Plain headless `pytest`** (no display, no environment variables): **2,823 passed, 28 skipped, 0 failed** in about 60 seconds. T1 remains fixed.
- **Release gate under Xvfb:** **2,845 passed, 6 skipped** (native Windows only), with Ruff clean.
- **New v695–v700 tests:** they exercise real FLACs and real CLI runs, which is good. None covers the following:
  - a second inventory after an accented compliant rename (V1);
  - non-Latin artists with pre-existing tags (V2);
  - the console output and counters for unverifiable folders (V3);
  - spaced commas or multi-word cities (V4).

  The tables in §5 can serve directly as test cases.

---

## 7. Checked and found sound

- **F1 safety.** Damaged unset-MD5 FLACs are no longer called verified, tagged or trashed. MD5-bearing damage is still caught by the sample-count check. Without Deep Audio Check, tagging behaves as before.
- **F2 logic.** Simulated Win32 results: invalid parameter gives False, access denied gives True, a live process gives True, an exited process gives False, and a failed query gives True. Linux recovery (dry-run and restore) and the new count were re-verified.
- **Search.** Accent and transliteration matching works in both directions, and the unbalanced-parenthesis error is clear.
- **`summary.log`.** The rename count is now scoped to the current run across two volumes.
- **Copy Requests, end to end:**
  - Year, exact-date, two-digit range and exact-Show items match correctly, and the invalid `yyyy-yyyy` range message is clear.
  - Five shows were copied with their original folder names, a second pass is a clean no-op, and request state moves to "Matches Complete / Unmatched Remain".
  - `latest-report.txt` is accurate and complete.
- **Manual Tweaks:** the folder rename, bootlist row, setlist rename and tag refresh all work in one pass.
- **Release tooling:** Ruff, the gate script and the new full-tree import audit all work.

---

## 8. Limits

- **No native Windows or macOS.** V6 and the F2 fix are code-read, plus a simulated Win32 API. MSI, signing and the PowerShell gate were not exercised.
- **The real Artist DB is not available.** The bundled `artists.sqlite` is a 0-byte placeholder, so V1's real-world severity depends on whether the production DB includes ASCII aliases for accented names.
- **FFmpeg.** I used system FFmpeg 6.1.1, not the bundled 9.0.2.
- **Not tested:** SHN conversion (no Shorten encoder available), Preferences, and online lookups (eTreeDB and setlist.fm).
- **Out of scope:** duplicate identification, as requested.

---

## 9. Appendix: minimal reproductions

**V1 (renamed shows vanish):**
```bash
# artists.sqlite contains the master "Björk" (no ASCII alias)
mkdir -p "music/Björk 2007-08-20 Paris" && cp tone.flac "music/Björk 2007-08-20 Paris/01.flac"
tlo-gi.py --TLOHome H --search-path "[D] $PWD/music" --rename-compliantly   # folder becomes "Bjork 2007-08-20 Paris"
tlo-gi.py --TLOHome H --search-path "[D] $PWD/music"                        # answer 1 to the re-inventory prompt
# console: "... unresolved omitted 1 | net -1"; the bootlist no longer has the show; unidentifiedShows.txt lists it
```
```python
from tlo_artist_db import load_artist_matcher, lookup_artist_master_with_status
m = load_artist_matcher(cfg)                       # cfg.artist_sqlite_db_file = H/TLO_DBs/artists.sqlite
lookup_artist_master_with_status('Björk', m)       # ('matched', ['Björk'])
lookup_artist_master_with_status('Bjork', m)       # ('no_match', [])
```
For Copy Requests, put `Björk` on a request line and call `evaluate_request(...)`. The item appears in `unmatched_items`, while `Bjork` matches.

**V2 (non-Latin tags overwritten):**
```bash
mkdir -p "music/Кино 1990-06-24 Москва" && cp tone.flac "music/Кино 1990-06-24 Москва/01.flac"
metaflac --set-tag="ARTIST=Кино" --set-tag="TITLE=Группа крови" "music/Кино 1990-06-24 Москва/01.flac"
tlo-gi.py --TLOHome H --search-path "[D] $PWD/music" --tag-during-inventory
metaflac --export-tags-to=- "music/Кино 1990-06-24 Москва/01.flac"   # artist=Unknown album=1990-06-24 title=Unknown
```

**V3 (silent skip):**
```bash
ffmpeg -v error -f lavfi -i "sine=frequency=440:duration=3" -ac 2 -ar 44100 -sample_fmt s16 -f flac - > piped.flac
mkdir -p "music/Phish 1997.11.29 Worcester" && cp piped.flac "music/Phish 1997.11.29 Worcester/d1t01.flac"
tlo-gi.py --TLOHome H --search-path "[D] $PWD/music" --deep-audio-check --rename-compliantly --tag-during-inventory
# console: "Rename Compliantly: 0 renamed, 0 skipped"; folder not renamed; file not tagged; nothing else on console
# logs/tage*.txt: TAG_SUMMARY folders=2 ... skipped_folders=1 file_errors=1   (one folder counted twice)
```

**V4 (spaced comma):**
```python
from tlo_phase23_v2 import _split_left_for_city_and_venue as s
s('Barton Hall , Cornell University Ithaca')   # v700: ('Barton Hall , Cornell', 'University Ithaca')
                                               # v694: ('Barton Hall Cornell University', 'Ithaca')
s('Cow Palace, Daly City')                     # both: venue 'Cow Palace[,] Daly', city 'City'
```

**V5 (city residuals):** inventory the folders `Wilco 1987-05-18 Berlin 24-96`, `Wilco 1987-05-24 Berlin - SBD`, `Wilco 1987-05-22 Metro Chicago` and `Grateful Dead 1977-05-09 Buffalo`. Each bootlist Show is only artist and date (plus `(set 2)` where present).
