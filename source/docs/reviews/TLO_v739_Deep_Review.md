# TLO Inventory v1.7 Build 739: Deep Review — Bug Checks and Consistent User Behavior

**Bundle reviewed:** `music_inventory_flat_bundle_v739.zip` (624 entries; all 623 entries listed in `SHA256SUMS_v739.txt` match; ZIP CRC clean; no duplicate member names)
**Baseline:** Build 739 remediation plan (follow-up to the Build 732 review) and the still-open items from the Build 700 deep review in `docs/reviews/`
**Review date:** 2026-11-27
**Environment:** Linux, Python 3.12.3 + Tk 8.6 under Xvfb, mutagen 1.48.1, pytest 9.1.1 and Ruff 0.16.10 (both pinned versions), FFmpeg 6.1.1 (used as the bundled validator for duplicate-repair runs), libFLAC 1.4.3, and the three SQLite catalogs shipped in the bundle (49,545 artists / 120,421 terms, 12,051 cities, 70,215 venue names)

---

## Contents

1. Method
2. Release gate and lint
3. Status of Build 739 remediation items and earlier open findings
4. Summary of new findings
5. Findings
6. Cross-tool consistency matrix
7. Test suite
8. Checked and found sound
9. Recommendations, in priority order
10. Limits
11. Appendix: minimal reproductions

---

## 1. Method

I did not treat the bundled tests or the earlier reports as evidence. Every finding below comes from running the code or reading it directly.

- **Real catalogs.** This is the first review with a populated `artists.sqlite`; earlier bundles shipped a 0-byte placeholder. Every artist, city and venue result below comes from the shipped databases.
- **End-to-end runs.** I built about 20 synthetic collections from real FLAC files (encoded by `flac`, so STREAMINFO MD5 is set), plus pipe-encoded files (MD5 unset) and deliberately damaged copies. I ran them through `tlo-gi.py`, `tlo-tag.py`, `tlo-deleteDupes.py`, `tlo-reverse.py`, the `searchAuxDBs` query functions and its GUI under Xvfb.
- **Tags.** All test tags were written with mutagen (UTF-8). In one early run I wrote tags with `metaflac` under a POSIX locale, which stores `Björk` as `Bj##rk`. I noticed this, discarded those results, and reran everything.
- **Consistency sweep.** I ran the same edge cases through every entry point: missing, relative and nonexistent TLOHome, unknown options, `--tlo-home`, `--dry-run`, the shared operation lock, and confirmation defaults.
- **v739 changes.** I exercised each item in the remediation plan: duplicate repair with MD5 checks and retained originals, auxiliary search, TLOHome precedence, the setlist.fm upgrade gate, and the CI Tk gate.

**Verified** means I reproduced the behaviour by running code. **Code-read** means it comes from inspection only.

---

## 2. Release gate and lint

- **Ruff 0.16.10** (pinned) with the bundled `ruff.toml`: *All checks passed*.
- **Full suite under Xvfb** (Python 3.12, pinned pytest 9.1.1, nothing deselected): **3,266 passed, 8 skipped, 4 warnings, 8 subtests passed** in 107 s. All 8 skips are native-Windows-only. The process-pool crash test that the bundle deselects ran and passed here.
- **CI Tk gate:** with `CI=1` and an interpreter without Tkinter, `conftest.py:201` raises `CI requires Tkinter; GUI tests cannot silently disappear`. **Verified.**

**Process note:** `REGRESSION_RESULTS_v739.txt` records *Ruff 0.17.6, pytest 9.2.0, Python 3.12.14*. The lock pins Ruff 0.16.10, pytest 9.1.1 and Python 3.13.16. The recorded local evidence was therefore not produced with the pinned toolchain. This run confirms the pinned Ruff and pytest pass, but the record should state the versions actually used, or use the pinned ones.

---

## 3. Status of Build 739 remediation items and earlier open findings

| Item | Result on v739 |
|---|---|
| **B5** Auxiliary artist variants, compressed fallback, city-region guidance | **Works for ASCII input.** `The Grateful Dead`, `GD`, `Band`, `Allman Brothers`, `AllmanBrothersBand`, `Crosby Stills and Nash`, `Dead and Company` and `Rolling Stones, The` all give the same master as the inventory matcher. **Gap:** Artist search does not fold accents, while City and Venue do (**W2**). The City hint appears; full state names (`Portland, Oregon`) return nothing, which matches the documented "region abbreviation" rule. |
| **B7** MD5 compatibility; retain originals on the same volume | **Works.** A healthy same-size copy with a different declared MD5 is refused. Repair succeeds from a matching copy, and the original is kept on the same volume. New issues with where the original goes and how it can be found: **W3**, **W4**. |
| **B6/R10** Empty alias records; tagger rethrow | Code-read: `_validate_required_tables` requires only `artists` and `terms`. Sound. |
| **U1/U4/R1** Radio group, status label, reusable results window, TLOHome precedence, GUI argument errors | **Verified under Xvfb:** the radio buttons are exclusive, status shows on the main window, the results window is reused and retitled, and a bad `--database` value appears in a dialog. Residuals: **W8** (`tlo-main` still reports TLOHome errors only on stderr), **W12**, **W13**. |
| **U3** Explicit setlist.fm upgraded-access preference | Code-read plus bundled test: only `SETLISTFM_API_KEY` is needed; a legacy upgrade key with a different value is refused with a clear message. Sound. |
| **CI** Fail without Tk | **Verified** (§2). |
| **D5** History de-duplication | Root `CHANGES` is down from 10,860 to 6,704 lines. Contradictory normative text remains (**W15**). |
| v700 **V1** Renamed ASCII folders not re-identified | **No longer reproduces with the shipped ASCII-only DB.** Index-side folding was added (`tlo_artist_db.py:280–288`), but query-side folding was not, so the problem now runs the other way (**W2**). |
| v700 **V2** Non-Latin artists erased; tags overwritten | **Improved:** `Кино` tags are now preserved (`TAG_SKIP … show unidentified`). Residual: **W10**. Latin diacritics in existing tags are still ASCII-folded when TLO rewrites them (`TITLE=Glósóli` became `Glosoli`). |
| v700 **V3** Deep Audio Check silently skips intact pipe-encoded files | **Fixed.** The console now names the folder and the remedy, and `TAG_SUMMARY` no longer double-counts. |
| v700 **V4** Spaced comma splits venue and city | **Fixed** for the reported case: `Barton Hall , Cornell University Ithaca, NY` gives `… Barton Hall Cornell University Ithaca, NY`. |
| v700 **V5** City residuals | **Improved:** `Berlin 24-96` keeps Berlin; `Buffalo` and `Metro Chicago` are kept. |

---

## 4. Summary of new findings

**W3**, **W4** and part of **W12** are in code changed for v739. The rest predate v739. I found them by running real catalogs and checking behaviour across tools, which earlier reviews could not do.

| # | Severity | Finding | Status |
|---|---|---|---|
| W1 | **High** | When a show folder's artist is not in the DB, TLO takes the artist from an **ancestor folder** that happens to be an Artist DB term: the search root itself, or a folder above it such as a mount or volume name. Examples: `Dropbox`, `Elements` (WD drives on macOS), `Archive`, `Work`, `Public`, `nas`, `Plex`. That artist **outranks an existing, correct ARTIST tag**, is **written into ARTIST/ALBUM tags**, and the show is **not** listed as unidentified. | Verified (inventory and `tlo-tag`) |
| W2 | **Medium**; High together with W1 | Accented artist names never match the ASCII-only Artist DB. `Björk`, `Beyoncé`, `Motörhead`, `Sigur Rós`, `Mötley Crüe`, `Béla Fleck` and `Maná` are not recognized from folder names or tags. Auxiliary Artist search fails the same way, while City and Venue search in the same window fold accents. | Verified |
| W3 | **Medium** (v739) | Retained corrupt originals land **inside the show** when the duplicate cluster is disc-level. Tag Copy and Copy Requests then **copy `.tlo-deleteDupes-originals-*` to the destination**; only `.tlo-shn-originals` is excluded. | Verified (Tag Copy); Copy Requests by function probe |
| W4 | Low–Medium (v739) | Retained originals cannot be traced: one hidden folder per file, holding only the bare filename. The path appears only on the console; nothing is written to TLOHome; the `Complete:` line has no repair count; there is no report tool. | Verified |
| W5 | **Medium** | The Dry Run plan says "rename to resolved compliant show name" for every folder. The real run then refuses those renames (3 of 3 in my test). | Verified |
| W6 | **Medium** | The shared one-mutating-run-per-TLOHome lock is taken by Inventory (GUI and `tlo-gi`), Add Shows, Manual Tweaks and Reverse (even with `--dry-run`), but **not by Tag (GUI Tag and `tlo-tag`) or `tlo-deleteDupes`**. | Verified (CLI); code-read (GUI Tag) |
| W7 | Low–Medium | `tlo-deleteDupes` leaves a stale `bootlist.csv` row for every relocated duplicate and does not prompt a re-inventory. | Verified |
| W8 | Low–Medium | `tlo-main` reports an invalid TLOHome (for example an unplugged drive in `TLOHome`) only on stderr, which windowed builds do not show. `tlo-search` and `searchAuxDBs` show a dialog. | Verified |
| W9 | Low | Copy Requests confirmations (Delete request, Clear stale lock ×2, Process All, Close) default to **Yes**. Every other consequential confirmation in the GUI defaults to **No**. | Code-read |
| W10 | Low | A non-Latin artist show becomes a bare-date bootlist row (`1990-06-24`) and is not listed in `unidentifiedShows.txt`. An unknown ASCII artist is handled the opposite way. | Verified |
| W11 | Low | An explicit bracketed label (`[Elements]`) is silently replaced by the folder basename (`[Live]`) when the OS reports no label. | Verified |
| W12 | Low | The auxiliary search uses the whole multi-line clipboard as its first query and runs it automatically. The status says "match found" whether there is 1 match or 5. | Verified |
| W13 | Low | The hidden `--myTLO` silently overrides an explicit `--TLOHome` in every tool, and a v739 test locks this in. | Verified |
| W14 | Nit | Inconsistent command-line conventions: exit codes, the `--tlo-home` alias, Dry Run availability, and writable-home requirements (§6). | Verified / code-read |
| W15 | Doc | Contradictory current text: "checkboxes" vs "radio buttons"; old vs new aux-search requirement; `--tag-path` vs `--search-folder`. | Confirmed in text |
| W16 | Tests | The v739 "accent" test passes without testing anything against the shipped DB. W1, W3, W5 and W6 have no tests. | Verified |

---

## 5. Findings

### W1. An ancestor folder name replaces an unrecognized artist and overwrites correct tags (High)

**Verified** with the shipped `artists.sqlite`, in Full Inventory (`--tag-during-inventory`) and in standalone `tlo-tag`.

| Collection path | Existing tags | Bootlist Show | Tags after the run |
|---|---|---|---|
| `…/Dropbox/Björk 2007-08-20 Paris, France` (search root = `Dropbox`) | `ARTIST=Björk`, `TITLE=Jóga`, `ALBUM=Live in Paris` | `Dropbox 2007-08-20 Paris, France` | `artist=Dropbox`, `album=Dropbox 2007-08-20 Paris, France`, `title=Joga` |
| `/…/Volumes/Elements/Live/Zzyzx Quartet 2023-01-01 The Sinclair, Cambridge, MA` (root = `Live`) | none | `Elements 2023-01-01 The Sinclair Cambridge, MA` | `artist=Elements` (`tlo-tag`) |
| `/…/Volumes/Elements/Live/Mötley Crüe 1985-02-14 Cow Palace, Daly City, CA` | none | `Elements 1985-02-14 …` | `artist=Elements` |
| `…/work/m1/Motörhead 1981-03-28 Hammersmith Odeon, London, England` | none | `Work 1981-03-28 …` | not tagged in that run |
| Same `Zzyzx Quartet` folder under a neutral parent | none | *(not in bootlist)* | listed in `unidentifiedShows.txt`, as designed |

The last row shows the intended fail-safe: an unknown artist should become unidentified. Any ancestor that matches an Artist DB term defeats it. The metadata log records the cause: `EVIDENCE_ARTIST: Dropbox | subdirectory:Dropbox | 60` and `OBSERVATION: deferring raw tag artist while path/setlist evidence is checked: Björk`.

**Common folder names that are Artist DB terms** (checked in the shipped DB): `Dropbox`, `Elements`, `Passport`, `Archive`, `Work`, `Public` (as in `C:\Users\Public\Music`), `nas`, `Plex`, `Sound`, `Sounds`, `Various`, `Jam`, `Dead`, `Keep`, `Best`, `Seeds`, `Trees`, `X` and `Prince`. `Music` and `Video` are safe only because they are wrapper names.

**Root cause:**
- `_path_parts` (`tlo_phase23_v2.py:1633–1651`) returns every component up to the filesystem root. It strips only the WSL `/mnt/<drive>` prefix.
- `_eligible_artist_path_parts` (`:1701–1727`) and `_resolve_artist_from_subdirs` (`:6472–6549`) treat the search root, folders above it, and mount or volume names as artist evidence with weight 60.
- An unmatched tag artist has weight 45 and is deferred (`:8270–8278`), so the ancestor wins.
- The rename guard did protect the folder name ("source identifying text would be lost: bjork"). Tags have no matching guard.

**Impact:**
- Correct ARTIST, ALBUM and TITLE tags are overwritten.
- The bootlist shows the wrong artist, so Search, Copy Requests and View cannot find the show by its real artist.
- Nothing is reported. The show is in neither `unidentifiedShows.txt` nor `artistsNotInDatabase.txt`.
- On macOS every external drive is mounted at `/Volumes/<label>`, so one unlucky label (for example a WD "Elements" drive) affects every unrecognized artist on that drive.

**Fix:**
1. Never use components **above** the search root as artist evidence, and never use mount or volume components (`/Volumes/X`, `/media/<user>/X`, `/run/media/<user>/X`, `/mnt/X`, a UNC share). The search root itself should count only when the show folder has no artist text before the date.
2. If the show folder has non-empty artist text before the date, or the files have a non-empty ARTIST tag, an ancestor-only DB hit should be a **conflict**, giving an unidentified show, not a winner.
3. Never replace a non-empty existing ARTIST tag with an artist whose only evidence is `subdirectory:`.
4. Add the tables above as regression cases.

### W2. Accented artist names never match the ASCII-only Artist DB (Medium; High together with W1)

**Verified.** The shipped `artists.sqlite` holds no non-ASCII characters (0 of 120,421 terms). Its masters are `Bjork`, `Beyonce`, `Motorhead`, `Sigur Ros`, `Motley Crue`, `Blue Oyster Cult`, `Husker Du`, `Mana` and `Bela Fleck & The Flecktones`.

| Query | `lookup_artist_master_with_status` | searchAuxDBs Artist | searchAuxDBs City / Venue |
|---|---|---|---|
| `Bjork` | matched `Bjork` | `Bjork` | — |
| `Björk`, `BJÖRK` | **no_match** | **no results** | — |
| `Motörhead`, `Sigur Rós`, `Béla Fleck & the Flecktones` | **no_match** | **no results** | — |
| `Köln` / `Koln` | — | — | City: both give `Köln, Germany` |
| `Zénith` / `Café Wha?` | — | — | Venue: give `Zenith` / `Cafe Wha?` |

**Root cause.** The v700 V1 fix added ASCII folding on the **index** side only (`tlo_artist_db.py:280–288`). The **query** side still looks up `variant.casefold()` (`:369`). The compressed fallback key keeps non-ASCII letters (`_compressed_artist_key`, `:38–43`, so `ö` stays `ö`). With an all-ASCII DB, the index-side folding has no effect.

**Consequences:**
- Folders such as `Motörhead 1981-…` or `Maná 1999-…` become unidentified. In the `Maná` run, the folder text also produced a hit on the band `Man`, logged as a conflict.
- Under any W1 ancestor they are misattributed.
- An existing `ARTIST=Björk` tag is treated as "not in DB". Here the release notes contradict the behaviour: inventory Search finds "Bjork with an umlaut", but inventory identification and Artist search do not.

**Fix:** In `lookup_artist_masters`, also try `standard_ascii_text(variant).casefold()` against `exact_map`, and build `_compressed_artist_key` from folded text. Use the same key in `searchAuxDBs._query_database`: add a folded `term_text` comparison, or rely on the matcher fallback once it folds. Then the three radio choices behave alike.

### W3. Retained corrupt originals can end up inside the show and are copied to destinations (Medium, v739)

**Verified.** `repair_corrupt_flacs_from_copies` passes `holding_parent = dirname(original_path)` (`tlo-deleteDupes.py:1007–1011`). The code comment says the intent is to *"Hold originals outside the show … future Copy/Delete cannot consume them."*

- **Show-level cluster** (`X` and `X (copy2)` side by side): the holding folder is created next to the show. Correct.
- **Disc-level cluster** (`Show/CD1` and `Show/CD1 (copy2)`, an exact copy family): `original_path` is `Show/CD1`, so its parent is **the show**. My run printed `Original FLAC retained for recovery: …/Phish 1997-11-29 Worcester, MA/.tlo-deleteDupes-originals-88w98jx7/d1t01.flac`.
- A later **Tag Copy** of that show then produced `dest/Phish 1997-11-29 Worcester, MA/.tlo-deleteDupes-originals-88w98jx7/d1t01.flac`. The corrupt file travels with the show. Tag Copy excludes only `.tlo-shn-originals` (`tlo_tag_lib.py:3182–3184`).
- **Copy Requests** has the same gap. `_walk_tree_size_and_reject_links` (`tlo_copy_requests.py:1470`) and `_copytree_ignore_root_names` (`:1491`) exclude only `.tlo-shn-originals`. Probed on a collection root holding three retained-originals folders, the ignore function returned `[]` and the size total included them. A whole-volume or parent-folder request therefore ships them.

The FAQ says held SHN originals "are excluded from Tag Copy and Copy Requests". Duplicate-repair originals, the other kind of TLO-held original, are not.

**Fix:**
- Choose the holding parent as the parent of the **outermost show folder**: walk up from `original_path` to the folder that is a sibling-cluster member at show level, or simply use `search_root`.
- Add the shared prefix list in `tlo_path_policy.TLO_TEMP_DIR_PREFIXES` to the Tag Copy, Copy Requests and tree-compare ignore functions, so that one list governs every enumerator.

### W4. Retained originals cannot be traced (Low–Medium, v739)

**Verified.** Three corrupt files repaired in two shows produced:

```
coll/.tlo-deleteDupes-originals-nrczff5b/01.flac
coll/.tlo-deleteDupes-originals-u661ne7m/d2t01.flac
coll/.tlo-deleteDupes-originals-urtaohns/d1t01.flac
```

- **One random folder per file, holding only the basename** (`:919–921`). Neither the show name nor the relative path (`CD1` or `CD2`) is kept.
- **The path is only printed** (`console_emit`, `:923`). TLOHome gets `deletedDirs.txt` and `deleteDupesMismatches.txt`, but nothing records the repair. Once the console is gone, the user cannot tell which show `01.flac` came from.
- The final line is `Complete: duplicate_folders_moved=2`. It has no count of repaired files or retained originals.
- Dot-folders are hidden by default on macOS and Linux, so these accumulate unseen. SHN originals have `tools/report_held_shn_originals.py`; there is no equivalent here.
- `tempfile.mkdtemp` creates the folder with mode `0700`. On a shared NAS, other accounts cannot inspect it.
- **Code-read note on the MD5 guard:** if the keeper's STREAMINFO itself is unreadable, `_recorded_flac_md5` returns `None` (`:990`), and any healthy same-name, same-size candidate is accepted without an MD5 comparison (`:1004`). This is conservative enough given the size match, but the manual implies the comparison always happens.

**Fix:**
- Use one holding folder per run and show: `.tlo-deleteDupes-originals-<YYYYMMDD-HHMMSS>/<show folder>/<relative path>`.
- Append `timestamp | keeper file | retained path | source copy` to a TLOHome log such as `deleteDupesRepairs.txt`.
- Extend the summary line, for example `repaired=3 originals_retained=3 (see deleteDupesRepairs.txt)`.
- Generalise `report_held_shn_originals.py` to cover both kinds of held original.

### W5. Dry Run promises renames that the real run refuses (Medium)

**Verified.** These three folders were run with `--dry-run --tag-during-inventory --rename-compliantly`, then for real:

| Folder | Dry Run "Planned action" | Real run |
|---|---|---|
| `Beyoncé 2016-05-01 Marlins Park, Miami, FL` | rename to resolved compliant show name (Show `Dropbox …`) | `RENAME_COMPLIANTLY_SKIP … source identifying text would be lost: beyonce` |
| `Björk 2007-08-20 Paris, France` | rename … | `… would be lost: bjork` |
| `Phish 1997-11-29 Worcester Centrum, Worcester, MA` | rename … | `… punctuation-only reduction` |

The action list is static. `tlo_ux.py:373–374` appends "rename to resolved compliant show name" whenever the option is on, without running the rename guard. The real run's console line ("0 renamed, 3 skipped") contradicts the preview. The same preview also showed the W1 artist (`Dropbox`) with no warning. Dry Run is the only place a user could catch W1 before tags are written.

**Fix:**
- Run the same rename guard in preview and print "rename skipped: <reason>" or "no rename needed".
- Flag any Show whose artist evidence is `subdirectory:` only.

### W6. The shared TLOHome operation lock is not taken by Tag or tlo-deleteDupes (Medium)

**Verified for the command-line tools.** I held `inventory_operation_lock(H)` in one process, then started each tool against the same TLOHome:

| Tool | Result |
|---|---|
| `tlo-gi` | `ERROR: Another inventory-mutating TLO run is already active for this TLOHome` (exit 1) |
| `tlo-reverse --dry-run` | same refusal |
| `tlo-tag` | ran: `Complete: folders=1 tagged_files=1` |
| `tlo-deleteDupes` | ran: `Complete: duplicate_folders_moved=0` |

**Code-read for GUI Tag.** The Main window's Tag button calls `run_tagger_jobs` in a worker thread (`tlo-main.py:2587–2600`) with no lock, and `run_tagger_jobs` (`tlo_tag_lib.py:5933`) takes none itself. In the same file, Add Shows (`:4925`), Manual Tweaks (`:4480`), duplicate processing (`:5235`) and Reverse (`:1774`) all use `inventory_operation_lock`. One GUI window blocks overlapping operations through its own UI state, but a second GUI instance or any command-line run on the same TLOHome is not blocked.

The unlocked operations change media: tags, compliant renames, FLAC replacement, and folder moves. They also write TLOHome logs. The manual's "one inventory-mutating run per TLOHome" rule reads as universal.

**Fix:** Wrap `run_tagger_jobs`, used by GUI Tag and `tlo-tag`, and `delete_duplicate_copy_directories` in `inventory_operation_lock(tlo_home)`, as `tlo-reverse.py:64` does.

### W7. Relocated duplicates leave stale bootlist rows (Low–Medium)

**Verified.** I inventoried `Wilco … ` and `Wilco … (copy2)`, then ran `tlo-deleteDupes`. `(copy2)` moved to the duplicates folder, but `bootlist.csv` still lists `[c] …/Wilco 2004-06-01 Chicago, IL (copy2)`. Search, View and Copy Requests keep offering a folder that is no longer there. The tool never reads or updates the inventory, and the manual (§20) does not tell the user to re-inventory.

A large clean-up followed by a re-inventory can also trip the 25% "Significant Inventory Change" guard without any prior warning.

**Fix:** At the end of the run, print "N inventoried folders were relocated; re-inventory <root> to update bootlist.csv (expect a removal prompt if N ≥ 25%)". Alternatively, mark the rows as relocated, as Reverse and Manual Tweaks maintain inventory state.

### W8. tlo-main reports an invalid TLOHome only on stderr (Low–Medium)

**Verified.** `TLOHome=/nonexistent/drive tlo-main.py` prints `ERROR: TLOHome directory does not exist: …` and exits 2 without opening any window (`tlo-main.py:5279–5288`). Only the *missing* case gets the setup dialog. On Windows and macOS `tlo-main` is built `--windowed` (`createWindowsDist.ps1:347`, `createMacOSDist.sh:215`), so a stale `TLOHome` pointing at an unplugged drive looks like "the app does nothing". `searchAuxDBs` (v739) and `tlo-search` show this error in a dialog.

**Fix:** Route the non-missing error through the same `show_config_error_dialog` with a console fallback.

### W9. Copy Requests confirmations default to Yes (Low, code-read)

Reverse, Significant Inventory Change, Connect Existing Inventory, MSI install, Force exit and the storage dialogs all pass `default=messagebox.NO`. These Copy Requests dialogs do not, so Enter confirms them:

- `Delete Copy Request` — deletes TLO state and report history (`tlo-main.py:4232`)
- `Clear Stale Copy Request Lock`, twice (`:4080`, `:4143`)
- `Process All Active Requests` (`:4153`)
- `Close Copy Request` (`:4216`)

**Fix:** Add `default=messagebox.NO` to all five.

### W10. Non-Latin artist shows: tags are safe, but inventory output is inconsistent (Low)

**Verified.** `Кино 1990-06-24 Москва`, with `ARTIST=Кино` and `TITLE=Группа крови`:
- **Tags:** now untouched (`TAG_SKIP … show unidentified; no tags written`), an improvement on v700.
- **Bootlist:** the row is still written as `Show = 1990-06-24`.
- **Unidentified list:** `unidentifiedShows.txt` is empty.

The tagger calls the show unidentified while the inventory calls it identified. An unknown *ASCII* artist (`Zzyzx Quartet`) gets the opposite and correct treatment: it is listed as unidentified and has no bootlist row. Because the Show is the bare date, two different non-Latin bands on the same date would share one Show.

**Fix:** When the artist is empty after normalisation, use the unidentified path for every output.

### W11. An explicit bracketed volume label is silently replaced (Low)

**Verified.** `--search-path "[Elements]/…/Volumes/Elements/Live"` gave bootlist rows labelled `[Live]`. When the OS reports no label, `register_inventory_root` names the root from `info.label or basename(root)` (`tlo_storage_identities.py:411`), and `inventory_list_lib.py:868–876` then overrides the explicit label.

The comment at `inventory_list_lib.py:698` says explicit labels "must be preserved exactly", and the manual says a label that disagrees with the drive is *refused*. Here the label is neither used nor refused, and the console line `Queued search path 1: … | slam=` does not show it.

**Fix:** When a new root is registered, prefer the explicit bracketed label over the basename. Alternatively, print "label [Elements] ignored; inventory name is [Live]".

### W12. Auxiliary search preload and status wording (Low; partly v739)

**Verified under Xvfb:**
- With `C:\Users\Jay\Music` and a newline followed by `second line` on the clipboard, the app opened with that whole string as the query, searched Artist automatically and showed "no results" (`searchAuxDBs.py:70–77`).
- "match found" is shown for 1 or for 5 results (`Portland`).

**Fix:**
- Preload only the first line, capped at about 120 characters, and skip the automatic search if it looks like a path.
- Show "N matches".

### W13. The hidden `--myTLO` overrides an explicit `--TLOHome` (Low)

**Verified.** `resolve_tlo_home` takes `my_tlo or tlo_home or env` (`tlo_path_inputs.py:97`), and `tlo-search.py:1298` mirrors it. The v739 test `test_aux_home_precedence` asserts that the hidden alias wins over an explicit `--TLOHome`. A script that passes both silently uses a value the user cannot see in `--help`.

**Fix:** When both are given and differ after normalisation, raise "--TLOHome and --myTLO disagree".

### W14. Command-line convention drift (Nit)

See the matrix in §6. In summary:

- **Exit codes for TLOHome errors:** 1 in `tlo-tag` and `tlo-deleteDupes`; 2 everywhere else.
- **`--tlo-home` alias:** accepted by `tlo-main`, `tlo-tag` and `tlo-search`; rejected by `tlo-gi`, `tlo-reverse`, `tlo-research`, `tlo-deleteDupes` and `searchAuxDBs`.
- **`--dry-run`:** exists in Main, `tlo-gi` and `tlo-reverse`. `tlo-tag` rejects it (`unrecognized arguments: --dry-run`), even though GUI Tag supports Dry Run. `tlo-deleteDupes` has no preview although it moves folders and replaces files.
- **Writable TLOHome:** `tlo-research` requires write access (default `require_writable=True`) although it only reads logs, while both search tools accept a read-only shared home. Code-read; I could not test as non-root.

### W15. Documentation contradictions (Doc)

- **User Manual:** the Search paragraph says "searchAuxDBs has mutually exclusive Artist, City, and Venue **checkboxes**", while the "Duplicate repair and database search" section says "**radio buttons**".
- **Requirements DOCX:** the older normative paragraph still says "one mutually exclusive **checkbox** selection … Artist: **exact case-insensitive term_text**". The new `REQ-AUX-SEARCH-001` requires radio buttons plus article variants and compressed fallback. This is the same pattern of appended addenda alongside stale normative text noted in earlier reviews; the older paragraph should be edited.
- **Manual example** uses `tlo-tag --tag-path`, while `--help` documents `--search-folder` (`--tag-path` is a hidden compatibility alias).
- **Manual and FAQ** say the retained original's path is "reported". It is printed to the console only (W4).
- **Release notes** say accented artist names work in Search. That is true for inventory Search, not for Artist search or identification (W2).

### W16. Test-suite gaps

- `test_aux_article_and_accent_matches` (`tests/behavior/test_build739_review_followup.py:79`) checks accents only `if expected:`. With the shipped DB, `lookup_artist_masters("BJÖRK")` is empty, so the accent check never runs and the test passes without testing anything. It should assert that `BJÖRK` finds `Bjork`, which currently fails (W2).
- No test covers ancestor attribution (W1), disc-level retained-original placement or Tag Copy / Copy Requests exclusion (W3), Dry Run versus real rename parity (W5), or lock enforcement in `tlo-tag` and `tlo-deleteDupes` (W6). The tables in §5 can be used directly as test cases.

### Data notes (catalog content, not code)

- `Saint Paul, MN` and `St. Paul, MN` are separate city masters, so the displayed city depends on the input spelling.
- `NYC` resolves to the master `N.Y.C, NY`.
- US `region_names` hold only postal abbreviations, so `Portland, Oregon` matches nothing in either search or folder parsing.

---

## 6. Cross-tool consistency matrix

| Behaviour | tlo-main (GUI) | tlo-gi | tlo-tag | tlo-reverse | tlo-deleteDupes | tlo-research | tlo-search | searchAuxDBs |
|---|---|---|---|---|---|---|---|---|
| Invalid TLOHome reported in a dialog | **No (stderr)** | n/a | n/a | n/a | n/a | n/a | Yes | Yes |
| Exit code for TLOHome error | 2 | 2 | **1** | 2 | **1** | 2 | 2 | 2 |
| `--tlo-home` alias | Yes | **No** | Yes | **No** | **No** | **No** | Yes | **No** |
| Hidden `--myTLO` overrides `--TLOHome` | Yes | Yes | Yes | Yes | Yes | Yes | Yes | Yes |
| Dry Run / preview | Yes | Yes | **No** | Yes | **No** | n/a | n/a | n/a |
| Takes shared TLOHome lock | Inventory, Add Shows, Manual Tweaks, Reverse: Yes; **Tag: No** | Yes | **No** | Yes (incl. dry run) | **No** | n/a | n/a | n/a |
| Accepts read-only TLOHome | No | No | No | No | No | **No** | Yes | Yes |
| Accent-insensitive artist | (via inventory) **No** | **No** | **No** | n/a | n/a | n/a | Yes | **No** (City/Venue: Yes) |

Bold cells are where the tool differs from the others or from what the documentation says.

---

## 7. Test suite

- **Result:** 3,266 passed and 8 skipped (all native Windows) under Xvfb with the pinned pytest. Nothing was deselected.
- **New v739 tests:** six. They cover MD5 refusal, retention of the original outside the show for a show-level cluster, aux article matching, TLOHome precedence, and the upgrade key. They are well targeted, but see W16.
- **Prior assurance gap still applies:** many contract tests grep source or documentation text rather than exercising behaviour. A green suite therefore says little about real-catalog behaviour. W1 and W2 can only be seen with the real `artists.sqlite`, and this is the first bundle that ships it.

---

## 8. Checked and found sound

- **Archive integrity:** 623 of 623 SHA-256 entries match; ZIP CRC clean.
- **Lint and CI:** pinned Ruff is clean; the CI Tk gate works.
- **Duplicate repair core:**
  - Staged copy, verified backup and atomic install work as designed.
  - Rollback is used only from a byte-verified backup.
  - A different declared MD5 is refused.
  - After repair the copy is relocated to the duplicates folder; `deletedDirs.txt` gets the full original path.
  - Held originals are pruned from inventory (`is_phase1_pruned_directory`) and from `tlo-tag` discovery; I confirmed both by running.
- **Inventory Dry Run writes nothing:** no TLOHome files, no `.tlo-root-id.json`, and no tag or rename changes.
- **Auxiliary search:** ASCII artist parity with the inventory matcher across 25 probes. City and venue accent folding works. Window reuse, status label and radio exclusivity work. Bad arguments appear in a dialog.
- **Deep Audio Check (v700 V3):** an unverifiable pipe-encoded folder now gets one console line with a remedy, and the counts are correct.
- **Rename guard:** refused lossy renames in every case I tried (accent loss, `24-96`, punctuation-only), including all the W1 cases.
- **setlist.fm:** the upgrade gate works, and the rate-limit state uses the resolved TLOHome passed by the inventory.

---

## 9. Recommendations, in priority order

1. **W1 + W2 together (data safety).**
   - Restrict artist evidence from ancestor folders: nothing above the search root, no mount or volume names, and a conflict rather than a win when the folder or tags carry their own artist.
   - Never overwrite a non-empty ARTIST tag from `subdirectory:` evidence.
   - Add query-side accent folding to `lookup_artist_masters` and to Artist search.
   - Ship both sets of tables as regression tests that run against the real DB.
2. **W5.** Make Dry Run apply the rename guard and flag ancestor-only artists, so users can catch problems before anything is written.
3. **W6.** Put Tag (GUI and `tlo-tag`) and `tlo-deleteDupes` under the shared TLOHome lock.
4. **W3 + W4 (finish B7).**
   - Hold originals beside the outermost show.
   - Exclude every `TLO_TEMP_DIR_PREFIXES` entry in Tag Copy and Copy Requests.
   - Use one holding folder per run and show, preserving relative paths.
   - Log repairs to TLOHome and add counts to the summary line.
5. **W7, W8, W9, W10, W11.** Small consistency fixes; each is a few lines.
6. **W12–W16.** Clipboard preload, conflicting `--myTLO`, command-line alias and exit-code alignment, and the documentation fixes. Make the accent test meaningful.

---

## 10. Limits

- **No native Windows or macOS.** The `/Volumes/…` and `C:\Users\Public` exposure for W1 was simulated with equivalent POSIX paths. MSI, signing, the PowerShell gates and native Recycle Bin behaviour were not exercised.
- **Validator.** Duplicate-repair runs used system FFmpeg 6.1.1 placed as the bundled validator, not the pinned 9.0.2 build.
- **Not tested:** online lookups (eTreeDB, setlist.fm), SHN conversion, Manual Tweaks, the Main GUI end to end (only `searchAuxDBs` was driven under Xvfb), and Copy Requests end to end (W3 for Copy Requests rests on its ignore and size functions, probed directly).
- **Read-only homes.** Tests ran as root, so writable-TLOHome checks (W14 `tlo-research`) are code-read.

---

## 11. Appendix: minimal reproductions

Use mutagen, or set a UTF-8 locale before using `metaflac`, so that tags are stored as real UTF-8.

**W1 (ancestor artist overwrites correct tags):**
```bash
mkdir -p "/x/Dropbox/Björk 2007-08-20 Paris, France" && cp tone.flac "/x/Dropbox/Björk 2007-08-20 Paris, France/01.flac"
python -c "from mutagen.flac import FLAC; f=FLAC('/x/Dropbox/Björk 2007-08-20 Paris, France/01.flac'); f['ARTIST']='Björk'; f['TITLE']='Jóga'; f['ALBUM']='Live in Paris'; f.save()"
tlo-gi.py --TLOHome H --search-path "/x/Dropbox" --tag-during-inventory
# bootlist: "Dropbox 2007-08-20 Paris, France"; tags: artist=Dropbox album="Dropbox 2007-08-20 Paris, France" title=Joga
# meta0.log: EVIDENCE_ARTIST: Dropbox | subdirectory:Dropbox | 60
```
A variant with no tags and an unknown ASCII artist: `/x/Volumes/Elements/Live/Zzyzx Quartet 2023-01-01 The Sinclair, Cambridge, MA`, then `tlo-tag.py --TLOHome H /x/Volumes/Elements/Live` gives `artist=Elements`.

**W2 (accent lookup):**
```python
from types import SimpleNamespace
from tlo_artist_db import load_artist_matcher, lookup_artist_master_with_status
m = load_artist_matcher(SimpleNamespace(artist_sqlite_db_file="TLO_DBs/artists.sqlite"))
lookup_artist_master_with_status("Bjork", m)   # ('matched', ['Bjork'])
lookup_artist_master_with_status("Björk", m)   # ('no_match', [])
```

**W3 (held original inside the show and copied by Tag Copy):**
```bash
mkdir -p "/x/c/Phish 1997-11-29 Worcester, MA/CD1" && cp tone.flac "/x/c/Phish 1997-11-29 Worcester, MA/CD1/d1t01.flac"
cp -r "/x/c/Phish 1997-11-29 Worcester, MA/CD1" "/x/c/Phish 1997-11-29 Worcester, MA/CD1 (copy2)"
# flip ~100 bytes near the end of the CD1 file (same size), then:
tlo-deleteDupes.py --TLOHome H --duplicates-dir /x/dupes /x/c
#   Original FLAC retained for recovery: /x/c/Phish 1997-11-29 Worcester, MA/.tlo-deleteDupes-originals-XXXX/d1t01.flac
tlo-gi.py --TLOHome H --search-path /x/c --tag-copy-during-inventory --tag-copy-destination /x/dest
#   /x/dest/Phish 1997-11-29 Worcester, MA/.tlo-deleteDupes-originals-XXXX/d1t01.flac   (copied)
```

**W5 (Dry Run versus real rename):** use the three folders from the W5 table under any parent. Run `tlo-gi.py --dry-run --rename-compliantly --tag-during-inventory`: every folder shows "rename to resolved compliant show name". Run it again without `--dry-run`: `Rename Compliantly: 0 renamed, 3 skipped`.

**W6 (lock):**
```bash
python -c "import time; from tlo_runtime_control import inventory_operation_lock as L
with L('H'): time.sleep(30)" &
tlo-gi.py --TLOHome H --search-path /x/c        # refused
tlo-tag.py --TLOHome H /x/c                     # runs and tags
tlo-deleteDupes.py --TLOHome H /x/c             # runs
```

**W7 (stale bootlist):** inventory `/x/c` containing `Wilco 2004-06-01 Chicago, IL` and an identical `… (copy2)`. Run `tlo-deleteDupes.py --TLOHome H --duplicates-dir /x/dupes /x/c`. `bootlist.csv` still lists `… (copy2)` at its old path.

**W8:** `TLOHome=/nonexistent tlo-main.py` prints to stderr, exits 2 and opens no window. `TLOHome=/nonexistent searchAuxDBs.py` shows a dialog.
