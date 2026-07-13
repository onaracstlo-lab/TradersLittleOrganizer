"""
Regression tests pinning the TLO Inventory requirements' explicit worked examples
to the current implementation behavior.

These tests are derived directly from the worked examples in
TLO_Inventory_Requirements_Working_v335.docx (Sections 1-15 and
Appendices A-I, with focused examples from Sections 1, 5, 7, 8, 10-15, and Appendix E). They are intended as a guard so that
future date/filename/metadata regex churn cannot silently change documented
behavior.

Run from the directory containing the TLO .py modules:

    pip install mutagen pytest
    python3 -m pytest test_tlo_requirements.py -v

The review-report xfail markers for the compact filename range and >36-token
errors were removed in v190 because those defects are fixed. v191 adds filename.ext:<hex> checksum-row coverage. v192 adds tagger filename-title fallback coverage. v193 adds Tag During Inventory coverage. v194 narrows the compliant Billboard MP3 year-folder special case. v195 adds volume-aware inventory handling, bracketed log headers, and video subdir pattern matching. v196 moves startup volume decisions to group-log headers. v197 adds explicit bracketed search-path volume prefixes and normalized volume matching. v198 makes overwrite/re-inventory reuse existing log tokens. v199 adds zero-padded tag track numbers, zero-based setlist track recognition, and comma-separated unnumbered setlist fallback. v200 fills missing bracketed search-path volume prefixes from the operating-system volume label for logging and comparison. v201 rejects explicit bracketed volume labels that do not match the mounted drive volume label. v202 removes the obsolete group-log utility from the deployment bundle. v203 regenerates legacy placeholder setlists that say the folder never contained an info file. v204 adds postprocess stage status messages and timing details in summary.log. v205 adds eTreeDB setlist song-title fallback during tagging. v206 uses size-aware setlist collision handling and (altN) alternate suffixes. v207 scopes postprocess to current run log tokens and makes overwrite output replacement path-scoped. v208 removes the user-facing overwrite choice, uses in-memory current-run records for postprocess, and optimizes small re-inventory setlist export. v210 fixes in-memory postprocess when current-run records are ShowMetadata objects. v211 adds parallel postprocess setlist/bootlist piece generation by filename-base groups. v212 adds compliant strict date-first parsing, compliant artist Master/As-Is choice, and immediate Quit cleanup alert. v213 keeps GUI inventory startup responsive by moving root preparation into the worker and marshaling GUI prompts back to Tk. v214 uses compact Phase 1 music-directory markers instead of logging every media file while preserving media type and count. v215 logs only one representative media file path and discovers setlist files/media details later from known folders. v216 centralizes input arguments and GUI checkbox metadata in a shared option registry with one canonical destination name per option. v217 caps postprocess ThreadPoolExecutor workers so large filename-group counts cannot create one thread per filename group. v218 replaces camelCase user-facing flags with kebab-case flags and rejects the removed camelCase spellings. v219 adds optional Search Path folder drag/drop on Windows/WSL when TkDND support is available while leaving pure Linux unchanged. v220 restricts that drag/drop support to native Windows and explicitly reports it unavailable in WSL because Windows File Explorer drops do not reach WSL Tk GUI windows. v221 simplifies drag/drop further: only native Windows attempts drag/drop, Windows release builds assume TkDND/tkinterdnd2 is bundled, and WSL/Linux do not advertise the feature. v222 makes existing log and bootlist path matching ignore Windows drive letters and WSL /mnt/<drive> mount prefixes inside the matching layer. v223 makes inventory-time tagging rescan known music folders so all eligible audio files are tagged after Phase 1 logs only one representative sample path. v224 uses existing audio title tags as the last-resort inventory-time track-title source when setlist titles are missing or count-mismatched, writing Unknown for empty/generic title tags and logging the discrepancy. v225 stops tag-track parsing at collector/note prose and trims obvious trailing prose misparsed as a numbered track before falling back to title tags. v226 writes a debug copy of the responsible setlist file to TLOHome/debug, with the matching meta log entry prepended, whenever debug is enabled and tagging writes Unknown track titles. v227 accepts Windows drive-rooted tag paths such as P:\\tagtest when the tagger runs under WSL/Linux by translating them to /mnt/p/tagtest before validation. v228 adds a Quit button behavior for the GUI tagger window that requests cancellation, closes only the tagger window, and leaves the main GUI open. v229 makes standalone and GUI tagger output write to tagT.log and lets standalone/GUI tagger debug mode write Unknown-title setlist diagnostic copies that include music filenames. v230 broadens tag debug setlist copies to title-related skips and file-write errors so skipped/error folders can be diagnosed when debug is true. v231 makes standalone/GUI tagger progress logging append directly to tagT.log so progress lines cannot be lost after the header is created. v232 treats auCDtect audio-analysis result rows as technical report lines, not song-title rows. v233 rejects ordinal event/header lines such as "9th Annual" as track rows and treats literal setlist titles like "unknown" as supplied titles rather than generated Unknown-title failures. v234 parses unnumbered CD/Set song-list blocks and adds a filename-title tagging fallback confirmed against setlist text. v235 broadens parent/sibling setlist discovery and tightens filename-title fallback. v236 parses set/disc track tokens and stops setlists at patch notes. v237 clears TRACKTOTAL, DISCNUMBER and DISCTOTAL when tagging. v238 adds optional --convert-shn / Convert shn support to convert SHN files to FLAC before tagging. v240 logs the effective Convert shn setting when SHN files are detected and prevents SHN sources from reaching the generic tag writer when conversion is enabled. v241 adds mutually exclusive Tag in Place/Tag Copy During Inventory modes, Tag Copy destination validation/confirmation, and Rename Compliantly folder preparation before inventory-time tagging. v242 makes Tag Copy confirmation cancel silent so Quit or window close aborts inventory startup without a second empty alert. v243 relabels Tag in Place/Tag Copy, carries Tag Copy/Rename Compliantly into the standalone/GUI Tag workflow, and makes Add Shows cancellation silent. v244 removes duplicate Tag in Place/Tag Copy/Rename Compliantly checkboxes from the GUI tagger window and makes the tagger inherit those main-window settings. v245 removes the GUI Silent checkbox while keeping --silent, moves Convert shn to the former Silent slot, shortens the console, and throttles setlist export progress messages. v246 removes the Compliant checkbox from Add Shows, makes Add Shows inherit main-window Compliant/Rename Compliantly while ignoring Tag in Place/Tag Copy, and requires Tag in Place or Tag Copy when Rename Compliantly is checked for Tag or Inventory. v249 broadens tagging title recovery from non-standard setlists and uses usable filename titles before falling back to existing title tags. v250 selects the best eTreeDB same-date performance for venue/location and tag-title fallback and generates real setlists from marker-only missing-info files. v251 improves tag title recovery from damaged rows, skips sample audio files, and confirms bad/corrupt files do not stop the rest of a tag run. v252 treats Extras as a sidecar setlist folder and sorts generic TrackNN files by Disc/CD parent folder before tagging multi-disc wrapper releases. v253 caches setlist.fm setlists from same venue/location responses. v254 handles comma-separated setlist lines without spaces. v255 broadens unnumbered setlist blocks. v256 improves unnumbered blocks, embedded disc-track filename ordering, and sparse unknown-title recovery. v257 treats numbered question-mark placeholders as supplied unknown titles so successful tags do not create false Unknown-title debug failures. v258 suppresses noisy successful debug/tag-write logs and keeps only anomalies. v259 enforces numbered setlist starts/sequences while ignoring false numbered prose before real track lists. v262 strips list-position prefixes such as "4 of 28" and t/track row prefixes before writing song-title tags. v265 leaves unidentified shows untouched by copy/delete, rename, and tag operations. v266 treats Tag Copy and Delete Path as a full inventory-time tagging mode and applies compliant names at the transfer target. v267 removes noisy eTreeDB exact-artist debug lines. v268 normalizes song-title tags to regular printable characters. v269 normalizes TLO-written names and tags to ASCII. v270 addresses release hygiene findings. v271 treats foreign-language unknown artist tags as blank. v272/v273 add standalone foreign-language unknown words. v274 makes setlist.fm a strict eTreeDB fallback. v277 adds volume-style release-part sibling aggregation. v278 keeps same-base volume siblings separate while aggregating differing-base collection volumes. v279 preserves trailing parentheticals in exported setlist filenames. v285 formats invalid-FLAC tagging errors as one concise full-path message. v287 accepts Disc One/Late Show-style unnumbered section headings and skips Encore separators without counting them as song titles. v288 parses disc-track dash setlist rows and blocks revision notes from unnumbered fallback titles. v289 broadens safe setlist title parsing and normalizes remaining tag file error lines. v290 splits tag logs into tagsN/tageN text files and names debug files after generated inventory setlist filenames. v291 parses numbered Set I/Set II duration headings and strips embedded encore prefixes from numbered titles. v292 allows implicit numbered list resets without set/disc headings once the restarted sequence is confirmed. v293 compacts complete-path logs after Phase 1 so reused or legacy comp logs keep one representative media row per music directory. v296 adds structured tag reason codes and stops writing debug files for bad audio-file errors. v297 adds elapsed-time output to the tagger GUI completion display. v303 makes Rename Compliantly independent of tagging and performs rename-only full inventory in place. v304 serializes blank-volume roots while parallelizing named-volume groups, restores the versioned Tagger frame title, and relabels the updater duplicate button. v305 removes the startup release-summary sentence and standardizes every GUI title bar on v1.1 Build 305. v306 updates release metadata and documentation only; functional behavior is unchanged. v307 changes the Tagger and Add Shows in-window headings to Traders Little Helper™ while leaving functional behavior unchanged. v308 makes toBeInventoried.txt ignore blank lines and # comment lines as documented. v313 adds a first-run Add Shows guard when bootlist.csv does not exist. v319 hardens cleanup on forced GUI/CLI exits, SHN conversion timeout handling, and setlist file reads. v321 adds packaged Windows ICO and macOS ICNS icon assets and passes packaged icons directly to native builds. v323 preserves compliant trailing parentheticals in Add Shows, full inventory, and tagging destination names. v324 makes Add Shows honor Tag in Place for regular staged folders and duplicate-resolution folders while continuing to ignore Tag Copy. v325 removes the editable TLOHome fields from the Inventory and Search GUIs while keeping myTLO, --TLOHome, and environment precedence. v326 serializes same-physical-drive labeled volumes, runs blank-label roots after labeled roots, fixes deleteBackupFolders path generation, and shows read-only TLOHome labels in both GUIs. v329 updates source version stamping and accepts the injected GitHub release builder display-version stamp. v330 addresses review findings by hardening updater downloads, bounding the artist-query cache, releasing the setlist.fm rate-limit lock while waiting, and cleaning the requirements/test provenance text.
"""


__version__ = "v335"
# TLO-GI package version: v335
__version_summary__ = 'Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.'
# TLO-GI version summary: Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.

import importlib.util
import inspect
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as P
import tlo_postprocess as PP
import tlo_setlist_metadata_lookup as M
import tlo_inventory_update as U
import tlo_tag_lib as T
import logging_lib
import inventory_parser_lib as IPL
from tlo_options import apply_lookup_dependency


# --------------------------------------------------------------------------- #
# Section 5 / Appendix E4 - Date parsing
# --------------------------------------------------------------------------- #

def _norm(text, allow_slash=False):
    return [(m["raw"], m["normalized"]) for m in P._find_date_matches(text, allow_slash=allow_slash)]


@pytest.mark.parametrize("text,expected", [
    ("1-2-34", "2034-01-02"),   # year < 35 -> 20xx
    ("1-2-35", "1935-01-02"),   # year >= 35 -> 19xx
    ("1-2-75", "1975-01-02"),
])
def test_two_digit_year_pivot(text, expected):
    assert _norm(text) == [(text, expected)]


@pytest.mark.parametrize("text,expected", [
    ("96-98", "1996-1998"),
    ("1996-97-98", "1996-1998"),
    ("1996-1998", "1996-1998"),
    ("1917-1939", "1917-1939"),   # all-4-digit ranges: no span cap
])
def test_increasing_ranges(text, expected):
    assert _norm(text) == [(text, expected)]


@pytest.mark.parametrize("text", ["1998-1996", "1998-97", "2010-1996", "19981997"])
def test_decreasing_ranges_rejected(text):
    assert _norm(text) == []


@pytest.mark.parametrize("text", [
    "2001-04-1x", "2001-04-xx", "2004-0x-xx", "202x-xx-xx", "xxxx-xx-xx",
])
def test_x_placeholder_valid(text):
    assert _norm(text) == [(text, text)]


@pytest.mark.parametrize("text", [
    "20xx-xx-xx", "19xx-xx-xx", "2xxx-xx-xx", "1xxx-xx-xx",
    "xxxx-04-14", "2001-x4-14", "2001-xx-14", "2001-04-x4",
])
def test_x_placeholder_invalid(text):
    assert _norm(text) == []


@pytest.mark.parametrize("text", ["44.1/16", "24/96", "16/48", "16-44", "24-96", "16-44.1"])
def test_audio_rate_depth_ignored(text):
    assert _norm(text, allow_slash=True) == []


@pytest.mark.parametrize("text,expected", [
    ("14APR01", "2001-04-14"),
    ("Apr142001", "2001-04-14"),
    ("2001APR14", "2001-04-14"),
    ("14-Apr-2001", "2001-04-14"),
    ("April 14, 2001", "2001-04-14"),
    ("June 15, 2006", "2006-06-15"),
    ("1972 march 9", "1972-03-09"),
])
def test_textual_month_forms(text, expected):
    assert _norm(text) == [(text, expected)]


def test_slash_only_in_setlist_or_tag_context():
    assert _norm("3/9/1972", allow_slash=False) == []
    assert _norm("3/9/1972", allow_slash=True) == [("3/9/1972", "1972-03-09")]


@pytest.mark.parametrize("text", ["2001 04-14", "2001.04-14"])
def test_mixed_separator_numeric_rejected(text):
    assert _norm(text) == []


def test_date_conflict_complete_preferred_over_partial():
    cands = [
        {"raw": "1997-11-05", "normalized": "1997-11-05"},
        {"raw": "November2020", "normalized": "2020-11-xx"},
    ]
    kept = P._filtered_preferred_date_candidates(cands)
    assert [(c["raw"], c["normalized"]) for c in kept] == [("1997-11-05", "1997-11-05")]


def test_dates_compatible_helpers():
    assert P._dates_compatible("1997-11-05", "1997-11-xx") is True
    assert P._most_specific_compatible_date("1997-11-05", "1997-11-xx") == "1997-11-05"
    assert P._dates_compatible("1997-11-05", "1998-01-02") is False


# --------------------------------------------------------------------------- #
# Section 1 / Appendix E1 - Setlist filename construction
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("token,expected", [
    ("19981003", "1998-10-03"),
    ("20020810", "2002-08-10"),
    ("20010414", "2001-04-14"),
])
def test_compact_valid_date_token_for_filename(token, expected):
    assert PP._compact_date_or_range_for_filename(token) == expected


def test_embedded_compact_date_in_filename_base():
    assert PP._normalize_compact_date_tokens_for_filename("IrisDement-19981003") == "IrisDement-1998-10-03"
    assert PP._normalize_compact_date_tokens_for_filename(
        "KarlDensonsTinyUniverse-20020810") == "KarlDensonsTinyUniverse-2002-08-10"


def test_ampersand_and_parens_preserved_unsafe_stripped():
    assert PP._sanitize_setlist_text_preserving_date_dashes("AC & DC (Live)") == "AC&DC(Live)"
    assert PP._sanitize_setlist_text_preserving_date_dashes("Simon & Garfunkel @ MSG!") == "Simon&GarfunkelMSG"


def test_string_dash_string_date_like_preserves_separator_and_dashes():
    # Iris Dement - 1998-10-03 must export as IrisDement-1998-10-03 (Section 1, E1).
    rec = {"show_name": "Iris Dement - 1998-10-03", "artist": "Iris Dement",
           "date": "", "venue": "", "album_name": "1998-10-03",
           "parentheticals": "", "main_dir_path": "", "setlist_file": ""}
    assert PP._setlist_base_from_record(rec) == "IrisDement-1998-10-03"


def test_compliant_dash_case_keeps_dash():
    # Compliant String1 - String2: filename must keep a dash (Section 8.3).
    rec = {"show_name": "James Taylor - (Live)", "artist": "James Taylor",
           "date": "", "venue": "", "album_name": "(Live)",
           "parentheticals": "", "main_dir_path": "", "setlist_file": ""}
    assert PP._setlist_base_from_record(rec) == "JamesTaylor-(Live)"


def test_compact_increasing_year_range_for_filename():
    assert PP._compact_date_or_range_for_filename("19961998") == "1996-1998"


# --------------------------------------------------------------------------- #
# Sections 10-12 - Aggregator output (bootlist.csv / unidentifiedShows.txt)
# --------------------------------------------------------------------------- #

def test_bootlist_volume_path_format():
    assert PP._format_bootlist_volume_path("tloTest 1", "/mnt/p/Artist/show") == "[tloTest 1] /Artist/show"


def test_unidentified_shows_append_sort_dedupe(tmp_path):
    home = str(tmp_path)
    target = os.path.join(home, "unidentifiedShows.txt")
    with open(target, "w", encoding="utf-8") as fh:
        fh.write("/z/older\n/a/older\n")
    PP._write_unidentified_shows(home, ["/m/new", "/a/older", "/m/new"])
    lines = open(target, encoding="utf-8").read().splitlines()
    assert lines == ["/a/older", "/m/new", "/z/older"]  # sorted, deduped, prior kept


# --------------------------------------------------------------------------- #
# Section 16 / Appendix E8 - Log token range
# --------------------------------------------------------------------------- #

def test_tokens_unique_within_36():
    home = tempfile.mkdtemp()
    toks = logging_lib.allocate_log_tokens(home, 36)
    assert len(toks) == 36 and len(set(toks)) == 36
    assert all(len(t) == 1 for t in toks)


def test_more_than_36_tokens_is_error():
    home = tempfile.mkdtemp()
    with pytest.raises(Exception):
        logging_lib.allocate_log_tokens(home, 37)


# --------------------------------------------------------------------------- #
# Section 7.20 - Selected setlist metadata extraction
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("line,expected", [
    ("Artist: Wilco", ("artist", "Wilco")),
    ("Artist - Wilco", ("artist", "Wilco")),
    ("Venue: Fillmore", ("venue", "Fillmore")),
    ("Venue - Fillmore West", ("venue", "Fillmore West")),
    ("Location: Boston, MA", ("location", "Boston, MA")),
    ("Date: 1998-10-03", ("date", "1998-10-03")),
])
def test_explicit_metadata_labels(line, expected):
    assert M._explicit_metadata_match(line) == expected


def test_prose_label_not_metadata():
    assert M._explicit_metadata_match("the venue was packed that night") is None


@pytest.mark.parametrize("line", [
    "01. Intro", "1)Intro", "1) Intro", "03 - Song", "01 TrackTitle",
    "1 TrackTitle", "01 [08:23] TrackTitle", "Track01", "d1t01 Song",
    "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6",
])
def test_tracklist_and_hash_boundaries(line):
    assert M._is_setlist_metadata_scan_boundary(line) is True


def test_filename_colon_hash_line_is_metadata_boundary():
    line = "01 Highway Star.flac:81b2cf16b83390c1875f67afb2d37350"
    assert M._is_setlist_metadata_scan_boundary(line) is True


def test_filename_colon_hash_run_is_confirmed_boundary():
    lines = [
        "Artist: Deep Purple",
        "Date: 1972-08-16",
        "01 Highway Star.flac:81b2cf16b83390c1875f67afb2d37350",
        "02 Smoke On The Water.flac:91b2cf16b83390c1875f67afb2d37351",
    ]
    assert M._is_confirmed_tracklist_boundary(lines, 2, lines[:2]) is True


@pytest.mark.parametrize("line", ["09-20-1941", "1998-10-03", "Date: 1998-10-03", "Grand Ole Opry"])
def test_date_headers_are_not_boundaries(line):
    # v167: a valid date header line must not terminate metadata scanning.
    assert M._is_setlist_metadata_scan_boundary(line) is False


def test_venue_tail_cleaning_strips_airdate_and_date():
    raw = "Madison Square Garden, New York 23/12/72; Air date: Jan 5 1973"
    assert M._trim_explicit_metadata_value_tail(raw) == "Madison Square Garden, New York 23/12/72"
    assert M._strip_trailing_performance_date_from_metadata_value(raw) == "Madison Square Garden, New York"


def _support():
    base = tempfile.mkdtemp()
    with open(os.path.join(base, "venues.txt"), "w") as fh:
        fh.write("Parc des Expos\nStadthalle\nMadison Square Garden\n")
    with open(os.path.join(base, "cities.csv"), "w") as fh:
        fh.write("city^region^country\nReims^^France\nSt. Ingbert^^Germany\n")
    with open(os.path.join(base, "countries.csv"), "w") as fh:
        fh.write("name^code\nFrance^FR\nGermany^DE\n")
    return M._SupportData(base)


def test_comma_combined_venue_location_split():
    # Parc des Expos, Reims, France -> Venue = Parc des Expos, Location = Reims France
    venue, city, region, country, *_ = M._split_unlabeled_combined_venue_location_line(
        "Parc des Expos, Reims, France", _support())
    assert venue == "Parc des Expos"
    assert city == "Reims"
    assert country == "France"


def test_space_combined_venue_location_split():
    # Stadthalle St. Ingbert Germany -> Venue = Stadthalle, Location = St. Ingbert Germany
    venue, city, region, country, *_ = M._split_unlabeled_space_combined_venue_location_line(
        "Stadthalle St. Ingbert Germany", _support())
    assert venue == "Stadthalle"
    assert city == "St. Ingbert"
    assert country == "Germany"


# --------------------------------------------------------------------------- #
# Revision note v191 - Tagger setlist track parsing / checksum rows
# --------------------------------------------------------------------------- #

def test_tagger_ignores_filename_colon_hash_rows(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "01 Highway Star.flac:81b2cf16b83390c1875f67afb2d37350\n"
        "02 Smoke On The Water.flac:91b2cf16b83390c1875f67afb2d37351\n",
        encoding="utf-8",
    )
    assert T.parse_setlist_tracks(str(setlist)) == []


def test_tagger_stops_before_filename_colon_hash_run(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "Tracks:\n"
        "1 Highway Star\n"
        "2 Smoke On The Water\n"
        "01 Highway Star.flac:81b2cf16b83390c1875f67afb2d37350\n"
        "02 Smoke On The Water.flac:91b2cf16b83390c1875f67afb2d37351\n"
        "03 Later Checksum Noise That Must Not Become A Track\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [(t["normalized_number"], t["title"]) for t in tracks] == [
        (1, "Highway Star"),
        (2, "Smoke On The Water"),
    ]


def test_tagger_filename_title_fallback_patterns(tmp_path):
    files = []
    for name in [
        "01 Highway Star.flac",
        "d1t02-Smoke On The Water.flac",
        "03Lazy.flac",
        "untitled.flac",
    ]:
        path = tmp_path / name
        path.write_bytes(b"")
        files.append(str(path))
    tracks = T.tracks_from_audio_filenames(files)
    assert [(t["normalized_number"], t["title"]) for t in tracks] == [
        (1, "Highway Star"),
        (2, "Smoke On The Water"),
        (3, "Lazy"),
        (4, "unknown"),
    ]


def test_tagger_no_setlist_uses_filename_titles_and_unknown(tmp_path, monkeypatch):
    audio1 = tmp_path / "01 Highway Star.flac"
    audio2 = tmp_path / "notes.flac"
    audio1.write_bytes(b"")
    audio2.write_bytes(b"")

    fake_record = SimpleNamespace(artist="Deep Purple", date="1972-08-16", venue="Budokan", location="Tokyo Japan")
    monkeypatch.setattr(T, "_extract_metadata_for_group", lambda *args, **kwargs: (fake_record, [], []))
    written = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: written.append((path, artist, album, track_number, title, total_tracks)))

    config = SimpleNamespace(compliant=False)
    group = {
        "main_dir_path": str(tmp_path),
        "main_dir_name": tmp_path.name,
        "music_files": [str(audio1), str(audio2)],
        "setlist_file": "",
        "setlist_files": [],
        "music_dirs": [str(tmp_path)],
        "music_file_count": 2,
        "group_number": 1,
    }
    messages = []
    stats = T.process_tagging_group(config, group, artist_matcher=None, emit=messages.append)

    assert {key: stats[key] for key in ["groups", "tagged", "skipped", "errors"]} == {"groups": 1, "tagged": 2, "skipped": 0, "errors": 0}
    assert [(item[3], item[4]) for item in written] == [("01", "Highway Star"), ("02", "unknown")]
    assert all(item[2] == "Deep Purple 1972-08-16 Budokan Tokyo Japan" for item in written)


# --------------------------------------------------------------------------- #
# v194 - Compliant Billboard MP3 year folder special case
# --------------------------------------------------------------------------- #

def _mp3_year_group(path):
    return {
        "main_dir_path": path,
        "music_files": [os.path.join(path, "01 Song.mp3"), os.path.join(path, "02 Song.mp3")],
    }


def test_compliant_mp3_year_show_name_requires_billboard_path():
    assert P._compliant_mp3_year_show_name(_mp3_year_group("/music/Billboard Top Hits/1961"), "1961") == "1961"
    assert P._compliant_mp3_year_show_name(_mp3_year_group("/music/Top Hits/1961"), "1961") == ""


def test_compliant_mp3_year_show_name_requires_mp3_year_and_range():
    assert P._compliant_mp3_year_show_name(_mp3_year_group("/music/Billboard/1958"), "1958") == ""
    assert P._compliant_mp3_year_show_name(_mp3_year_group("/music/Billboard/2006"), "2006") == ""
    assert P._compliant_mp3_year_show_name(_mp3_year_group("/music/Billboard/1961"), "1961-2004") == ""
    flac_group = {
        "main_dir_path": "/music/Billboard/1961",
        "music_files": ["/music/Billboard/1961/01 Song.flac"],
    }
    assert P._compliant_mp3_year_show_name(flac_group, "1961") == ""


def test_compliant_billboard_mp3_year_setlist_base_does_not_use_parent_range():
    rec = {
        "show_name": "1961",
        "artist": "",
        "date": "",
        "venue": "",
        "album_name": "",
        "location": "",
        "parentheticals": "",
        "main_dir_path": "/mnt/e/Billboard/1960-2004/1961",
        "setlist_file": "",
    }
    assert PP._setlist_base_from_record(rec) == "1961"


# --------------------------------------------------------------------------- #
# Revision notes v170-v185 - Add Shows updater duplicate detection
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("show,date,expected", [
    ("Wilco 2002-08-10 The Vic Chicago IL", "2002-08-10", True),
    ("Wilco 2002-08-10 The Vic Chicago IL", "2002-08-11", False),
    ("Phish 19971205 MSG", "1997-12-05", True),   # compact date normalized in show name
    ("Some Album Name", "2002-08-10", False),
])
def test_updater_show_has_date(show, date, expected):
    assert U._show_has_date(show, date) is expected


@pytest.mark.parametrize("show,artist,date,expected", [
    ("Wilco 2002-08-10 The Vic", "Wilco", "2002-08-10", True),
    ("Wilco 2002-08-10 The Vic", "Phish", "2002-08-10", False),
    ("Wilco 2002-08-10 The Vic", "Wilco", "2001-01-01", False),
])
def test_updater_artist_and_date(show, artist, date, expected):
    assert U._show_has_artist_and_date(show, artist, date, None) is expected


def test_updater_compliant_folder_parsing():
    s1d = U._compliant_string_date_string2("/x/Wilco 2002-08-10 The Vic")
    assert s1d and s1d["string1_stripped"] == "Wilco" and s1d["date_norm"] == "2002-08-10"
    dash = U._compliant_string_dash_string2("/x/James Taylor - (Live)")
    assert dash and dash["artist"] == "James Taylor" and dash["show_name"] == "James Taylor - (Live)"

# --------------------------------------------------------------------------- #
# v193 - Tag During Inventory
# --------------------------------------------------------------------------- #

def test_tag_log_path_uses_inventory_log_token(tmp_path):
    config = type("C", (), {"TLOHome": str(tmp_path)})()
    logging_lib.setup_logging(config)
    config.logs.start_search_path("/music/root", 1, log_token="7")
    assert os.path.basename(config.logs.paths.tag_success) == "tags7.txt"
    assert os.path.basename(config.logs.paths.tag_error) == "tage7.txt"
    config.logs.tag("TAG_DURING_INVENTORY: enabled")
    assert "TAG_DURING_INVENTORY" in open(config.logs.paths.tag_success, encoding="utf-8").read()
    assert "TAG_DURING_INVENTORY" not in open(config.logs.paths.tag_error, encoding="utf-8").read()


def test_inventory_time_tagging_uses_unknown_when_show_name_blank(tmp_path, monkeypatch):
    import tlo_tag_lib as T
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 First Song.flac"
    audio2 = tmp_path / "Mystery.flac"
    audio1.write_bytes(b"not real audio; write_audio_tags is patched")
    audio2.write_bytes(b"not real audio; write_audio_tags is patched")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(
        group_number=1,
        main_dir_name="Bad Metadata Folder",
        main_dir_path=str(tmp_path),
        setlist_file="",
        music_file_count=2,
        artist="",
        album_name="",
        show_name="",
    )
    group = {
        "main_dir_path": str(tmp_path),
        "main_dir_name": "Bad Metadata Folder",
        "setlist_file": "",
        "music_files": [str(audio1), str(audio2)],
    }

    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((os.path.basename(path), artist, album, track_number, title)))
    messages = []
    stats = T.tag_group_with_record(
        config,
        group,
        record,
        emit=messages.append,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        metadata_problems=["unable to create show name"],
    )

    assert stats["tagged"] == 2
    assert calls == [
        ("01 First Song.flac", "Unknown", "Unknown", "01", "Unknown"),
        ("Mystery.flac", "Unknown", "Unknown", "02", "Unknown"),
    ]
    assert any("no setlist found" in str(message) for message in messages)
    assert any("writing Unknown" in str(message) for message in messages)
    assert any("show name not determined" in str(message) for message in messages)


def test_inventory_time_tagging_rescans_folder_from_sample_path(tmp_path, monkeypatch):
    import tlo_tag_lib as T
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    show_dir = tmp_path / "Artist 2001-04-14 Venue City ST"
    show_dir.mkdir()
    audio1 = show_dir / "01 First.flac"
    audio2 = show_dir / "02 Second.flac"
    audio3 = show_dir / "03 Third.flac"
    for audio in (audio1, audio2, audio3):
        audio.write_bytes(b"not real audio; write_audio_tags is patched")
    setlist = show_dir / "info.txt"
    setlist.write_text("1 First\n2 Second\n3 Third\n", encoding="utf-8")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(
        group_number=1,
        main_dir_name=show_dir.name,
        main_dir_path=str(show_dir),
        setlist_file=str(setlist),
        music_file_count=3,
        artist="Artist",
        date="2001-04-14",
        venue="Venue",
        location="City ST",
        show_name="Artist 2001-04-14 Venue City ST",
    )
    group = {
        "main_dir_path": str(show_dir),
        "main_dir_name": show_dir.name,
        "music_dirs": [str(show_dir)],
        "setlist_file": str(setlist),
        # v215+ inventory discovery carries only one representative media path.
        "music_files": [str(audio1)],
    }

    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((os.path.basename(path), track_number, title, total_tracks)))

    stats = T.tag_group_with_record(
        config,
        group,
        record,
        emit=lambda _text: None,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        metadata_problems=[],
    )

    assert stats["tagged"] == 3
    assert calls == [
        ("01 First.flac", "01", "First", 3),
        ("02 Second.flac", "02", "Second", 3),
        ("03 Third.flac", "03", "Third", 3),
    ]


def test_inventory_time_tagging_falls_back_to_filenames_on_setlist_mismatch(tmp_path, monkeypatch):
    import tlo_tag_lib as T
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "d1t01 Opening.flac"
    audio2 = tmp_path / "d1t02 Closing.flac"
    setlist = tmp_path / "info.txt"
    audio1.write_bytes(b"not real audio; write_audio_tags is patched")
    audio2.write_bytes(b"not real audio; write_audio_tags is patched")
    setlist.write_text("1 Only One Track\n", encoding="utf-8")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(
        group_number=1,
        main_dir_name="Good Metadata Folder",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        music_file_count=2,
        artist="Artist",
        date="2001-04-14",
        venue="Venue",
        location="City ST",
        show_name="Artist 2001-04-14 Venue City ST",
    )
    group = {
        "main_dir_path": str(tmp_path),
        "main_dir_name": "Good Metadata Folder",
        "setlist_file": str(setlist),
        "music_files": [str(audio2), str(audio1)],
    }

    title_tags = {
        str(audio1): "01. Title From Tag",
        str(audio2): "track 2",
    }
    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path: title_tags.get(path, ""))
    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((os.path.basename(path), artist, album, track_number, title)))
    messages = []
    stats = T.tag_group_with_record(
        config,
        group,
        record,
        emit=messages.append,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        metadata_problems=[],
    )

    assert stats["tagged"] == 2
    assert calls == [
        ("d1t01 Opening.flac", "Artist", "Artist 2001-04-14 Venue City ST", "01", "Title From Tag"),
        ("d1t02 Closing.flac", "Artist", "Artist 2001-04-14 Venue City ST", "02", "Unknown"),
    ]
    assert any("track count mismatch" in str(message) for message in messages)
    assert any("title tags" in str(message) for message in messages)
    assert any("writing Unknown" in str(message) for message in messages)


# --------------------------------------------------------------------------- #
# v224 - Existing title-tag fallback for inventory-time track titles
# --------------------------------------------------------------------------- #

def test_audio_title_tag_fallback_accepts_and_rejects_expected_forms():
    assert T._usable_title_from_audio_title_tag("Bertha") == ("Bertha", True)
    assert T._usable_title_from_audio_title_tag("Scarlet Begonias") == ("Scarlet Begonias", True)
    assert T._usable_title_from_audio_title_tag("001. Fire On The Mountain") == ("Fire On The Mountain", True)
    assert T._usable_title_from_audio_title_tag("") == ("Unknown", False)
    assert T._usable_title_from_audio_title_tag("d1t01") == ("Unknown", False)
    assert T._usable_title_from_audio_title_tag("Track 7") == ("Unknown", False)


def test_inventory_time_title_tag_fallback_handles_bad_title_tags(tmp_path, monkeypatch):
    import tlo_tag_lib as T
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 file.flac"
    audio2 = tmp_path / "02 file.flac"
    audio3 = tmp_path / "03 file.flac"
    for path in (audio1, audio2, audio3):
        path.write_bytes(b"not real audio; title tags are patched")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Only One Track\n", encoding="utf-8")

    title_tags = {
        str(audio1): "Help On The Way",
        str(audio2): "02: Slipknot!",
        str(audio3): "d1t03",
    }
    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path: title_tags.get(path, ""))

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(group_number=1, main_dir_name="Title Tags", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=3, artist="Artist",
                          date="1975-08-13", venue="Venue", location="City ST",
                          show_name="Artist 1975-08-13 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Title Tags",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2), str(audio3)]}

    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((os.path.basename(path), track_number, title)))
    messages = []
    stats = T.tag_group_with_record(config, group, record, emit=messages.append,
                                    allow_unknown_metadata=True,
                                    fallback_to_filenames_on_track_problem=True,
                                    metadata_problems=[])

    assert stats["tagged"] == 3
    assert stats["title_tag_folders"] == [str(tmp_path)]
    assert calls == [
        ("01 file.flac", "01", "Help On The Way"),
        ("02 file.flac", "02", "Slipknot!"),
        ("03 file.flac", "03", "Unknown"),
    ]
    assert any("track count mismatch" in str(message) for message in messages)
    assert any("writing Unknown" in str(message) for message in messages)



# --------------------------------------------------------------------------- #
# v225 - Stop before collector/note prose and avoid false title-tag fallback
# --------------------------------------------------------------------------- #

def test_setlist_parser_stops_before_note_prose_track_like_lines(tmp_path):
    setlist = tmp_path / "grandmothers-info.txt"
    setlist.write_text(
        "Grandmothers Broadway Club, San Francisco, Ca 5-31-81\n"
        "Audience Recording, Incomplete as it cuts off.\n\n"
        "01 Intro\n"
        "02 Burn You With Cold\n"
        "03 King Kong Meets Dr. Strange\n"
        "04 You Didn't Try to Call Me\n"
        "05 Lonesome Cowboy Burt\n"
        "06 Those Lonely, Lonely Nights\n"
        "07 Banter/Larry the Dwarf Story\n"
        "08 I Can't Breathe\n"
        "09 Son of Orange County Pt.1\n"
        "10 Son of Orange County cont.\n"
        "11 Who are the Brain Police? >\n"
        "12 Cutester Patrol_\n\n"
        "note to collectors.\n"
        "40 years, its hard to remember where and who I traded for these shows.\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))
    assert len(tracks) == 12
    assert tracks[-1]["title"] == "Cutester Patrol_"
    assert all(track["original_number"] != 40 for track in tracks)


def test_inventory_tagging_uses_setlist_when_extra_tail_is_obvious_prose(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio = []
    for idx in range(1, 13):
        path = tmp_path / f"{idx:02d} track.flac"
        path.write_bytes(b"not real audio; write_audio_tags is patched")
        audio.append(str(path))
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "01 Intro\n"
        "02 Burn You With Cold\n"
        "03 King Kong Meets Dr. Strange\n"
        "04 You Didn't Try to Call Me\n"
        "05 Lonesome Cowboy Burt\n"
        "06 Those Lonely, Lonely Nights\n"
        "07 Banter/Larry the Dwarf Story\n"
        "08 I Can't Breathe\n"
        "09 Son of Orange County Pt.1\n"
        "10 Son of Orange County cont.\n"
        "11 Who are the Brain Police? >\n"
        "12 Cutester Patrol_\n"
        "40 years, its hard to remember where and who I traded for these shows.\n",
        encoding="utf-8",
    )

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(group_number=1, main_dir_name="Grandmothers", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=12, artist="Grandmothers",
                          date="1981-05-31", venue="Broadway", location="San Francisco, CA",
                          show_name="Grandmothers 1981-05-31 Broadway San Francisco, CA")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Grandmothers",
             "setlist_file": str(setlist), "music_files": audio}

    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path: "track 1")
    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((os.path.basename(path), track_number, title)))
    messages = []
    stats = T.tag_group_with_record(config, group, record, emit=messages.append,
                                    allow_unknown_metadata=True,
                                    fallback_to_filenames_on_track_problem=True,
                                    metadata_problems=[])

    assert stats["tagged"] == 12
    assert stats["title_tag_folders"] == []
    assert calls[0] == ("01 track.flac", "01", "Intro")
    assert calls[1] == ("02 track.flac", "02", "Burn You With Cold")
    assert calls[-1] == ("12 track.flac", "12", "Cutester Patrol_")
    assert not any("using existing audio title tags" in str(message) for message in messages)


# --------------------------------------------------------------------------- #
# v226 - Debug setlist copies for Unknown tag titles
# --------------------------------------------------------------------------- #

def test_debug_true_does_not_write_setlist_copy_when_unknown_titles_are_written(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 file.flac"
    audio2 = tmp_path / "02 file.flac"
    audio1.write_bytes(b"not real audio; write_audio_tags is patched")
    audio2.write_bytes(b"not real audio; write_audio_tags is patched")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Only One Setlist Track\n", encoding="utf-8")

    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path: "track 1")
    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((track_number, title)))

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(group_number=3, main_dir_name="Debug Show", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Debug Show",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}
    messages = []
    stats = T.tag_group_with_record(config, group, record, emit=messages.append,
                                    allow_unknown_metadata=True,
                                    fallback_to_filenames_on_track_problem=True,
                                    metadata_problems=[],
                                    meta_log_entry="SHOW_NAME: Artist 1977-05-08 Venue City ST\nSETLIST_FILE: " + str(setlist) + "\nEND_SHOW_METADATA\n")

    assert stats["tagged"] == 2
    assert calls == [("01", "Unknown"), ("02", "Unknown")]
    assert not (tmp_path / "debug").exists()
    assert not any("wrote tag debug setlist copy" in str(message) for message in messages)


def test_debug_false_does_not_write_unknown_title_setlist_copy(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 file.flac"
    audio2 = tmp_path / "02 file.flac"
    audio1.write_bytes(b"not real audio; write_audio_tags is patched")
    audio2.write_bytes(b"not real audio; write_audio_tags is patched")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Only One Setlist Track\n", encoding="utf-8")

    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path: "d1t01")
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: None)

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(group_number=1, main_dir_name="No Debug", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "No Debug",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}
    T.tag_group_with_record(config, group, record, emit=lambda _text: None,
                            allow_unknown_metadata=True,
                            fallback_to_filenames_on_track_problem=True,
                            metadata_problems=[])

    assert not (tmp_path / "debug").exists()

# --------------------------------------------------------------------------- #
# v195 - Volume-aware inventory/log handling and video path pattern matching
# --------------------------------------------------------------------------- #

def test_log_header_prepends_volume_label_to_search_path(tmp_path):
    config = type("C", (), {"TLOHome": str(tmp_path)})()
    logging_lib.setup_logging(config)
    config.logs.start_search_path("/music/root", 1, log_token="8", volume_label="VOL1")
    text = open(config.logs.paths.groups, encoding="utf-8").read()
    assert "# groupsLog for search path: [VOL1] /music/root" in text
    assert "SEARCH_PATH: [VOL1] /music/root" in text


def test_empty_volume_label_is_preserved_for_log_header(tmp_path):
    config = type("C", (), {"TLOHome": str(tmp_path)})()
    logging_lib.setup_logging(config)
    config.logs.start_search_path("/music/root", 1, log_token="9", volume_label="")
    text = open(config.logs.paths.groups, encoding="utf-8").read()
    assert "# groupsLog for search path: []" in text
    assert "SEARCH_PATH: []" in text


def test_volume_action_filtering_keeps_append_and_skip_rows_but_removes_overwrite_rows():
    from tlo_bootlist_volume_policy import filter_rows_for_volume_actions
    rows = [
        {"Show": "Old A", "VolumePath": "[VOL1] /old/a", "Volume": "VOL1", "Path": "/old/a"},
        {"Show": "Old B", "VolumePath": "[VOL2] /old/b", "Volume": "VOL2", "Path": "/old/b"},
        {"Show": "Old Empty", "VolumePath": "[] /old/empty", "Volume": "", "Path": "/old/empty"},
    ]
    kept = filter_rows_for_volume_actions(rows, {"vol1": "overwrite", "vol2": "append", "": "skip"})
    assert [(row["Show"], row["VolumePath"]) for row in kept] == [
        ("Old B", "[VOL2] /old/b"),
        ("Old Empty", "[] /old/empty"),
    ]


def test_postprocess_merges_existing_rows_according_to_volume_actions(tmp_path):
    from tlo_bootlist_volume_policy import write_bootlist_rows
    home = str(tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    write_bootlist_rows(home, [
        {"Show": "Overwrite Old", "VolumePath": "[VOL1] /old/one"},
        {"Show": "Append Old", "VolumePath": "[VOL2] /old/two"},
    ])
    meta = logs_dir / "meta0.log"
    meta.write_text(
        "SHOW_NAME: New Show\n"
        "SHOW_IN_CONFLICT: no\n"
        "MAIN_DIR_PATH: /new/path\n"
        "GROUP_NUMBER: 1\n"
        "MAIN_DIR_NAME: New Show\n"
        "SETLIST_FILE: \n"
        "MUSIC_FILE_COUNT: 1\n"
        "VOLUME_LABEL: VOL1\n"
        "ARTIST: New Artist\n"
        "DATE: 2001-04-14\n"
        "VENUE: New Venue\n"
        "LOCATION: New City ST\n"
        "PARENTHETICALS: \n"
        "ALBUM_NAME: \n"
        "IS_24_BIT: no\n"
        "END_SHOW_METADATA\n",
        encoding="utf-8",
    )
    config = SimpleNamespace(TLOHome=home, inventory_volume_actions={"vol1": "reinventory", "vol2": "append"}, silent=True)
    PP.postprocess_metadata_outputs(config)
    rows = PP.read_bootlist_rows(home) if hasattr(PP, "read_bootlist_rows") else []
    # read through shared helper to avoid relying on postprocess internals
    from tlo_bootlist_volume_policy import read_bootlist_rows
    rows = read_bootlist_rows(home)
    assert ("Overwrite Old", "[VOL1] /old/one") not in [(r["Show"], r["VolumePath"]) for r in rows]
    assert ("Append Old", "[VOL2] /old/two") in [(r["Show"], r["VolumePath"]) for r in rows]
    assert ("New Show", "[VOL1] /new/path") in [(r["Show"], r["VolumePath"]) for r in rows]




def _write_minimal_meta(logs_dir, token, show, path, volume="VOL1"):
    (logs_dir / f"meta{token}.log").write_text(
        f"SHOW_NAME: {show}\n"
        "SHOW_IN_CONFLICT: no\n"
        f"MAIN_DIR_PATH: {path}\n"
        "GROUP_NUMBER: 1\n"
        f"MAIN_DIR_NAME: {show}\n"
        "SETLIST_FILE: \n"
        "MUSIC_FILE_COUNT: 1\n"
        f"VOLUME_LABEL: {volume}\n"
        "ARTIST: New Artist\n"
        "DATE: 2001-04-14\n"
        "VENUE: New Venue\n"
        "LOCATION: New City ST\n"
        "PARENTHETICALS: \n"
        "ALBUM_NAME: \n"
        "IS_24_BIT: no\n"
        "END_SHOW_METADATA\n",
        encoding="utf-8",
    )


def test_postprocess_uses_only_current_run_log_tokens(tmp_path):
    from tlo_bootlist_volume_policy import read_bootlist_rows
    home = str(tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    _write_minimal_meta(logs_dir, "OLD", "Old Log Show", "/old/path")
    _write_minimal_meta(logs_dir, "NEW", "Current Run Show", "/new/path")
    config = SimpleNamespace(TLOHome=home, inventory_volume_actions={}, inventory_path_actions=[], current_run_log_tokens=["NEW"], silent=True)

    PP.postprocess_metadata_outputs(config)

    rows = read_bootlist_rows(home)
    assert [(r["Show"], r["Path"]) for r in rows] == [("Current Run Show", "/new/path")]


def test_path_scoped_overwrite_only_replaces_matching_subtree_rows(tmp_path):
    from tlo_bootlist_volume_policy import write_bootlist_rows, read_bootlist_rows
    home = str(tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    write_bootlist_rows(home, [
        {"Show": "Old MP3", "VolumePath": "[VOL1] /mnt/e/MP3/Old"},
        {"Show": "Old Other", "VolumePath": "[VOL1] /mnt/e/Other"},
    ])
    _write_minimal_meta(logs_dir, "N", "New MP3", "/mnt/e/MP3/New")
    config = SimpleNamespace(
        TLOHome=home,
        inventory_volume_actions={"vol1": "reinventory"},
        inventory_path_actions=[{"volume": "VOL1", "volume_key": "vol1", "path": "/mnt/e/MP3", "action": "reinventory"}],
        current_run_log_tokens=["N"],
        silent=True,
    )

    PP.postprocess_metadata_outputs(config)

    rows = read_bootlist_rows(home)
    values = [(r["Show"], r["VolumePath"]) for r in rows]
    assert ("Old MP3", "[VOL1] /mnt/e/MP3/Old") not in values
    assert ("Old Other", "[VOL1] /Other") in values
    assert ("New MP3", "[VOL1] /MP3/New") in values


def test_compliant_video_folder_checks_path_subdirs_for_patterns():
    record = P.ShowMetadata(
        group_number=1,
        main_dir_name="VIDEO_TS",
        main_dir_path="/archive/video/Deep Purple 1972-08-16 Budokan Tokyo Japan/VIDEO_TS",
        setlist_file="",
        music_file_count=1,
    )
    group = {
        "main_dir_path": record.main_dir_path,
        "main_dir_name": record.main_dir_name,
        "music_dirs": [record.main_dir_path],
        "music_files": [record.main_dir_path + "/VTS_01_1.VOB"],
    }
    observations = []
    text, source = P._compliant_pattern_text_for_group(record, group, observations)
    assert text == "Deep Purple 1972-08-16 Budokan Tokyo Japan"
    assert source.endswith("Deep Purple 1972-08-16 Budokan Tokyo Japan")
    assert any("video folder matched" in item for item in observations)


# --------------------------------------------------------------------------- #
# v196/v208 - Group-log decisions, size-aware alternates, and path-scoped re-inventory
# --------------------------------------------------------------------------- #

def test_existing_volume_decisions_use_group_logs_not_bootlist(tmp_path):
    from tlo_bootlist_volume_policy import write_bootlist_rows
    import inventory_list_lib as IL

    home = str(tmp_path)
    write_bootlist_rows(home, [{"Show": "Old", "VolumePath": "[VOL1] /old"}])
    calls = []
    config = SimpleNamespace(
        TLOHome=home,
        silent=True,
        volume_action_callback=lambda volume, existing, queued: calls.append((volume, existing, queued)) or "skip",
    )

    actions = IL._resolve_existing_volume_actions(config, [("/new", "", "VOL1", "volkey")])
    assert actions[0]["action"] == "new"
    assert actions[0]["volume_key"] == "vol1"
    assert calls == []


def test_existing_volume_decisions_count_group_log_headers(tmp_path):
    import inventory_list_lib as IL

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "groups0.log").write_text(
        "# groupsLog for search path: [VOL1] /old/root\n"
        "SEARCH_PATH: [VOL1] /old/root\n"
        "GROUP: 1\n",
        encoding="utf-8",
    )
    calls = []
    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        silent=True,
        volume_action_callback=lambda volume, existing, queued: calls.append((volume, existing, queued)) or "skip",
    )

    actions = IL._resolve_existing_volume_actions(config, [("/old/root/MP3", "", "VOL1", "volkey")])
    assert actions[0]["action"] == "reinventory"
    assert actions[0]["volume_key"] == "vol1"
    assert actions[0]["related_group_paths"] == ["/old/root"]
    assert calls == []


def test_setlist_collision_same_size_reuses_original(tmp_path):
    setlists_dir = tmp_path / "setlists"
    setlists_dir.mkdir()
    original = setlists_dir / "Artist2001-04-14Venue.txt"
    original.write_text("same setlist\n", encoding="utf-8")
    used = {original.name}

    # Same byte size is treated as the same setlist without reading contents.
    name, should_write = PP._resolve_setlist_filename_for_text(
        "Artist2001-04-14Venue", str(setlists_dir), "differenttxt\n", used
    )

    assert name == "Artist2001-04-14Venue.txt"
    assert should_write is False
    assert sorted(path.name for path in setlists_dir.glob("*.txt")) == ["Artist2001-04-14Venue.txt"]


def test_setlist_collision_different_size_uses_alt_suffix(tmp_path):
    setlists_dir = tmp_path / "setlists"
    setlists_dir.mkdir()
    (setlists_dir / "Artist2001-04-14Venue.txt").write_text("first\n", encoding="utf-8")
    (setlists_dir / "Artist2001-04-14Venue(alt1).txt").write_text("second longer\n", encoding="utf-8")
    used = {"Artist2001-04-14Venue.txt", "Artist2001-04-14Venue(alt1).txt"}

    name, should_write = PP._resolve_setlist_filename_for_text(
        "Artist2001-04-14Venue", str(setlists_dir), "third and different size\n", used
    )

    assert name == "Artist2001-04-14Venue(alt2).txt"
    assert should_write is True


def test_setlist_collision_existing_alt_same_size_reuses_alt(tmp_path):
    setlists_dir = tmp_path / "setlists"
    setlists_dir.mkdir()
    (setlists_dir / "Artist2001-04-14Venue.txt").write_text("first\n", encoding="utf-8")
    (setlists_dir / "Artist2001-04-14Venue(alt1).txt").write_text("same length\n", encoding="utf-8")
    used = {"Artist2001-04-14Venue.txt", "Artist2001-04-14Venue(alt1).txt"}

    name, should_write = PP._resolve_setlist_filename_for_text(
        "Artist2001-04-14Venue", str(setlists_dir), "12345678901", used
    )

    assert name == "Artist2001-04-14Venue(alt1).txt"
    assert should_write is False

# --------------------------------------------------------------------------- #
# v197 - Explicit search-path volume prefixes and normalized volume matching
# --------------------------------------------------------------------------- #

def test_search_path_accepts_bracketed_volume_prefix_without_space():
    import inventory_list_lib as IL

    volume, path = IL._split_optional_volume_prefix("[string]E:")
    assert volume == "string"
    assert path == "E:"
    assert IL._normalize_input_path(path) == "/mnt/e"

    volume, path = IL._split_optional_volume_prefix("[string]/mnt/e")
    assert volume == "string"
    assert path == "/mnt/e"
    assert IL._normalize_input_path(path) == "/mnt/e"


def test_search_path_without_bracketed_volume_uses_empty_volume():
    import inventory_list_lib as IL

    volume, path = IL._split_optional_volume_prefix("/mnt/e/music")
    assert volume == ""
    assert path == "/mnt/e/music"


def test_inventory_file_bracketed_volume_prefix_is_not_part_of_physical_path(tmp_path):
    import inventory_list_lib as IL

    inv = tmp_path / "toBeInventoried.txt"
    inv.write_text("[VOL A]/mnt/e/music -$slam Artist Name\n", encoding="utf-8")
    parsed = IL._parse_inventory_file(str(inv))
    assert parsed == [("[VOL A]/mnt/e/music", "/mnt/e/music", "Artist Name", "VOL A")]


def test_group_log_volume_matching_normalizes_case_and_brackets(tmp_path):
    from tlo_bootlist_volume_policy import count_group_logs_by_volume, volume_key

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "groups0.log").write_text("SEARCH_PATH: [Vol A] /mnt/e/music\n", encoding="utf-8")
    counts = count_group_logs_by_volume(str(tmp_path))
    assert counts[volume_key("[vol a]")] == 1

# --------------------------------------------------------------------------- #
# v198 - Existing volume log reuse for overwrite / re-inventory
# --------------------------------------------------------------------------- #

def test_existing_volume_reinventory_exact_reuses_existing_token_and_writes_mode(tmp_path):
    import inventory_list_lib as IL

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "groups7.log").write_text("SEARCH_PATH: [VOL1] /old/root\nold group text\n", encoding="utf-8")
    for prefix in ["dead", "dups", "comp", "conf", "meta", "tag"]:
        (logs_dir / f"{prefix}7.log").write_text("old text\n", encoding="utf-8")

    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        silent=True,
        volume_action_callback=lambda volume, existing, queued: "re-inventory",
    )
    prepared = IL.apply_existing_volume_actions(config, [("/old/root", "", "VOL1", "volkey")])

    assert prepared == [("/old/root", "", "VOL1", "volkey", "7", "w")]
    for prefix in ["groups", "dead", "dups", "comp", "conf", "meta", "tag"]:
        assert (logs_dir / f"{prefix}7.log").read_text(encoding="utf-8") == ""


def test_existing_volume_reinventory_reuses_existing_token_and_replaces_exact_logs(tmp_path):
    import inventory_list_lib as IL

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "groupsB.log").write_text("SEARCH_PATH: [VOL2] /old/root\nold group text\n", encoding="utf-8")

    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        silent=True,
        volume_action_callback=lambda volume, existing, queued: "re-inventory",
    )
    prepared = IL.apply_existing_volume_actions(config, [("/old/root", "", "VOL2", "volkey")])

    assert prepared == [("/old/root", "", "VOL2", "volkey", "B", "w")]




def test_child_path_reinventory_reuses_parent_token_and_appends_after_prune(tmp_path):
    import inventory_list_lib as IL

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "groupsD.log").write_text("SEARCH_PATH: [VOL1] /mnt/e\nold group text\n", encoding="utf-8")
    (logs_dir / "metaD.log").write_text("old metadata\n", encoding="utf-8")

    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        silent=True,
        volume_action_callback=lambda volume, existing, queued: "re-inventory",
    )
    prepared = IL.apply_existing_volume_actions(config, [("/mnt/e/MP3", "", "VOL1", "volkey")])

    assert prepared == [("/mnt/e/MP3", "", "VOL1", "volkey", "D", "a")]
    assert (logs_dir / "groupsD.log").read_text(encoding="utf-8").startswith("SEARCH_PATH")
    assert config.inventory_path_actions[0]["action"] == "reinventory"
    assert config.inventory_path_actions[0]["related_group_paths"] == ["/mnt/e"]


def test_log_manager_appends_or_overwrites_existing_token_logs(tmp_path):
    config = type("C", (), {"TLOHome": str(tmp_path)})()
    logging_lib.setup_logging(config)
    logs_dir = tmp_path / "logs"
    groups_log = logs_dir / "groupsC.log"
    groups_log.write_text("old group text\n", encoding="utf-8")

    config.logs.start_search_path("/new/root", 1, log_token="C", volume_label="VOL3", log_mode="a")
    appended = groups_log.read_text(encoding="utf-8")
    assert appended.startswith("# groupsLog for search path: [VOL3] /new/root\nSEARCH_PATH: [VOL3] /new/root")
    assert "SEARCH_PATH: [VOL3] /new/root" in appended

    config.logs.start_search_path("/newer/root", 1, log_token="C", volume_label="VOL3", log_mode="w")
    overwritten = groups_log.read_text(encoding="utf-8")
    assert "old group text" not in overwritten
    assert "SEARCH_PATH: [VOL3] /newer/root" in overwritten


# --------------------------------------------------------------------------- #
# v199 - Tag number formatting and unnumbered comma setlist fallback
# --------------------------------------------------------------------------- #

def test_tag_track_numbers_are_zero_padded_by_total_count():
    assert T.format_tag_track_number(1, 1) == "01"
    assert T.format_tag_track_number(9, 99) == "09"
    assert T.format_tag_track_number(99, 99) == "99"
    assert T.format_tag_track_number(1, 100) == "001"
    assert T.format_tag_track_number(99, 100) == "099"
    assert T.format_tag_track_number(100, 100) == "100"


@pytest.mark.parametrize("line,expected_title", [
    ("0 Intro", "Intro"),
    ("00 Intro", "Intro"),
    ("0-Intro", "Intro"),
    ("0) Intro", "Intro"),
    ("0.Intro", "Intro"),
    ("0: Intro", "Intro"),
    ("Track 0 - Intro", "Intro"),
    ("d1t00 Intro", "Intro"),
    ("0[08:23] Intro", "Intro"),
    ("0Intro", "Intro"),
])
def test_setlist_track_number_zero_variants_are_accepted(tmp_path, line, expected_title):
    setlist = tmp_path / "info.txt"
    setlist.write_text(line + "\n", encoding="utf-8")
    tracks = T.parse_setlist_tracks(str(setlist))
    assert len(tracks) == 1
    assert tracks[0]["original_number"] == 0
    assert tracks[0]["normalized_number"] == 1
    assert tracks[0]["title"] == expected_title


def test_tagger_uses_comma_items_when_unnumbered_items_match_audio_count(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio = []
    for idx in range(1, 6):
        path = tmp_path / f"{idx:02d} file{idx}.flac"
        path.write_bytes(b"not real audio; write_audio_tags is patched")
        audio.append(str(path))
    setlist = tmp_path / "info.txt"
    setlist.write_text("Alpha, Beta Song, Gamma Ray, Delta Force, Echo Point\n", encoding="utf-8")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False)
    record = ShowMetadata(group_number=1, main_dir_name="Comma Items", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=5, artist="Artist",
                          date="2001-04-14", venue="Venue", location="City ST",
                          show_name="Artist 2001-04-14 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Comma Items",
             "setlist_file": str(setlist), "music_files": audio}
    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((track_number, title)))
    messages = []
    stats = T.tag_group_with_record(config, group, record, emit=messages.append)

    assert stats["tagged"] == 5
    assert stats["comma_item_folders"] == [str(tmp_path)]
    assert calls == [("01", "Alpha"), ("02", "Beta Song"), ("03", "Gamma Ray"), ("04", "Delta Force"), ("05", "Echo Point")]
    assert any("comma-separated items" in str(message) for message in messages)


def test_tagger_uses_comma_lines_when_long_line_count_matches_audio_count(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio = []
    for idx in range(1, 3):
        path = tmp_path / f"{idx:02d} file{idx}.flac"
        path.write_bytes(b"not real audio; write_audio_tags is patched")
        audio.append(str(path))
    setlist = tmp_path / "info.txt"
    line1 = "Alpha One, Beta Two, Gamma Three, Delta Four, Echo Five"
    line2 = "Red Sun, Blue Moon, Green River, Black Night, White Room"
    setlist.write_text(line1 + "\n" + line2 + "\n", encoding="utf-8")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False)
    record = ShowMetadata(group_number=1, main_dir_name="Comma Lines", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="2001-04-14", venue="Venue", location="City ST",
                          show_name="Artist 2001-04-14 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Comma Lines",
             "setlist_file": str(setlist), "music_files": audio}
    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((track_number, title)))
    messages = []
    stats = T.tag_group_with_record(config, group, record, emit=messages.append)

    assert stats["tagged"] == 2
    assert stats["comma_line_folders"] == [str(tmp_path)]
    assert calls == [("01", line1), ("02", line2)]
    assert any("comma-separated lines" in str(message) for message in messages)


def test_tag_fallback_summary_lists_affected_folders():
    messages = []
    T.emit_tag_fallback_summary({
        "comma_item_folders": ["/music/a"],
        "comma_line_folders": ["/music/b"],
    }, messages.append)
    assert any("comma-separated setlist items" in str(message) and "/music/a" in str(message) for message in messages)
    assert any("comma-separated setlist lines" in str(message) and "/music/b" in str(message) for message in messages)

# --------------------------------------------------------------------------- #
# v200 - Missing bracketed search-path volume prefixes use OS volume label
# --------------------------------------------------------------------------- #

def test_missing_search_path_prefix_uses_os_volume_label(monkeypatch):
    import inventory_list_lib as IL

    monkeypatch.setattr(
        IL,
        "resolve_volume_label",
        lambda path: SimpleNamespace(volume_key="/mnt/e", label="Backup-1", label_source="test"),
    )
    assigned = IL._assign_volume_labels([("/mnt/e/music", "/mnt/e/music", "", "")])
    assert assigned == [("/mnt/e/music", "/mnt/e/music", "", "Backup-1", "/mnt/e")]


def test_explicit_blank_search_path_prefix_is_allowed_when_os_label_blank(monkeypatch):
    import inventory_list_lib as IL

    monkeypatch.setattr(
        IL,
        "resolve_volume_label",
        lambda path: SimpleNamespace(volume_key="/mnt/e", label="", label_source=""),
    )
    assigned = IL._assign_volume_labels([("[]/mnt/e/music", "/mnt/e/music", "", "")])
    assert assigned == [("[]/mnt/e/music", "/mnt/e/music", "", "", "/mnt/e")]


def test_unbracketed_group_log_header_uses_os_volume_label_for_matching(tmp_path, monkeypatch):
    import tlo_bootlist_volume_policy as VP

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "groups0.log").write_text("SEARCH_PATH: /mnt/e/music\n", encoding="utf-8")
    monkeypatch.setattr(VP, "os_volume_label_for_path", lambda path: "Backup-1")

    counts = VP.count_group_logs_by_volume(str(tmp_path))
    assert counts[VP.volume_key("backup-1")] == 1


def test_bracketed_group_log_header_preserves_explicit_blank_volume(tmp_path, monkeypatch):
    import tlo_bootlist_volume_policy as VP

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "groups0.log").write_text("SEARCH_PATH: [] /mnt/e/music\n", encoding="utf-8")
    monkeypatch.setattr(VP, "os_volume_label_for_path", lambda path: "Backup-1")

    counts = VP.count_group_logs_by_volume(str(tmp_path))
    assert counts[VP.volume_key("")] == 1
    assert VP.volume_key("backup-1") not in counts
# --------------------------------------------------------------------------- #
# v201 - Explicit search-path volume labels must match mounted drive label
# --------------------------------------------------------------------------- #

def test_explicit_search_path_volume_matching_os_label_is_allowed(monkeypatch):
    import inventory_list_lib as IL

    monkeypatch.setattr(
        IL,
        "resolve_volume_label",
        lambda path: SimpleNamespace(volume_key="/mnt/e", label="Backup-1", label_source="test"),
    )
    assigned = IL._assign_volume_labels([("[Backup-1]/mnt/e/music", "/mnt/e/music", "", "Backup-1")])
    assert assigned == [("[Backup-1]/mnt/e/music", "/mnt/e/music", "", "Backup-1", "/mnt/e")]


def test_explicit_search_path_volume_mismatch_is_rejected(monkeypatch):
    import inventory_list_lib as IL

    monkeypatch.setattr(
        IL,
        "resolve_volume_label",
        lambda path: SimpleNamespace(volume_key="/mnt/e", label="Backup-1", label_source="test"),
    )
    with pytest.raises(ValueError, match="Search path volume mismatch"):
        IL._assign_volume_labels([("[www]/mnt/e/music", "/mnt/e/music", "", "www")])


def test_explicit_blank_search_path_volume_mismatch_is_rejected_when_os_label_known(monkeypatch):
    import inventory_list_lib as IL

    monkeypatch.setattr(
        IL,
        "resolve_volume_label",
        lambda path: SimpleNamespace(volume_key="/mnt/e", label="Backup-1", label_source="test"),
    )
    with pytest.raises(ValueError, match="Search path volume mismatch"):
        IL._assign_volume_labels([("[]/mnt/e/music", "/mnt/e/music", "", "")])


# --------------------------------------------------------------------------- #
# v301 - Default OS volume names are treated as blank visible volume labels
# --------------------------------------------------------------------------- #

def test_default_os_volume_labels_normalize_to_blank():
    import tlo_bootlist_volume_policy as VP

    assert VP.normalize_volume_label("New Volume") == ""
    assert VP.normalize_volume_label("Local Disk") == ""
    assert VP.normalize_volume_label("[New Volume]") == ""
    assert VP.normalize_volume_label("[Local Disk]") == ""


def test_missing_search_path_prefix_treats_default_os_volume_label_as_blank(monkeypatch):
    import inventory_list_lib as IL

    monkeypatch.setattr(
        IL,
        "resolve_volume_label",
        lambda path: SimpleNamespace(volume_key="/mnt/e", label="New Volume", label_source="test"),
    )
    assigned = IL._assign_volume_labels([("/mnt/e/music", "/mnt/e/music", "", "")])
    assert assigned == [("/mnt/e/music", "/mnt/e/music", "", "", "/mnt/e")]


def test_bootlist_rows_treat_default_volume_names_as_blank(tmp_path):
    import tlo_bootlist_volume_policy as VP

    (tmp_path / "bootlist.csv").write_text(
        "sep=^\nShow^VolumePath\nArtist Show^[Local Disk] /Music/Artist Show\n",
        encoding="utf-8",
    )

    rows = VP.read_bootlist_rows(str(tmp_path))
    assert rows[0]["Volume"] == ""
    assert rows[0]["VolumePath"] == "[] /Music/Artist Show"


# --------------------------------------------------------------------------- #
# v302/v304/v305 - Tagger GUI uses one bold app heading and the current public version
# --------------------------------------------------------------------------- #

def test_v305_tagger_gui_keeps_bold_app_heading_and_uses_current_public_version():
    gui = _load_tlo_ggi_module()
    from tlo_tag_lib import TAGGER_TITLE

    init_source = inspect.getsource(gui.TaggerWindow.__init__)
    build_source = inspect.getsource(gui.TaggerWindow._build)

    assert TAGGER_TITLE == "Traders Little Helper™ Tagger App"
    assert gui.TAGGER_DISPLAY_VERSION == "TLO Tagger GUI v1.2 Build 335"
    assert "self.window.title(TAGGER_DISPLAY_VERSION)" in init_source
    assert build_source.count("text=TAGGER_TITLE") == 1
    assert "text=TAGGER_TITLE, font=title_font" in build_source
    assert ').grid(row=1, column=0, columnspan=3' in build_source


# --------------------------------------------------------------------------- #
# v203 - Placeholder setlists requesting generated music-file setlists
# --------------------------------------------------------------------------- #

def test_folder_never_contained_info_file_setlist_generates_from_music_files(tmp_path):
    music_dir = tmp_path / "show"
    music_dir.mkdir()
    (music_dir / "01 Intro.flac").write_text("", encoding="utf-8")
    (music_dir / "02 Song.flac").write_text("", encoding="utf-8")
    source = music_dir / "info.txt"
    source.write_text('Folder never contained an info file\n', encoding="utf-8")

    record = {
        "artist": "Artist",
        "date": "2001-04-14",
        "venue": "Venue",
        "location": "City ST",
        "main_dir_path": str(music_dir),
        "music_dirs_json": __import__("json").dumps([str(music_dir)]),
    }
    text = PP._export_setlist_text(str(source), record)
    assert "Folder never contained an info file" not in text
    lines = text.splitlines()
    assert lines[:5] == ["Artist", "2001-04-14", "Venue", "City ST", ""]
    assert "TRACKS:" in lines
    assert "01. Intro" in text
    assert "02. Song" in text


def test_tagger_keeps_folder_never_contained_marker_when_other_content_exists(tmp_path):
    source = tmp_path / "info.txt"
    source.write_text('Folder never contained an info file\n01 Wrong Title\n', encoding="utf-8")
    tracks = T.parse_setlist_tracks(str(source))
    assert [track["title"] for track in tracks] == ["Wrong Title"]
    assert T.parse_unnumbered_comma_tracks(str(source), 1) == ([], "")

# --------------------------------------------------------------------------- #
# v204 - Postprocess timing/status instrumentation
# --------------------------------------------------------------------------- #

def test_postprocess_writes_timing_section_to_summary_log(tmp_path):
    home = str(tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "meta0.log").write_text(
        "SHOW_NAME: Timed Show\n"
        "SHOW_IN_CONFLICT: no\n"
        "MAIN_DIR_PATH: /timed/path\n"
        "SETLIST_FILE: \n"
        "VOLUME_LABEL: VOL1\n"
        "ARTIST: Timed Artist\n"
        "DATE: 2001-04-14\n"
        "VENUE: Timed Venue\n"
        "LOCATION: Timed City ST\n"
        "PARENTHETICALS: \n"
        "ALBUM_NAME: \n"
        "END_SHOW_METADATA\n",
        encoding="utf-8",
    )
    config = SimpleNamespace(TLOHome=home, inventory_volume_actions={}, silent=True)

    result = PP.postprocess_metadata_outputs(config)
    text = open(result["summary_log"], encoding="utf-8").read()

    assert "Postprocess timing:" in text
    assert "read metadata logs:" in text
    assert "export setlists and build bootlist rows:" in text
    assert "write summary.log:" in text
    assert "total postprocess:" in text


def test_postprocess_prints_stage_status_lines(tmp_path, capsys):
    home = str(tmp_path)
    (tmp_path / "logs").mkdir()
    config = SimpleNamespace(TLOHome=home, inventory_volume_actions={}, silent=False)

    PP.postprocess_metadata_outputs(config)
    out = capsys.readouterr().out

    assert "POSTPROCESS: reading metadata logs..." in out
    assert "POSTPROCESS: exporting setlists and building bootlist rows..." in out
    assert "POSTPROCESS: writing summary.log complete" in out
    assert "POSTPROCESS: total complete" in out

# --------------------------------------------------------------------------- #
# v205 - eTreeDB song-title fallback for tagging
# --------------------------------------------------------------------------- #

def test_etreedb_setlist_normalization_splits_commas_and_removes_encore():
    import tlo_etree_lookup as E

    assert E.normalize_setlists_for_output(["Alpha, Encore, Beta &gt Gamma"]) == [
        "01 Alpha\n02 Beta > Gamma"
    ]


def test_tagger_uses_etreedb_titles_when_no_setlist(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 Unknown.flac"
    audio2 = tmp_path / "02 Unknown.flac"
    audio1.write_bytes(b"not real audio; write_audio_tags is patched")
    audio2.write_bytes(b"not real audio; write_audio_tags is patched")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, etree_lookup=True)
    record = ShowMetadata(group_number=1, main_dir_name="Etree", main_dir_path=str(tmp_path),
                          setlist_file="", music_file_count=2, artist="Bob Dylan",
                          date="1975-11-13", venue="Venue", location="City ST",
                          show_name="Bob Dylan 1975-11-13 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Etree",
             "setlist_file": "", "music_files": [str(audio1), str(audio2)]}

    monkeypatch.setattr(T, "lookup_setlists_by_performance", lambda artist, date_yyyy_mm_dd, debug=False: [(SimpleNamespace(performance_id=101), ["1 Etree First\n2 Etree Second"])])
    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((os.path.basename(path), track_number, title)))
    messages = []
    stats = T.tag_group_with_record(config, group, record, emit=messages.append)

    assert stats["tagged"] == 2
    assert stats["etreedb_folders"] == [str(tmp_path)]
    assert calls == [("01 Unknown.flac", "01", "Etree First"), ("02 Unknown.flac", "02", "Etree Second")]
    assert any("using eTreeDB setlist titles" in str(message) for message in messages)


def test_tagger_uses_etreedb_titles_when_setlist_has_no_titles(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "d1t01 Alpha.flac"
    audio2 = tmp_path / "d1t02 Beta.flac"
    setlist = tmp_path / "info.txt"
    audio1.write_bytes(b"not real audio; write_audio_tags is patched")
    audio2.write_bytes(b"not real audio; write_audio_tags is patched")
    setlist.write_text("Venue: Somewhere\nDate: 1975-11-13\n", encoding="utf-8")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, etree_lookup=True)
    record = ShowMetadata(group_number=1, main_dir_name="Etree", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Bob Dylan",
                          date="1975-11-13", venue="Venue", location="City ST",
                          show_name="Bob Dylan 1975-11-13 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Etree",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}

    monkeypatch.setattr(T, "lookup_setlists_by_performance", lambda artist, date_yyyy_mm_dd, debug=False: [(SimpleNamespace(performance_id=102), ["01 Etree One\n02 Etree Two"])])
    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((track_number, title)))
    stats = T.tag_group_with_record(config, group, record, emit=lambda _text: None)

    assert stats["tagged"] == 2
    assert stats["etreedb_folders"] == [str(tmp_path)]
    assert calls == [("01", "Etree One"), ("02", "Etree Two")]

# --------------------------------------------------------------------------- #
# v208 - In-memory postprocess records and skip/re-inventory-only decisions
# --------------------------------------------------------------------------- #

def test_postprocess_prefers_in_memory_metadata_records_over_reused_log_token(tmp_path):
    from tlo_bootlist_volume_policy import read_bootlist_rows
    home = str(tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    _write_minimal_meta(logs_dir, "PARENT", "Old Parent Show", "/mnt/e/Other")
    config = SimpleNamespace(
        TLOHome=home,
        inventory_volume_actions={},
        inventory_path_actions=[{"volume": "VOL1", "volume_key": "vol1", "path": "/mnt/e/MP3", "action": "reinventory"}],
        current_run_log_tokens=["PARENT"],
        current_metadata_records=[{
            "show_name": "New Child Show",
            "setlist_file": "",
            "volume_label": "VOL1",
            "artist": "New Artist",
            "date": "2001-04-14",
            "venue": "New Venue",
            "location": "New City ST",
            "parentheticals": "",
            "album_name": "",
            "show_in_conflict": "no",
            "main_dir_path": "/mnt/e/MP3/New",
            "setlist_files_json": "",
            "music_dirs_json": "",
        }],
        silent=True,
    )
    PP.postprocess_metadata_outputs(config)
    rows = read_bootlist_rows(home)
    assert [(row["Show"], row["Path"]) for row in rows] == [("New Child Show", "/MP3/New")]




def test_postprocess_accepts_showmetadata_in_memory_records(tmp_path):
    from tlo_bootlist_volume_policy import read_bootlist_rows
    from tlo_models import ShowMetadata

    home = str(tmp_path)
    main_dir = tmp_path / "Artist 2001-04-14 Venue City ST"
    main_dir.mkdir()
    (tmp_path / "logs").mkdir()

    record = ShowMetadata(
        group_number=1,
        main_dir_name=main_dir.name,
        main_dir_path=str(main_dir),
        setlist_file="",
        music_file_count=0,
        volume_label="Back-up-1",
        artist="Artist",
        date="2001-04-14",
        venue="Venue",
        location="City ST",
        show_name="Artist 2001-04-14 Venue City ST",
    )
    config = SimpleNamespace(
        TLOHome=home,
        inventory_volume_actions={},
        inventory_path_actions=[],
        current_run_log_tokens=[],
        current_metadata_records=[record],
        silent=True,
    )

    PP.postprocess_metadata_outputs(config)
    rows = read_bootlist_rows(home)
    assert len(rows) == 1
    assert rows[0]["Show"] == "Artist 2001-04-14 Venue City ST"
    assert rows[0]["Volume"] == "Back-up-1"

def test_normalize_volume_action_user_choices_are_skip_or_reinventory():
    from tlo_bootlist_volume_policy import normalize_volume_action
    assert normalize_volume_action("skip") == "skip"
    assert normalize_volume_action("s") == "skip"
    assert normalize_volume_action("re-inventory") == "reinventory"
    assert normalize_volume_action("r") == "reinventory"
    # Legacy spellings remain accepted as re-inventory aliases, but are not shown in prompts.
    assert normalize_volume_action("overwrite") == "reinventory"
    assert normalize_volume_action("append") == "reinventory"

# --------------------------------------------------------------------------- #
# v211 - Parallel postprocess setlist/bootlist piece generation
# --------------------------------------------------------------------------- #

def test_postprocess_worker_count_not_capped_by_single_search_path():
    config = SimpleNamespace(performance_mode="fast", max_workers=0)
    assert PP._postprocess_worker_count(config, 5) >= 2 or (os.cpu_count() or 1) == 1


def test_parallel_postprocess_keeps_same_setlist_base_conflicts_serial(tmp_path, monkeypatch):
    home = str(tmp_path)
    (tmp_path / "logs").mkdir()
    source1 = tmp_path / "info1.txt"
    source2 = tmp_path / "info2.txt"
    source1.write_text("01 First\n", encoding="utf-8")
    source2.write_text("01 First\n02 Alternate\n", encoding="utf-8")

    records = [
        {
            "show_name": "Artist 2001-04-14 Venue City ST",
            "setlist_file": str(source1),
            "volume_label": "VOL1",
            "artist": "Artist",
            "date": "2001-04-14",
            "venue": "Venue",
            "location": "City ST",
            "parentheticals": "",
            "album_name": "",
            "show_in_conflict": "no",
            "main_dir_path": "/mnt/e/A",
            "setlist_files_json": "",
            "music_dirs_json": "",
        },
        {
            "show_name": "Artist 2001-04-14 Venue City ST",
            "setlist_file": str(source2),
            "volume_label": "VOL1",
            "artist": "Artist",
            "date": "2001-04-14",
            "venue": "Venue",
            "location": "City ST",
            "parentheticals": "",
            "album_name": "",
            "show_in_conflict": "no",
            "main_dir_path": "/mnt/e/B",
            "setlist_files_json": "",
            "music_dirs_json": "",
        },
    ]
    config = SimpleNamespace(
        TLOHome=home,
        inventory_volume_actions={},
        inventory_path_actions=[],
        current_run_log_tokens=[],
        current_metadata_records=records,
        silent=True,
        performance_mode="fast",
        max_workers=2,
    )
    monkeypatch.setattr(PP, "_postprocess_worker_count", lambda _config, _count: 2)

    PP.postprocess_metadata_outputs(config)

    setlist_names = sorted(name for name in os.listdir(tmp_path / "setlists") if name.endswith(".txt"))
    assert setlist_names == [
        "Artist2001-04-14VenueCityST(alt1).txt",
        "Artist2001-04-14VenueCityST.txt",
    ]

# --------------------------------------------------------------------------- #
# v212 - Compliant strict date-first parsing and compliant artist mode
# --------------------------------------------------------------------------- #

def test_compliant_primary_date_prefers_ymd_before_earlier_range():
    matches = P._compliant_string_date_matches(
        "Collection 1960-1962 Band 2001-04-14 Venue",
        allow_string2=False,
    )
    assert matches
    assert matches[0]["date_raw"] == "2001-04-14"
    assert matches[0]["date_norm"] == "2001-04-14"


def test_compliant_primary_date_accepts_year_range_when_no_ymd():
    matches = P._compliant_string_date_matches("Band 1996-1998 Archive", allow_string2=False)
    assert matches
    assert matches[0]["date_norm"] == "1996-1998"


def test_compliant_artist_mode_as_is_skips_master_lookup():
    matcher = P.ArtistMatcher(db_path="")
    matcher.exact_map = {"airplanes": {"Jefferson Airplane"}}
    matcher.master_aliases = {"Jefferson Airplane": ["Jefferson Airplane", "Airplanes"]}
    matcher.master_norms = {"Jefferson Airplane": {"jeffersonairplane", "airplanes"}}
    group = {
        "group_number": 1,
        "main_dir_name": "The Airplanes 2001-04-14 Fillmore",
        "main_dir_path": "/music/The Airplanes 2001-04-14 Fillmore",
        "music_file_count": 1,
        "music_files": [],
        "music_dirs": [],
        "setlist_file": "",
        "setlist_files": [],
    }
    as_is_config = SimpleNamespace(compliant=True, compliant_artist_mode="as-is", current_volume_label="", etree_lookup=False, setlistfm_lookup=False)
    master_config = SimpleNamespace(compliant=True, compliant_artist_mode="master", current_volume_label="", etree_lookup=False, setlistfm_lookup=False)

    as_is_record, _dates, _unresolved = P._extract_metadata_for_group_compliant(as_is_config, group, matcher)
    master_record, _dates, _unresolved = P._extract_metadata_for_group_compliant(master_config, group, matcher)

    assert as_is_record.artist == "The Airplanes"
    assert master_record.artist == "Jefferson Airplane"


# --------------------------------------------------------------------------- #
# v213 - GUI startup remains responsive while roots are prepared
# --------------------------------------------------------------------------- #

def _load_tlo_ggi_module():
    module_path = Path(__file__).with_name("tlo-ggi.py")
    spec = importlib.util.spec_from_file_location("tlo_ggi_for_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_gui_start_defers_inventory_root_preparation_to_worker():
    gui = _load_tlo_ggi_module()
    start_source = inspect.getsource(gui.App._start)
    assert "prepare_inventory_items" not in start_source
    assert "_ask_existing_volume_action_threadsafe" in start_source
    assert start_source.index("self.full_inventory_active = True") < start_source.index("threading.Thread")


def test_gui_thread_marshal_runs_directly_on_main_thread():
    gui = _load_tlo_ggi_module()
    app = SimpleNamespace()
    assert gui.App._run_on_gui_thread(app, lambda value: value + 1, 41) == 42


# --------------------------------------------------------------------------- #
# v215 - Phase 1 representative media paths
# --------------------------------------------------------------------------- #

def test_phase1_logs_one_representative_media_path_not_every_media_or_setlist_file(tmp_path):
    from initial_dir_walk_lib import initial_dir_walk

    home = tmp_path / "home"
    show_dir = tmp_path / "music" / "Artist 2001-04-14 Venue City ST"
    show_dir.mkdir(parents=True)
    for name in ("01 opener.mp3", "02 middle.mp3", "03 closer.mp3"):
        (show_dir / name).write_bytes(b"audio")
    setlist = show_dir / "info.txt"
    setlist.write_text("Artist\n2001-04-14\n", encoding="utf-8")

    config = SimpleNamespace(TLOHome=str(home), performance_mode="balanced", silent=True)
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(tmp_path / "music"), 1, log_token="Z")

    initial_dir_walk(config, str(tmp_path / "music"))

    raw_lines = Path(config.logs.paths.complete_paths).read_text(encoding="utf-8").splitlines()
    payload_lines = [line for line in raw_lines if line and ": " not in line]
    assert payload_lines == [os.path.normpath(str(show_dir / "01 opener.mp3"))]
    assert not any(line.endswith("02 middle.mp3") for line in raw_lines)
    assert not any(line.endswith("03 closer.mp3") for line in raw_lines)
    assert not any(line.endswith("info.txt") for line in raw_lines)

    groups = P._build_groups_from_search_path(config, str(tmp_path / "music"))
    assert len(groups) == 1
    assert groups[0]["music_file_count"] == 3
    assert groups[0]["music_media_extensions"] == [".mp3"]
    assert groups[0]["music_files"] == [os.path.normpath(str(show_dir / "01 opener.mp3"))]
    assert groups[0]["setlist_file"] == os.path.normpath(str(setlist))

def test_phase1_sample_only_log_allows_safe_parent_setlist_lookup(tmp_path):
    from initial_dir_walk_lib import initial_dir_walk

    home = tmp_path / "home"
    release_dir = tmp_path / "music" / "Artist 2001-04-14 Venue City ST"
    disc_dir = release_dir / "CD1"
    disc_dir.mkdir(parents=True)
    (disc_dir / "01 opener.flac").write_bytes(b"audio")
    parent_setlist = release_dir / "info.txt"
    parent_setlist.write_text("Artist\n2001-04-14\nVenue City ST\n", encoding="utf-8")

    config = SimpleNamespace(TLOHome=str(home), performance_mode="balanced", silent=True)
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(tmp_path / "music"), 1, log_token="Y")

    initial_dir_walk(config, str(tmp_path / "music"))
    raw_lines = Path(config.logs.paths.complete_paths).read_text(encoding="utf-8").splitlines()
    payload_lines = [line for line in raw_lines if line and ": " not in line]
    assert payload_lines == [os.path.normpath(str(disc_dir / "01 opener.flac"))]
    assert not any(line.endswith("info.txt") for line in raw_lines)

    groups = P._build_groups_from_search_path(config, str(tmp_path / "music"))
    assert len(groups) == 1
    assert groups[0]["setlist_file"] == os.path.normpath(str(parent_setlist))

# --------------------------------------------------------------------------- #
# v216 - Input option registry and checkbox handling
# --------------------------------------------------------------------------- #

def test_cli_and_gui_defaults_share_registry(monkeypatch, tmp_path):
    gui = _load_tlo_ggi_module()
    home = tmp_path / "home"
    home.mkdir()

    monkeypatch.setattr(sys, "argv", ["tlo-gi.py", "--TLOHome", str(home)])
    cli_values = IPL.parse_command_line()
    gui_args = gui._parse_gui_command_line(["--TLOHome", str(home)])

    assert cli_values["performance_mode"] == "balanced"
    assert gui_args.performance_mode == "balanced"
    assert "max_workers" not in vars(gui_args)  # argparse.SUPPRESS replaces argv string-scanning
    assert cli_values.get("max_workers", 0) == 0


def test_cli_uses_canonical_snake_case_dests(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(sys, "argv", [
        "tlo-gi.py",
        "--TLOHome", str(home),
        "--search-path", str(tmp_path),
        "--tag-during-inventory",
        "--etree-lookup",
        "--setlistfm-lookup",
        "--performance-mode", "fast",
        "--max-workers", "3",
        "--current-storage-volume", "Backup01",
    ])
    values = IPL.parse_command_line()

    assert values["search_path_override"] == str(tmp_path)
    assert values["tag_during_inventory"] is True
    assert values["etree_lookup"] is True
    assert values["setlistfm_lookup"] is True
    assert values["performance_mode"] == "fast"
    assert values["max_workers"] == 3
    assert values["current_storage_volume"] == "Backup01"
    assert "tagDuringInventory" not in values
    assert "etreeLookup" not in values
    assert "setlistFM" not in values


def test_lookup_dependency_strict_cli_and_auto_gui_modes():
    strict_values = {"setlistfm_lookup": True, "etree_lookup": False}
    with pytest.raises(ValueError, match="requires --etree-lookup"):
        apply_lookup_dependency(strict_values, mode="strict")

    auto_values = {"setlistfm_lookup": True, "etree_lookup": False}
    changed = apply_lookup_dependency(auto_values, mode="auto")
    assert changed is True
    assert auto_values == {"setlistfm_lookup": True, "etree_lookup": True}


def test_inventory_cli_rejects_setlistfm_without_etree(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(sys, "argv", ["tlo-gi.py", "--TLOHome", str(home), "--setlistfm-lookup"])
    with pytest.raises(SystemExit):
        IPL.parse_command_line()


def test_tlohome_mytlo_env_precedence_is_preserved(monkeypatch, tmp_path):
    env_home = tmp_path / "env_home"
    tlo_home = tmp_path / "tlo_home"
    my_tlo = tmp_path / "my_tlo"
    for path in (env_home, tlo_home, my_tlo):
        path.mkdir()

    monkeypatch.setenv("TLOHome", str(env_home))
    assert T.resolve_tlo_home(tlo_home=str(tlo_home), my_tlo=str(my_tlo)) == os.path.normpath(str(my_tlo))
    assert T.resolve_tlo_home(tlo_home=str(tlo_home), my_tlo="") == os.path.normpath(str(tlo_home))
    assert T.resolve_tlo_home(tlo_home="", my_tlo="") == os.path.normpath(str(env_home))

    monkeypatch.delenv("TLOHome", raising=False)
    with pytest.raises(T.TaggerError, match="TLOHome must be supplied"):
        T.resolve_tlo_home(tlo_home="", my_tlo="")


def test_tagger_parser_uses_registry_canonical_dest():
    module_path = Path(__file__).with_name("tlo-tag.py")
    spec = importlib.util.spec_from_file_location("tlo_tag_for_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    args = module._parse_args(["--compliant", "--etree-lookup"])
    assert args.compliant is True
    assert args.etree_lookup is True
    assert not hasattr(args, "etreeLookup")




# --------------------------------------------------------------------------- #
# v218 - Kebab-case command-line flags replace camelCase user-facing flags
# --------------------------------------------------------------------------- #

def test_v218_option_registry_uses_kebab_case_flags_only():
    from tlo_options import OPTIONS_BY_FIELD
    expected = {
        "search_path_override": "--search-path",
        "tag_during_inventory": "--tag-during-inventory",
        "etree_lookup": "--etree-lookup",
        "setlistfm_lookup": "--setlistfm-lookup",
        "performance_mode": "--performance-mode",
        "max_workers": "--max-workers",
        "current_storage_volume": "--current-storage-volume",
        "compliant_artist_mode": "--compliant-artist-mode",
    }
    for field, flag in expected.items():
        assert OPTIONS_BY_FIELD[field].flag == flag


def test_v218_legacy_camel_case_inventory_flags_are_rejected(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    legacy_flags = [
        "--searchPath",
        "--tagDuringInventory",
        "--etreeLookup",
        "--setlistFM",
        "--performanceMode",
        "--maxWorkers",
        "--currentStorageVolume",
        "--compliantArtistMode",
    ]
    for flag in legacy_flags:
        argv = ["tlo-gi.py", "--TLOHome", str(home), flag]
        if flag not in {"--tagDuringInventory", "--etreeLookup", "--setlistFM"}:
            argv.append("value")
        monkeypatch.setattr(sys, "argv", argv)
        with pytest.raises(SystemExit):
            IPL.parse_command_line()


def test_v218_tagger_uses_tag_path_and_rejects_legacy_tagPath():
    module_path = Path(__file__).with_name("tlo-tag.py")
    spec = importlib.util.spec_from_file_location("tlo_tag_for_v218_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    args = module._parse_args(["--tag-path", "/tmp/tags"])
    assert args.tagPath == "/tmp/tags"
    with pytest.raises(SystemExit):
        module._parse_args(["--tagPath", "/tmp/tags"])

# --------------------------------------------------------------------------- #
# v217 - Bounded postprocess thread pool for large filename-group counts
# --------------------------------------------------------------------------- #

def test_postprocess_extreme_respects_explicit_max_workers_for_large_runs(monkeypatch):
    monkeypatch.setattr(PP.os, "cpu_count", lambda: 1)
    config = SimpleNamespace(performance_mode="extreme", max_workers=9)
    assert PP._postprocess_worker_count(config, 23977) == 9


def test_postprocess_extreme_without_max_workers_uses_safe_thread_cap(monkeypatch):
    monkeypatch.setattr(PP.os, "cpu_count", lambda: 16)
    config = SimpleNamespace(performance_mode="extreme", max_workers=0)
    assert PP._postprocess_worker_count(config, 23977) == PP.POSTPROCESS_EXTREME_THREAD_CAP
    assert PP._postprocess_worker_count(config, 23977) < 23977


def test_postprocess_worker_count_accepts_legacy_max_workers_attr(monkeypatch):
    monkeypatch.setattr(PP.os, "cpu_count", lambda: 1)
    config = SimpleNamespace(performance_mode="extreme", maxWorkers=7)
    assert PP._postprocess_worker_count(config, 23977) == 7

# --------------------------------------------------------------------------- #
# v221 - GUI Search Path drag/drop native Windows only; no WSL/Linux attempts
# --------------------------------------------------------------------------- #

class _FakeTk:
    def splitlist(self, value):
        if value == "{C:/Music Folder} {D:/Other}":
            return ("C:/Music Folder", "D:/Other")
        return tuple(str(value).split())

class _FakeWidget:
    def __init__(self):
        self.tk = _FakeTk()


def test_v221_dragdrop_disabled_on_non_windows_without_registration(monkeypatch):
    import tlo_dragdrop as DD

    monkeypatch.setattr(DD, "is_windows_platform", lambda: False)

    class DndCapableWidget(_FakeWidget):
        def drop_target_register(self, *_args):
            raise AssertionError("non-Windows should not try to register a drop target")
        def dnd_bind(self, *_args):
            raise AssertionError("non-Windows should not bind a drop target")

    class Var:
        def set(self, _value):
            raise AssertionError("non-Windows should not install a drop handler")

    status = DD.enable_search_path_folder_drop(DndCapableWidget(), Var())
    assert status.enabled is False
    assert "native Windows" in status.reason


def test_v221_dragdrop_splits_tkdnd_folder_list(monkeypatch):
    import tlo_dragdrop as DD

    monkeypatch.setattr(DD, "is_windows_platform", lambda: True)
    paths = DD.split_dropped_paths(_FakeWidget(), "{C:/Music Folder} {D:/Other}")
    assert paths[0].endswith(r"C:\Music Folder")
    assert paths[1].endswith(r"D:\Other")


def test_v221_dragdrop_normalizes_windows_file_uris(monkeypatch):
    import tlo_dragdrop as DD

    monkeypatch.setattr(DD, "is_windows_platform", lambda: True)
    assert DD.normalize_dropped_path("file:///C:/Music/Artist%20Shows").endswith(r"C:\Music\Artist Shows")


def test_v221_dragdrop_can_register_on_native_windows_with_tkinterdnd2_methods(monkeypatch):
    import tlo_dragdrop as DD

    monkeypatch.setattr(DD, "is_windows_platform", lambda: True)

    class DndCapableWidget(_FakeWidget):
        def __init__(self):
            super().__init__()
            self.registered = []
            self.bound = []
        def drop_target_register(self, *args):
            self.registered.append(args)
        def dnd_bind(self, *args):
            self.bound.append(args)

    class Var:
        def set(self, _value):
            pass

    widget = DndCapableWidget()
    status = DD.enable_search_path_folder_drop(widget, Var())
    assert status.enabled is True
    assert status.provider == "tkinterdnd2"
    assert widget.registered
    assert widget.bound


def test_v221_gui_uses_dragdrop_root_factory():
    gui = _load_tlo_ggi_module()
    main_source = inspect.getsource(gui.main)
    assert "create_tk_root(tk)" in main_source
    build_source = inspect.getsource(gui.App._build)
    assert "_enable_search_path_drag_drop" in build_source
    assert "search_path_drop_status.reason" not in build_source


def test_v330_tagging_path_dragdrop_disabled_on_non_windows(monkeypatch):
    import tlo_dragdrop as DD

    monkeypatch.setattr(DD, "is_windows_platform", lambda: False)

    class DndCapableWidget(_FakeWidget):
        def drop_target_register(self, *_args):
            raise AssertionError("non-Windows should not try to register a tag drop target")
        def dnd_bind(self, *_args):
            raise AssertionError("non-Windows should not bind a tag drop target")

    class Var:
        def set(self, _value):
            raise AssertionError("non-Windows should not install a tag drop handler")

    status = DD.enable_tagging_path_folder_drop(DndCapableWidget(), Var())
    assert status.enabled is False
    assert "native Windows" in status.reason


def test_v330_tagging_path_dragdrop_registers_on_native_windows(monkeypatch):
    import tlo_dragdrop as DD

    monkeypatch.setattr(DD, "is_windows_platform", lambda: True)

    class DndCapableWidget(_FakeWidget):
        def __init__(self):
            super().__init__()
            self.registered = []
            self.bound = []
        def drop_target_register(self, *args):
            self.registered.append(args)
        def dnd_bind(self, *args):
            self.bound.append(args)

    class Var:
        def set(self, _value):
            pass

    widget = DndCapableWidget()
    status = DD.enable_tagging_path_folder_drop(widget, Var())
    assert status.enabled is True
    assert status.provider == "tkinterdnd2"
    assert widget.registered
    assert widget.bound


def test_v330_tagger_window_build_registers_tagging_path_dragdrop():
    gui = _load_tlo_ggi_module()
    build_source = inspect.getsource(gui.TaggerWindow._build)
    helper_source = inspect.getsource(gui.TaggerWindow._enable_tagging_path_drag_drop)
    assert "self.path_entry = ttk.Entry" in build_source
    assert "self._enable_tagging_path_drag_drop()" in build_source
    assert "enable_tagging_path_folder_drop" in helper_source
    assert "Tagging Path:" in build_source


# --------------------------------------------------------------------------- #
# v222 - Existing log/bootlist path checks ignore drive letter / WSL mount root
# --------------------------------------------------------------------------- #

def test_v222_path_compare_ignores_windows_drive_and_wsl_mount_root():
    from tlo_bootlist_volume_policy import normalize_path_for_compare, paths_related, path_is_same_or_under

    assert normalize_path_for_compare("E:/boots/Artist") == normalize_path_for_compare("F:/boots/Artist")
    assert normalize_path_for_compare(r"E:\boots\Artist") == normalize_path_for_compare("/mnt/n/boots/Artist")
    assert paths_related("/mnt/e/boots", "/mnt/n/boots/Artist") is True
    assert path_is_same_or_under("F:/boots/Artist", "E:/boots") is True
    assert path_is_same_or_under("/mnt/n/boots/Artist", "/mnt/e/boots") is True


def test_v222_existing_group_log_collision_matches_after_mount_letter_changes(tmp_path):
    import inventory_list_lib as IL

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    (logs_dir / "groupsQ.log").write_text("SEARCH_PATH: [VOL1] /mnt/e/boots\nold group text\n", encoding="utf-8")

    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        silent=True,
        volume_action_callback=lambda volume, path, existing, queued: "re-inventory",
    )
    prepared = IL.apply_existing_volume_actions(config, [("/mnt/n/boots", "", "VOL1", "volkey")])

    assert prepared == [("/mnt/n/boots", "", "VOL1", "volkey", "Q", "w")]
    assert config.inventory_path_actions[0]["related_group_paths"] == ["/mnt/e/boots"]


def test_v222_postprocess_replaces_bootlist_rows_after_mount_letter_changes(tmp_path):
    from tlo_bootlist_volume_policy import read_bootlist_rows, write_bootlist_rows

    home = str(tmp_path)
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    write_bootlist_rows(home, [
        {"Show": "Old Same Subtree", "VolumePath": "[VOL1] /mnt/e/boots/Artist"},
        {"Show": "Old Other", "VolumePath": "[VOL1] /mnt/e/other/Artist"},
    ])
    _write_minimal_meta(logs_dir, "N", "New Same Subtree", "/mnt/n/boots/New Artist", volume="VOL1")
    config = SimpleNamespace(
        TLOHome=home,
        inventory_volume_actions={"vol1": "reinventory"},
        inventory_path_actions=[{"volume": "VOL1", "volume_key": "vol1", "path": "/mnt/n/boots", "action": "reinventory"}],
        current_run_log_tokens=["N"],
        silent=True,
    )

    PP.postprocess_metadata_outputs(config)

    rows = read_bootlist_rows(home)
    values = [(r["Show"], r["VolumePath"]) for r in rows]
    assert ("Old Same Subtree", "[VOL1] /mnt/e/boots/Artist") not in values
    assert ("Old Other", "[VOL1] /other/Artist") in values
    assert ("New Same Subtree", "[VOL1] /boots/New Artist") in values


# --------------------------------------------------------------------------- #
# v227 - Tagger accepts Windows drive-rooted tag paths under WSL/Linux
# --------------------------------------------------------------------------- #

def test_v227_windows_drive_tag_path_translates_to_wsl_mount(monkeypatch):
    from tlo_path_inputs import normalize_platform_input_path, windows_drive_path_to_wsl_path

    assert windows_drive_path_to_wsl_path(r"P:\tagtest") == "/mnt/p/tagtest"
    assert windows_drive_path_to_wsl_path("P:/tagtest/Grandmothers") == "/mnt/p/tagtest/Grandmothers"
    assert windows_drive_path_to_wsl_path("file:///P:/tagtest/Grandmothers%20Shows") == "/mnt/p/tagtest/Grandmothers Shows"
    monkeypatch.setattr("tlo_path_inputs.os.name", "posix", raising=False)
    assert normalize_platform_input_path(r"P:\tagtest") == "/mnt/p/tagtest"


def test_v227_tagger_resolve_tagging_path_accepts_windows_drive_path(monkeypatch, tmp_path):
    home = tmp_path / "tlohome"
    home.mkdir()
    monkeypatch.setattr("tlo_path_inputs.os.name", "posix", raising=False)
    real_exists = T.os.path.exists
    real_isdir = T.os.path.isdir
    monkeypatch.setattr(T.os.path, "exists", lambda path: path == "/mnt/p/tagtest" or real_exists(path))
    monkeypatch.setattr(T.os.path, "isdir", lambda path: path == "/mnt/p/tagtest" or real_isdir(path))
    assert T.resolve_tagging_path(str(home), r"P:\tagtest") == "/mnt/p/tagtest"
    assert T.default_tagging_path(tlo_home=str(home), tag_path=r"P:\tagtest") == "/mnt/p/tagtest"


# --------------------------------------------------------------------------- #
# v228 - GUI tagger Quit cancels tag run and closes only tagger window
# --------------------------------------------------------------------------- #

def test_v228_tagger_window_quit_button_stays_enabled_and_requests_cancel():
    gui = _load_tlo_ggi_module()
    build_source = inspect.getsource(gui.TaggerWindow._build)
    controls_source = inspect.getsource(gui.TaggerWindow._set_processing_controls)
    exit_source = inspect.getsource(gui.TaggerWindow._request_exit)
    destroy_source = inspect.getsource(gui.TaggerWindow._destroy_tagger_window)

    assert 'text="Quit"' in build_source
    assert 'tag_button.configure(state=tag_state)' in controls_source
    assert 'exit_button.configure(state="normal")' in controls_source
    assert 'request_cancel()' in exit_source
    assert 'self._destroy_tagger_window()' in exit_source
    assert 'self.parent_app.active_tagger_window = None' in destroy_source
    assert 'root.quit' not in exit_source
    assert 'parent_app.root.quit' not in exit_source


def test_v228_tagger_write_loop_checks_cancel_before_each_file():
    source = inspect.getsource(T.tag_group_with_record)
    marker = 'for audio_path, track in zip(audio_files, tracks):'
    assert marker in source
    tail = source[source.index(marker):]
    assert 'if is_cancel_requested():' in tail
    assert 'CANCELLED:' in tail and 'stopping before' in tail

# --------------------------------------------------------------------------- #
# v229 - Standalone/GUI tagger logs output and debug copies list music files
# --------------------------------------------------------------------------- #

def test_v229_run_tagger_mirrors_output_to_tag_log(tmp_path, monkeypatch):
    messages = []

    monkeypatch.setattr(T, "validate_required_databases", lambda config: None)
    monkeypatch.setattr(T, "load_artist_matcher", lambda config: object())
    monkeypatch.setattr(T, "_groups_from_inventory_discovery", lambda config, tagging_path: [{"main_dir_path": str(tmp_path / "show")}])

    def fake_process(config, group, artist_matcher, emit=None):
        T._emit(emit, "ERROR: fake folder | file.flac | simulated anomaly")
        return {"groups": 1, "tagged": 0, "skipped": 0, "errors": 1,
                "comma_item_folders": [], "comma_line_folders": [], "etreedb_folders": [], "title_tag_folders": []}

    monkeypatch.setattr(T, "process_tagging_group", fake_process)
    totals = T.run_tagger(tlo_home=str(tmp_path), tag_path=str(tmp_path), emit=messages.append)

    assert totals["errors"] == 1
    assert any("ERROR: fake folder | file.flac | simulated anomaly" in str(message) for message in messages)
    tag_success_log = tmp_path / "logs" / "tagsT.txt"
    tag_error_log = tmp_path / "logs" / "tageT.txt"
    assert tag_success_log.exists()
    assert tag_error_log.exists()
    success_text = tag_success_log.read_text(encoding="utf-8")
    error_text = tag_error_log.read_text(encoding="utf-8")
    assert "Starting TLO Tagger" in success_text
    assert "Tagging Path:" in success_text
    assert "ERROR: fake folder | file.flac | simulated anomaly" not in success_text
    assert "ERROR: fake folder | file.flac | simulated anomaly" in error_text
    assert "Complete: folders=1 tagged_files=0 skipped_folders=0 file_errors=1" in error_text


def test_v229_run_tagger_passes_debug_into_tagger_config(tmp_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(T, "validate_required_databases", lambda config: None)
    monkeypatch.setattr(T, "load_artist_matcher", lambda config: object())
    monkeypatch.setattr(T, "_groups_from_inventory_discovery", lambda config, tagging_path: [{"main_dir_path": str(tmp_path / "show")}])

    def fake_process(config, group, artist_matcher, emit=None):
        seen["debug"] = bool(config.debug)
        return T.empty_tag_stats()

    monkeypatch.setattr(T, "process_tagging_group", fake_process)
    T.run_tagger(tlo_home=str(tmp_path), tag_path=str(tmp_path), debug=True, emit=lambda _text: None)
    assert seen["debug"] is True


def _load_tlo_tag_module():
    module_path = Path(__file__).with_name("tlo-tag.py")
    spec = importlib.util.spec_from_file_location("tlo_tag_cli_for_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_v229_tlo_tag_cli_accepts_debug_bool():
    tag_cli = _load_tlo_tag_module()
    assert tag_cli._parse_args(["--TLOHome", "/tmp/tlo", "--debug", "true"]).debug is True
    assert tag_cli._parse_args(["--TLOHome", "/tmp/tlo", "--debug", "false"]).debug is False
    assert tag_cli._parse_args(["--TLOHome", "/tmp/tlo", "--debug"]).debug is True


def test_v229_track_problem_debug_copy_lists_music_files_between_meta_and_setlist(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 Intro.flac"
    audio2 = tmp_path / "02 Song.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Only One Track\n", encoding="utf-8")

    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path: "track 1")
    monkeypatch.setattr(T, "write_audio_tags", lambda *args, **kwargs: None)

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(group_number=9, main_dir_name="Debug Show", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Debug Show",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}

    T.tag_group_with_record(config, group, record, emit=lambda _text: None,
                            allow_unknown_metadata=False,
                            fallback_to_filenames_on_track_problem=False,
                            metadata_problems=[],
                            meta_log_entry="SHOW_NAME: Artist 1977-05-08 Venue City ST\nEND_SHOW_METADATA\n")

    debug_text = next((tmp_path / "debug").glob("*.txt")).read_text(encoding="utf-8")
    assert debug_text.startswith("SHOW_NAME: Artist 1977-05-08 Venue City ST\nEND_SHOW_METADATA")
    assert "----- MUSIC FILES -----" in debug_text
    assert str(audio1) in debug_text
    assert str(audio2) in debug_text
    assert "----- ORIGINAL SETLIST FILE -----" in debug_text
    assert debug_text.index("END_SHOW_METADATA") < debug_text.index("----- MUSIC FILES -----")
    assert debug_text.index("----- MUSIC FILES -----") < debug_text.index("----- ORIGINAL SETLIST FILE -----")


# --------------------------------------------------------------------------- #
# v230 - Broader tag debug copies for skipped/error folders
# --------------------------------------------------------------------------- #

def test_debug_true_writes_setlist_copy_when_track_problem_skips_folder(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 file.flac"
    audio2 = tmp_path / "02 file.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Only One Setlist Track\n", encoding="utf-8")

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=False)
    record = ShowMetadata(group_number=4, main_dir_name="Skipped Debug", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Skipped Debug",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}
    messages = []
    stats = T.tag_group_with_record(config, group, record, emit=messages.append,
                                    allow_unknown_metadata=False,
                                    fallback_to_filenames_on_track_problem=False,
                                    metadata_problems=[],
                                    meta_log_entry="SHOW_NAME: Artist 1977-05-08 Venue City ST\nSETLIST_FILE: " + str(setlist) + "\nEND_SHOW_METADATA\n")

    assert stats["skipped"] == 1
    debug_files = list((tmp_path / "debug").glob("*.txt"))
    assert len(debug_files) == 1
    debug_text = debug_files[0].read_text(encoding="utf-8")
    assert "DEBUG_REASON: TAG_SKIP: track count mismatch: setlist=1 audio_files=2" in debug_text
    assert "----- MUSIC FILES -----" in debug_text
    assert str(audio1) in debug_text and str(audio2) in debug_text
    assert "----- ORIGINAL SETLIST FILE -----" in debug_text
    assert debug_text.rstrip().endswith("1 Only One Setlist Track")
    assert any("wrote tag debug setlist copy" in str(message) for message in messages)


def test_v296_bad_audio_errors_do_not_write_debug_files(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 file.flac"
    audio2 = tmp_path / "02 file.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Song One\n2 Song Two\n", encoding="utf-8")

    def fail_write(*_args, **_kwargs):
        raise RuntimeError("write failed")

    monkeypatch.setattr(T, "write_audio_tags", fail_write)

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=False)
    record = ShowMetadata(group_number=5, main_dir_name="Error Debug", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Error Debug",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}
    messages = []
    stats = T.tag_group_with_record(config, group, record, emit=messages.append,
                                    allow_unknown_metadata=False,
                                    fallback_to_filenames_on_track_problem=False,
                                    metadata_problems=[],
                                    meta_log_entry="SHOW_NAME: Artist 1977-05-08 Venue City ST\nSETLIST_FILE: " + str(setlist) + "\nEND_SHOW_METADATA\n")

    assert stats["errors"] == 2
    assert not (tmp_path / "debug").exists()
    assert any(f"ERROR_AUDIO_FILE: '{audio1}' - write failed" in str(message) for message in messages)
    assert any(f"ERROR_AUDIO_FILE: '{audio2}' - write failed" in str(message) for message in messages)


# --------------------------------------------------------------------------- #
# v231/v290 - Tagger log callback appends directly to the split tag logs
# --------------------------------------------------------------------------- #

def test_v231_tag_log_emit_uses_direct_append_when_logger_method_is_unavailable(tmp_path):
    from inventory_parser_lib import Config
    import logging_lib

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path))
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(tmp_path), 1, log_token="T")
    tag_log = tmp_path / "logs" / "tageT.txt"

    def broken_tag(*_args, **_kwargs):
        raise RuntimeError("simulated stale logging handler")

    config.logs.tag = broken_tag
    emitter = T._build_tag_log_emit(config, emit=lambda _text: None)
    emitter("ERROR: direct append proof | file.flac | simulated anomaly")

    text = tag_log.read_text(encoding="utf-8")
    assert "ERROR: direct append proof | file.flac | simulated anomaly" in text

def test_v231_run_tagger_log_contains_progress_even_if_log_manager_tag_method_breaks(tmp_path, monkeypatch):
    messages = []

    monkeypatch.setattr(T, "validate_required_databases", lambda config: None)
    monkeypatch.setattr(T, "load_artist_matcher", lambda config: object())
    monkeypatch.setattr(T, "_groups_from_inventory_discovery", lambda config, tagging_path: [{"main_dir_path": str(tmp_path / "show")}])

    original_builder = T._build_tag_log_emit

    def wrapped_builder(config, emit):
        def broken_tag(*_args, **_kwargs):
            raise RuntimeError("simulated stale logging handler")
        config.logs.tag = broken_tag
        return original_builder(config, emit)

    monkeypatch.setattr(T, "_build_tag_log_emit", wrapped_builder)

    def fake_process(config, group, artist_matcher, emit=None):
        T._emit(emit, "ERROR: fake folder | file.flac | simulated anomaly")
        return {"groups": 1, "tagged": 0, "skipped": 0, "errors": 1,
                "comma_item_folders": [], "comma_line_folders": [], "etreedb_folders": [], "title_tag_folders": []}

    monkeypatch.setattr(T, "process_tagging_group", fake_process)
    totals = T.run_tagger(tlo_home=str(tmp_path), tag_path=str(tmp_path), emit=messages.append)

    assert totals["errors"] == 1
    success_text = (tmp_path / "logs" / "tagsT.txt").read_text(encoding="utf-8")
    error_text = (tmp_path / "logs" / "tageT.txt").read_text(encoding="utf-8")
    assert "Starting TLO Tagger" in success_text
    assert "ERROR: fake folder | file.flac | simulated anomaly" in error_text
    assert "Complete: folders=1 tagged_files=0 skipped_folders=0 file_errors=1" in error_text

# --------------------------------------------------------------------------- #
# v232 - auCDtect result rows are not song titles
# --------------------------------------------------------------------------- #

def test_tagger_ignores_aucdtect_result_rows_when_no_tracks(tmp_path):
    setlist = tmp_path / "aucdtect.txt"
    setlist.write_text(
        "auCDtect:\n"
        "101 Ted the Mechanic.wav:  track looks like CDDA with probability 100%.\n"
        "102 Strange Kind of Woman.wav:  track looks like CDDA with probability 100%.\n"
        "103 Bloodsucker.wav:  track looks like CDDA with probability 100%.\n",
        encoding="utf-8",
    )
    assert T.parse_setlist_tracks(str(setlist)) == []


def test_tagger_stops_before_aucdtect_result_block_after_tracks(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "Tracks:\n"
        "01 Ted the Mechanic\n"
        "02 Strange Kind of Woman\n"
        "auCDtect:\n"
        "101 Ted the Mechanic.wav:  track looks like CDDA with probability 100%.\n"
        "102 Strange Kind of Woman.wav:  track looks like CDDA with probability 100%.\n"
        "103 Bloodsucker.wav:  track looks like CDDA with probability 100%.\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [(t["normalized_number"], t["title"]) for t in tracks] == [
        (1, "Ted the Mechanic"),
        (2, "Strange Kind of Woman"),
    ]


def test_tagger_rejects_bare_aucdtect_result_line_as_track():
    assert T._parse_track_line("101 Ted the Mechanic.wav:  track looks like CDDA with probability 100%.") is None

# --------------------------------------------------------------------------- #
# v233 - Ordinal headers are not tracks; literal setlist unknown is not debug failure
# --------------------------------------------------------------------------- #

def test_v233_ordinal_event_header_does_not_stop_later_numbered_tracks(tmp_path):
    setlist = tmp_path / "dejohnette_bowie.txt"
    setlist.write_text(
        "Jack DeJohnette & Lester Bowie\n"
        "9th Annual Eddie Moore Jazz Festival\n"
        "Yoshi's\n"
        "Oakland CA\n"
        "August 12, 1998 (Wednesday)\n\n"
        "Source: CS Cardioids > Tascam DA-P1 > DAT (48k)\n"
        "Transfer: DAT > Sony R500 > FLAC16\n\n"
        "Early show (1:14:35):\n"
        "1 (intro)\n"
        "2 (unknown title)\n"
        "3 (unknown title)\n"
        "4 Ntoro 1\n\n"
        "Late show (1:26:22)\n"
        "1 (intro)\n"
        "2 Silver Hollow\n"
        "3 /Stolen Moments >\n"
        "4 (unknown title) >\n"
        "5 (unknown title)\n"
        "6 (encore break)\n"
        "7 Encore: Yourself\n"
        "8 (outro)\n"
        "\ntotal time: 2:40:58\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert len(tracks) == 12
    assert tracks[0]["title"] == "(intro)"
    assert tracks[3]["title"] == "Ntoro 1"
    assert tracks[4]["title"] == "(intro)"
    assert tracks[-1]["title"] == "(outro)"
    assert T._parse_track_line("9th Annual Eddie Moore Jazz Festival") is None


def test_v233_literal_unknown_title_from_setlist_does_not_write_debug_copy(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 Intro.flac"
    audio2 = tmp_path / "02 unknown.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("01 Intro\n02 unknown\n", encoding="utf-8")

    monkeypatch.setattr(T, "write_audio_tags", lambda *args, **kwargs: None)

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(group_number=6, main_dir_name="Literal Unknown", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Literal Unknown",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}

    stats = T.tag_group_with_record(config, group, record, emit=lambda _text: None,
                                    allow_unknown_metadata=True,
                                    fallback_to_filenames_on_track_problem=True,
                                    metadata_problems=[],
                                    meta_log_entry="SHOW_NAME: Artist 1977-05-08 Venue City ST\nEND_SHOW_METADATA\n")

    assert stats["tagged"] == 2
    assert not (tmp_path / "debug").exists()


def test_v300_generated_unknown_from_title_tags_does_not_write_debug_copy(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 file.flac"
    audio2 = tmp_path / "02 file.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("01 Only One Track\n", encoding="utf-8")

    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path: "track 1")
    monkeypatch.setattr(T, "write_audio_tags", lambda *args, **kwargs: None)

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(group_number=7, main_dir_name="Generated Unknown", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Generated Unknown",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}

    stats = T.tag_group_with_record(config, group, record, emit=lambda _text: None,
                                    allow_unknown_metadata=True,
                                    fallback_to_filenames_on_track_problem=True,
                                    metadata_problems=[],
                                    meta_log_entry="SHOW_NAME: Artist 1977-05-08 Venue City ST\nEND_SHOW_METADATA\n")

    assert stats["tagged"] == 2
    assert not (tmp_path / "debug").exists()

# --------------------------------------------------------------------------- #
# v234 - Unnumbered CD/Set blocks and confirmed filename-title fallback
# --------------------------------------------------------------------------- #

def test_v234_parse_unnumbered_set_sections_after_delimiters(tmp_path):
    setlist = tmp_path / "unnumbered_sections.txt"
    setlist.write_text(
        "Artist Name\n"
        "Venue\n\n"
        "CD1:\n"
        "Opening Jam\n"
        "First Song\n"
        "Second Song\n\n"
        "Set 2\n"
        "Third Song\n"
        "Encore Song\n\n"
        "Notes: Great show\n",
        encoding="utf-8",
    )
    tracks, source = T.parse_unnumbered_section_tracks(str(setlist), 5)
    assert source == "unnumbered-sections"
    assert [track["title"] for track in tracks] == [
        "Opening Jam",
        "First Song",
        "Second Song",
        "Third Song",
        "Encore Song",
    ]


def test_v234_filename_title_fallback_extracts_embedded_date_set_track_prefix_and_confirms_setlist(tmp_path):
    audio1 = tmp_path / "jd31998-08-22t01_intro - Happy Birthday.flac"
    audio2 = tmp_path / "jd31998-08-22s2t02_All The Things You Are.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "01. intro - Happy Birthday\n"
        "02. All The Things You Are\n",
        encoding="utf-8",
    )
    tracks, source = T.tracks_from_audio_filenames_confirmed_by_setlist([str(audio2), str(audio1)], str(setlist))
    assert source == "filenames-confirmed"
    assert [track["title"] for track in tracks] == ["intro - Happy Birthday", "All The Things You Are"]


def test_v234_filename_title_fallback_rejects_unconfirmed_title_when_setlist_exists(tmp_path):
    audio1 = tmp_path / "show1998-08-22t01_Not In Setlist.flac"
    audio1.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("01. Different Title\n", encoding="utf-8")
    tracks, source = T.tracks_from_audio_filenames_confirmed_by_setlist([str(audio1)], str(setlist))
    assert tracks == []
    assert source == ""


# --------------------------------------------------------------------------- #
# v235 - Parent/sibling setlist lookup and stricter filename-title fallback
# --------------------------------------------------------------------------- #

def test_v235_parent_setlist_lookup_allowed_for_small_release_parent(tmp_path):
    from tlo_setlist_file_selection import find_setlist_files_for_music_dir

    parent = tmp_path / "Release Parent"
    disc1 = parent / "Disc 1"
    disc2 = parent / "Disc 2"
    disc1.mkdir(parents=True)
    disc2.mkdir()
    audio = disc1 / "01 Song One.flac"
    audio.write_bytes(b"not real audio")
    info = parent / "info.txt"
    info.write_text("01 Song One\n02 Song Two\n", encoding="utf-8")

    candidates = find_setlist_files_for_music_dir([str(audio)], str(disc1), str(disc1))
    assert candidates and candidates[0] == os.path.normpath(str(info))


def test_v235_sibling_info_folder_setlist_lookup_for_small_parent(tmp_path):
    from tlo_setlist_file_selection import find_setlist_files_for_music_dir

    parent = tmp_path / "Split Release"
    disc1 = parent / "Split Release CD1"
    disc2 = parent / "Split Release CD2"
    info_dir = parent / "set list"
    disc1.mkdir(parents=True)
    disc2.mkdir()
    info_dir.mkdir()
    audio = disc1 / "01 Song One.flac"
    audio.write_bytes(b"not real audio")
    info = info_dir / "setlist.txt"
    info.write_text("01 Song One\n02 Song Two\n", encoding="utf-8")

    candidates = find_setlist_files_for_music_dir([str(audio)], str(disc1), str(disc1))
    assert os.path.normpath(str(info)) in candidates




def test_v252_sibling_extras_info_folder_setlist_lookup_for_wrapper_release(tmp_path):
    from tlo_setlist_file_selection import find_setlist_files_for_music_dir

    parent = tmp_path / "Derek & The Dominos - Feast Away"
    disc1 = parent / "Disc 1"
    disc2 = parent / "Disc 2"
    extras = parent / "Extras"
    disc1.mkdir(parents=True)
    disc2.mkdir()
    extras.mkdir()
    audio = disc1 / "Track01.flac"
    audio.write_bytes(b"not real audio")
    info = extras / "info.txt"
    info.write_text("01 Song One\n02 Song Two\n", encoding="utf-8")

    candidates = find_setlist_files_for_music_dir([str(audio)], str(disc1), str(parent))
    assert candidates and candidates[0] == os.path.normpath(str(info))


def test_v252_generic_track_files_sort_by_parent_disc_folder(tmp_path):
    files = []
    for disc, count in ((1, 2), (2, 2), (3, 1)):
        disc_dir = tmp_path / f"Disc {disc}"
        disc_dir.mkdir(parents=True)
        for track in range(1, count + 1):
            path = disc_dir / f"Track{track:02d}.flac"
            path.write_bytes(b"not real audio")
            files.append(str(path))

    shuffled = [files[0], files[2], files[4], files[1], files[3]]
    ordered = sorted(shuffled, key=T._audio_track_order)
    assert [Path(path).parent.name + "/" + Path(path).name for path in ordered] == [
        "Disc 1/Track01.flac",
        "Disc 1/Track02.flac",
        "Disc 2/Track01.flac",
        "Disc 2/Track02.flac",
        "Disc 3/Track01.flac",
    ]

def test_v235_parent_setlist_lookup_rejects_broad_parent_with_many_children(tmp_path):
    from tlo_setlist_file_selection import find_setlist_files_for_music_dir

    parent = tmp_path / "Artist Folder"
    parent.mkdir()
    music_dir = parent / "Show 01"
    music_dir.mkdir()
    audio = music_dir / "01 Song One.flac"
    audio.write_bytes(b"not real audio")
    for idx in range(2, 15):
        (parent / f"Show {idx:02d}").mkdir()
    parent_info = parent / "info.txt"
    parent_info.write_text("Artist-level notes\n", encoding="utf-8")

    candidates = find_setlist_files_for_music_dir([str(audio)], str(music_dir), str(music_dir))
    assert os.path.normpath(str(parent_info)) not in candidates


def test_v235_filename_fallback_rejects_fill_in_track_identifiers(tmp_path):
    audio1 = tmp_path / "Track 01.flac"
    audio2 = tmp_path / "01 Track.flac"
    audio3 = tmp_path / "show1998-08-22d1t03_Track 03.flac"
    for audio in (audio1, audio2, audio3):
        audio.write_bytes(b"not real audio")
    assert T.track_title_from_audio_filename(str(audio1)) == "unknown"
    assert T.track_title_from_audio_filename(str(audio2)) == "unknown"
    assert T.track_title_from_audio_filename(str(audio3)) == "unknown"


def test_v235_filename_fallback_accepts_date_disc_track_prefix_with_real_title_and_confirms(tmp_path):
    audio = tmp_path / "show1998-08-22d1t03_Real Song Title.flac"
    audio.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("Real Song Title\n", encoding="utf-8")
    tracks, source = T.tracks_from_audio_filenames_confirmed_by_setlist([str(audio)], str(setlist))
    assert source == "filenames-confirmed"
    assert [track["title"] for track in tracks] == ["Real Song Title"]


# --------------------------------------------------------------------------- #
# v236 - Set/disc track tokens and patch terminators
# --------------------------------------------------------------------------- #

def test_v236_parse_set_and_disc_track_identifier_rows(tmp_path):
    setlist = tmp_path / "token_tracks.txt"
    setlist.write_text(
        "Artist\nVenue\n\n"
        "s2t01 - First Song\n"
        "cd1t02 Second Song\n"
        "d01t03: Third Song\n"
        "Disc 1 Track 04 Fourth Song\n"
        "Set 2 track 05 Fifth Song\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == [
        "First Song",
        "Second Song",
        "Third Song",
        "Fourth Song",
        "Fifth Song",
    ]
    assert [track["original_number"] for track in tracks] == [1, 2, 3, 4, 5]


def test_v236_patch_line_stops_after_track_list(tmp_path):
    setlist = tmp_path / "patch_after_tracks.txt"
    setlist.write_text(
        "01 Real Opener\n"
        "02 Real Closer\n"
        "Patch notes: patched from another source\n"
        "03 Not A Song From The Setlist\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == ["Real Opener", "Real Closer"]


def test_v236_filename_fallback_accepts_cd_track_prefix(tmp_path):
    audio = tmp_path / "cd1t01 - Real Song Title.flac"
    audio.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("Real Song Title\n", encoding="utf-8")
    tracks, source = T.tracks_from_audio_filenames_confirmed_by_setlist([str(audio)], str(setlist))
    assert source == "filenames-confirmed"
    assert [track["title"] for track in tracks] == ["Real Song Title"]

# --------------------------------------------------------------------------- #
# v237 - Tagging clears stale track/disc total tags
# --------------------------------------------------------------------------- #

def test_v237_easy_tag_writer_clears_tracktotal_discnumber_disctotal(monkeypatch, tmp_path):
    class FakeAudio(dict):
        tags = True
        def add_tags(self):
            self.tags = True
        def save(self):
            self.saved = True

    fake = FakeAudio({
        "TRACKTOTAL": ["12"],
        "discnumber": ["1"],
        "DISCTOTAL": ["2"],
        "genre": ["Jazz"],
    })
    monkeypatch.setattr(T, "MutagenFile", lambda path, easy=True: fake)

    T._write_easy_tags(str(tmp_path / "song.flac"), "Artist", "Album", "01", "Title")

    assert "TRACKTOTAL" not in fake
    assert "discnumber" not in fake
    assert "DISCTOTAL" not in fake
    assert fake["artist"] == ["Artist"]
    assert fake["album"] == ["Album"]
    assert fake["title"] == ["Title"]
    assert fake["tracknumber"] == ["01"]
    assert fake["genre"] == ["Jazz"]


def test_v237_id3_clear_removes_disc_and_total_frames():
    class FakeFrame:
        FrameID = "TXXX"
        def __init__(self, desc):
            self.desc = desc

    class FakeTags(dict):
        def __init__(self):
            super().__init__({
                "TXXX:TRACKTOTAL": FakeFrame("TRACKTOTAL"),
                "TXXX:DISCTOTAL": FakeFrame("DISCTOTAL"),
                "TXXX:KEEP": FakeFrame("KEEP"),
                "TPE1": object(),
            })
            self.deleted = []
        def delall(self, key):
            self.deleted.append(key)
            for existing in list(self.keys()):
                if existing == key or existing.startswith(key + ":"):
                    del self[existing]

    tags = FakeTags()
    T._clear_total_disc_id3_tags(tags)

    assert "TPOS" in tags.deleted
    assert "TXXX:TRACKTOTAL" not in tags
    assert "TXXX:DISCTOTAL" not in tags
    assert "TXXX:KEEP" in tags
    assert "TPE1" in tags


def test_v237_mp4_writer_clears_disc_and_does_not_write_track_total(monkeypatch, tmp_path):
    class FakeMP4(dict):
        def save(self):
            self.saved = True

    fake = FakeMP4({
        "disk": [(1, 2)],
        "----:com.apple.iTunes:TRACKTOTAL": [b"12"],
    })
    monkeypatch.setattr(T, "MP4", lambda path: fake)

    T._write_mp4_tags(str(tmp_path / "song.m4a"), "Artist", "Album", "03", "Title", 12)

    assert "disk" not in fake
    assert "----:com.apple.iTunes:TRACKTOTAL" not in fake
    assert fake["trkn"] == [(3, 0)]
    assert fake["\xa9ART"] == ["Artist"]
    assert fake["\xa9alb"] == ["Album"]
    assert fake["\xa9nam"] == ["Title"]

# --------------------------------------------------------------------------- #
# v238/v239 - Optional app-bundled SHN-to-FLAC conversion before tagging
# --------------------------------------------------------------------------- #

def test_v238_option_registry_adds_convert_shn_flag_and_gui_checkbox():
    from tlo_options import OPTIONS_BY_FIELD
    opt = OPTIONS_BY_FIELD["convert_shn"]
    assert opt.flag == "--convert-shn"
    assert opt.gui == "checkbox"
    assert opt.gui_label == "Convert shn"


def test_v238_inventory_cli_accepts_convert_shn(monkeypatch, tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(sys, "argv", ["tlo-gi.py", "--TLOHome", str(home), "--convert-shn"])
    values = IPL.parse_command_line()
    assert values["convert_shn"] is True


def test_v238_tagger_parser_accepts_convert_shn():
    module_path = Path(__file__).with_name("tlo-tag.py")
    spec = importlib.util.spec_from_file_location("tlo_tag_for_v238_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    args = module._parse_args(["--convert-shn", "--tag-path", "/tmp/tags"])
    assert args.convert_shn is True
    assert args.tagPath == "/tmp/tags"


def test_v238_prepare_audio_files_converts_shn_and_deletes_original(monkeypatch, tmp_path):
    from inventory_parser_lib import Config

    shn = tmp_path / "01 Song One.shn"
    wav = tmp_path / "02 Song Two.wav"
    shn.write_bytes(b"fake shn")
    wav.write_bytes(b"fake wav")
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), convert_shn=True)
    group = {"music_files": [str(shn), str(wav)]}
    messages = []

    monkeypatch.setattr(T, "_bundled_ffmpeg_executable", lambda: "/usr/bin/ffmpeg")

    def fake_run(command, stdout=None, stderr=None, text=None, timeout=None):
        out = Path(command[-1])
        out.write_bytes(b"fake flac")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(T.subprocess, "run", fake_run)

    audio_files, errors = T._prepare_audio_files_for_tagging(config, group, [str(shn), str(wav)], emit=messages.append)

    flac = tmp_path / "01 Song One.flac"
    assert errors == 0
    assert not shn.exists()
    assert flac.exists()
    assert os.path.normpath(str(flac)) in audio_files
    assert os.path.normpath(str(wav)) in audio_files
    assert any("CONVERTED SHN" in msg for msg in messages)


def test_v238_prepare_audio_files_logs_failed_shn_conversion_and_skips_file(monkeypatch, tmp_path):
    from inventory_parser_lib import Config

    shn = tmp_path / "01 Song One.shn"
    keep = tmp_path / "02 Song Two.flac"
    shn.write_bytes(b"fake shn")
    keep.write_bytes(b"fake flac")
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), convert_shn=True)
    group = {"music_files": [str(shn), str(keep)]}
    messages = []

    monkeypatch.setattr(T, "_bundled_ffmpeg_executable", lambda: "")

    audio_files, errors = T._prepare_audio_files_for_tagging(config, group, [str(shn), str(keep)], emit=messages.append)

    assert errors == 1
    assert shn.exists()
    assert os.path.normpath(str(shn)) not in audio_files
    assert os.path.normpath(str(keep)) in audio_files
    assert any(str(msg).strip() == f"ERROR_AUDIO_FILE: '{shn}' - SHN conversion failed: bundled native SHN converter is unavailable; rebuild the PyInstaller app with imageio-ffmpeg data included" for msg in messages)


def test_v238_tag_group_converts_shn_then_tags_flac(monkeypatch, tmp_path):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    shn = tmp_path / "01 Song One.shn"
    shn.write_bytes(b"fake shn")
    setlist = tmp_path / "info.txt"
    setlist.write_text("01 Song One\n", encoding="utf-8")
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), convert_shn=True)
    record = ShowMetadata(
        group_number=1,
        main_dir_name="SHN Show",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        music_file_count=1,
        artist="Artist",
        date="1999-01-02",
        venue="Venue",
        location="City ST",
        show_name="Artist 1999-01-02 Venue City ST",
    )
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "SHN Show", "setlist_file": str(setlist), "music_files": [str(shn)]}
    tagged = []

    monkeypatch.setattr(T, "_bundled_ffmpeg_executable", lambda: "/usr/bin/ffmpeg")

    def fake_run(command, stdout=None, stderr=None, text=None, timeout=None):
        Path(command[-1]).write_bytes(b"fake flac")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(T.subprocess, "run", fake_run)
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track, title, total_tracks=0: tagged.append((path, artist, album, track, title)))

    stats = T.tag_group_with_record(
        config,
        group,
        record,
        emit=lambda _text: None,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        metadata_problems=[],
    )

    flac = tmp_path / "01 Song One.flac"
    assert stats["tagged"] == 1
    assert stats["errors"] == 0
    assert not shn.exists()
    assert flac.exists()
    assert tagged[0][0] == os.path.normpath(str(flac))
    assert tagged[0][4] == "Song One"


def test_v239_shn_conversion_uses_only_bundled_converter(monkeypatch, tmp_path):
    shn = tmp_path / "01 Song One.shn"
    shn.write_bytes(b"fake shn")
    called = []

    monkeypatch.setenv("TLO_FFMPEG", "/user/path/ffmpeg")
    monkeypatch.setattr(T, "_bundled_ffmpeg_executable", lambda: "/app/bundled/ffmpeg")

    def fake_run(command, stdout=None, stderr=None, text=None, timeout=None):
        called.append(command)
        Path(command[-1]).write_bytes(b"fake flac")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(T.subprocess, "run", fake_run)

    out = T.convert_shn_to_flac(str(shn), emit=lambda _text: None)

    assert called
    assert called[0][0] == "/app/bundled/ffmpeg"
    assert out.endswith(".flac")
    assert not shn.exists()


def test_v239_missing_bundled_converter_message(monkeypatch, tmp_path):
    shn = tmp_path / "01 Song One.shn"
    shn.write_bytes(b"fake shn")
    monkeypatch.setattr(T, "_bundled_ffmpeg_executable", lambda: "")

    with pytest.raises(T.TaggerError) as exc:
        T.convert_shn_to_flac(str(shn), emit=lambda _text: None)

    assert "bundled native SHN converter is unavailable" in str(exc.value)
    assert shn.exists()

# --------------------------------------------------------------------------- #
# v240 - Convert SHN option must be visible at tag time and SHN must not reach
#        the generic tag writer when conversion is enabled.
# --------------------------------------------------------------------------- #

def test_v240_tag_group_logs_convert_shn_enabled_when_shn_detected(monkeypatch, tmp_path):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    shn = tmp_path / "skb2002-06-01d1t01.shn"
    shn.write_bytes(b"fake shn")
    setlist = tmp_path / "setlist.txt"
    setlist.write_text("01 Song One\n", encoding="utf-8")
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), convert_shn=True)
    record = ShowMetadata(
        group_number=1,
        main_dir_name="SKB Show",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        music_file_count=1,
        artist="Steve Kimock Band",
        date="2002-06-01",
        venue="House Of Blues",
        location="West Hollywood CA",
        show_name="Steve Kimock Band 2002-06-01 House Of Blues West Hollywood CA",
    )
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "SKB Show", "setlist_file": str(setlist), "music_dirs": [str(tmp_path)], "music_files": [str(shn)]}
    messages = []

    monkeypatch.setattr(T, "_bundled_ffmpeg_executable", lambda: "/usr/bin/ffmpeg")

    def fake_run(command, stdout=None, stderr=None, text=None, timeout=None):
        Path(command[-1]).write_bytes(b"fake flac")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(T.subprocess, "run", fake_run)
    monkeypatch.setattr(T, "write_audio_tags", lambda *args, **kwargs: None)

    stats = T.tag_group_with_record(
        config,
        group,
        record,
        emit=messages.append,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        metadata_problems=[],
    )

    assert stats["tagged"] == 1
    assert any("SHN files detected: 1; convert shn=yes" in msg for msg in messages)
    assert any("CONVERTED SHN" in msg for msg in messages)
    assert not any("unsupported or non-taggable audio extension: .shn" in msg for msg in messages)


def test_v240_shn_remaining_after_conversion_enabled_is_skipped_before_tag_writer(monkeypatch, tmp_path):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    shn = tmp_path / "skb2002-06-01d1t01.shn"
    shn.write_bytes(b"fake shn")
    setlist = tmp_path / "setlist.txt"
    setlist.write_text("01 Song One\n", encoding="utf-8")
    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), convert_shn=True)
    record = ShowMetadata(
        group_number=1,
        main_dir_name="SKB Show",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        music_file_count=1,
        artist="Steve Kimock Band",
        date="2002-06-01",
        venue="House Of Blues",
        location="West Hollywood CA",
        show_name="Steve Kimock Band 2002-06-01 House Of Blues West Hollywood CA",
    )
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "SKB Show", "setlist_file": str(setlist), "music_dirs": [str(tmp_path)], "music_files": [str(shn)]}
    messages = []
    write_calls = []

    def fake_prepare(config, group, audio_files, emit=None):
        return [str(shn)], 0

    monkeypatch.setattr(T, "_prepare_audio_files_for_tagging", fake_prepare)
    monkeypatch.setattr(T, "write_audio_tags", lambda *args, **kwargs: write_calls.append(args))

    stats = T.tag_group_with_record(
        config,
        group,
        record,
        emit=messages.append,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        metadata_problems=[],
    )

    assert stats["tagged"] == 0
    assert stats["errors"] == 1
    assert write_calls == []
    assert any("remained SHN after conversion preparation" in msg for msg in messages)
    assert not any("unsupported or non-taggable audio extension: .shn" in msg for msg in messages)

# --------------------------------------------------------------------------- #
# v240 - SHN conversion must propagate through tagger Config construction, and
#        trailing/bare duration stamps must not be written into track titles.
# --------------------------------------------------------------------------- #

def test_v240_build_tagger_config_preserves_convert_shn(tmp_path):
    config = T.build_tagger_config(tlo_home=str(tmp_path), convert_shn=True)
    assert config.convert_shn is True


def test_v240_clean_track_title_strips_trailing_duration_variants():
    assert T._clean_track_title("Song Title 08:23") == "Song Title"
    assert T._clean_track_title("Song Title 8:23") == "Song Title"
    assert T._clean_track_title("Song Title 1:23:48") == "Song Title"
    assert T._clean_track_title("Song Title [8:23]") == "Song Title"
    assert T._clean_track_title("Song Title (8:23)") == "Song Title"
    assert T._clean_track_title("8:23 Song Title") == "Song Title"
    assert T._clean_track_title("[8:23] Song Title") == "Song Title"


def test_v240_tag_writer_strips_duration_before_writing(monkeypatch, tmp_path):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio = tmp_path / "01 Song Title.flac"
    audio.write_bytes(b"fake flac")
    setlist = tmp_path / "setlist.txt"
    setlist.write_text("01 Song Title [8:23]\n", encoding="utf-8")
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), convert_shn=False)
    record = ShowMetadata(
        group_number=1,
        main_dir_name="Duration Show",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        music_file_count=1,
        artist="Artist",
        date="2000-01-01",
        venue="Venue",
        location="City ST",
        show_name="Artist 2000-01-01 Venue City ST",
    )
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Duration Show", "setlist_file": str(setlist), "music_dirs": [str(tmp_path)], "music_files": [str(audio)]}
    written = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_no, title, total_tracks=None: written.append(title))

    stats = T.tag_group_with_record(
        config,
        group,
        record,
        emit=lambda _text: None,
        allow_unknown_metadata=True,
        fallback_to_filenames_on_track_problem=True,
        metadata_problems=[],
    )

    assert stats["tagged"] == 1
    assert written == ["Song Title"]

# --------------------------------------------------------------------------- #
# v241 - Tag in Place/Tag Copy During Inventory and Rename Compliantly.
# --------------------------------------------------------------------------- #

def test_v241_option_registry_adds_tag_copy_and_rename_options():
    from tlo_options import OPTIONS_BY_FIELD

    assert OPTIONS_BY_FIELD["tag_during_inventory"].gui_label == "Tag in Place"
    assert OPTIONS_BY_FIELD["tag_copy_during_inventory"].flag == "--tag-copy-during-inventory"
    assert OPTIONS_BY_FIELD["tag_copy_during_inventory"].gui_label == "Tag Copy"
    assert OPTIONS_BY_FIELD["rename_compliantly"].flag == "--rename-compliantly"
    assert OPTIONS_BY_FIELD["tag_copy_destination"].flag == "--tag-copy-destination"


def test_v241_tag_copy_cli_validation_requires_destination_and_exclusivity(tmp_path):
    values = {"tag_copy_during_inventory": True, "tag_copy_destination": ""}
    with pytest.raises(ValueError):
        IPL._validate_tag_copy_values(values)

    values = {
        "tag_during_inventory": True,
        "tag_copy_during_inventory": True,
        "tag_copy_destination": str(tmp_path),
    }
    with pytest.raises(ValueError):
        IPL._validate_tag_copy_values(values)

    values = {"tag_copy_during_inventory": True, "tag_copy_destination": str(tmp_path)}
    IPL._validate_tag_copy_values(values)
    assert values["tag_copy_destination"] == os.path.normpath(str(tmp_path))


def test_v241_tag_copy_preparation_copies_to_show_name_without_touching_source(tmp_path):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    source = tmp_path / "Original Folder"
    source.mkdir()
    audio = source / "01 Song.flac"
    audio.write_bytes(b"fake")
    setlist = source / "info.txt"
    setlist.write_text("01 Song\n", encoding="utf-8")
    dest = tmp_path / "copies"
    dest.mkdir()

    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "music_sample_files": [str(audio)],
        "setlist_file": str(setlist),
        "setlist_files": [str(setlist)],
        "txt_files": [str(setlist)],
    }
    record = ShowMetadata(
        group_number=1,
        main_dir_name=source.name,
        main_dir_path=str(source),
        setlist_file=str(setlist),
        music_file_count=1,
        artist="Artist",
        date="2000-01-02",
        venue="Venue",
        location="City ST",
        show_name="Artist 2000-01-02 Venue City ST",
        music_dirs=[str(source)],
        setlist_files=[str(setlist)],
    )
    config = Config(
        debug=False,
        silent=True,
        TLOHome=str(tmp_path),
        tag_copy_during_inventory=True,
        tag_copy_destination=str(dest),
        rename_compliantly=True,
    )
    messages = []
    copied_group, copied_record = T.prepare_inventory_tagging_target(config, group, record, emit=messages.append)

    expected = dest / "Artist 2000-01-02 Venue City ST"
    assert source.exists()
    assert expected.is_dir()
    assert (expected / "01 Song.flac").is_file()
    assert copied_group["main_dir_path"] == os.path.normpath(str(expected))
    assert copied_record.main_dir_path == os.path.normpath(str(expected))
    assert record.main_dir_path == os.path.normpath(str(source))
    assert any("TAG_COPY:" in msg for msg in messages)


def test_v241_rename_compliantly_in_place_renames_group_and_record(tmp_path):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    source = tmp_path / "bad folder name"
    source.mkdir()
    audio = source / "01 Song.flac"
    audio.write_bytes(b"fake")
    setlist = source / "info.txt"
    setlist.write_text("01 Song\n", encoding="utf-8")
    show_name = "Artist 2001-03-04 Nice Venue Boston MA"
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "music_sample_files": [str(audio)],
        "setlist_file": str(setlist),
        "setlist_files": [str(setlist)],
        "txt_files": [str(setlist)],
    }
    record = ShowMetadata(
        group_number=1,
        main_dir_name=source.name,
        main_dir_path=str(source),
        setlist_file=str(setlist),
        music_file_count=1,
        artist="Artist",
        date="2001-03-04",
        venue="Nice Venue",
        location="Boston MA",
        show_name=show_name,
        music_dirs=[str(source)],
        setlist_files=[str(setlist)],
    )
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), tag_during_inventory=True, rename_compliantly=True)
    renamed_group, renamed_record = T.prepare_inventory_tagging_target(config, group, record, emit=lambda _text: None)
    expected = tmp_path / show_name

    assert not source.exists()
    assert expected.is_dir()
    assert renamed_group is group
    assert renamed_record is record
    assert group["main_dir_path"] == os.path.normpath(str(expected))
    assert record.main_dir_path == os.path.normpath(str(expected))
    assert group["setlist_file"] == os.path.normpath(str(expected / "info.txt"))

# --------------------------------------------------------------------------- #
# v242 - Tag Copy confirmation cancel is silent.
# --------------------------------------------------------------------------- #

def test_v242_gui_inventory_start_cancel_is_silent_before_general_error_handler():
    from pathlib import Path

    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    method_start = source.index("    def _start(self):")
    marker = "try:\n            config = self._build_config()"
    start = source.index(marker, method_start)
    snippet = source[start:source.index("        clear_cancel_request()", start)]
    assert "except _InventoryStartCancelled:\n            return" in snippet
    assert snippet.index("except _InventoryStartCancelled") < snippet.index("except Exception as exc")


# --------------------------------------------------------------------------- #
# v243 - Tag Copy/Rename Compliantly apply to Add Shows and Tag workflows.
# --------------------------------------------------------------------------- #

def test_v243_gui_add_shows_start_cancel_is_silent_before_general_error_handler():
    from pathlib import Path

    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    method_start = source.index("    def _open_add_to_inventory(self):")
    marker = "try:\n            config = self._build_config(for_add_shows=True)"
    start = source.index(marker, method_start)
    snippet = source[start:source.index("        script_path = updater_delete_script_path", start)]
    assert "except _InventoryStartCancelled:\n            return" in snippet
    assert snippet.index("except _InventoryStartCancelled") < snippet.index("except Exception as exc")


def test_v243_tagger_config_preserves_copy_destination_and_rename(tmp_path):
    import tlo_tag_lib as T

    home = tmp_path / "TLOHome"
    home.mkdir()
    dest = tmp_path / "copies"
    dest.mkdir()

    config = T.build_tagger_config(
        tlo_home=str(home),
        tag_copy=True,
        tag_copy_destination=str(dest),
        rename_compliantly=True,
    )

    assert config.tag_copy_during_inventory is True
    assert config.tag_during_inventory is False
    assert config.tag_copy_destination == os.path.normpath(str(dest))
    assert config.rename_compliantly is True


def test_v243_process_tagging_group_prepares_copy_or_rename_target():
    import inspect
    import tlo_tag_lib as T

    source = inspect.getsource(T.process_tagging_group)
    assert "prepare_inventory_tagging_target(config, group, record" in source
    assert 'getattr(config, "tag_copy_during_inventory", False)' in source
    assert 'getattr(config, "rename_compliantly", False)' in source


def test_v243_tagger_parser_accepts_tag_copy_and_rename(tmp_path):
    import importlib.util

    module_path = os.path.join(os.path.dirname(__file__), "tlo-tag.py")
    spec = importlib.util.spec_from_file_location("tlo_tag_cli_v243", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    dest = tmp_path / "copies"
    dest.mkdir()
    args = module._parse_args([
        "--tag-copy-during-inventory",
        "--tag-copy-destination",
        str(dest),
        "--rename-compliantly",
    ])

    assert args.tag_copy_during_inventory is True
    assert args.tag_copy_destination == os.path.normpath(str(dest))
    assert args.rename_compliantly is True


# --------------------------------------------------------------------------- #
# v244 - GUI Tag inherits main-window tag mode settings; no tagger checkboxes.
# --------------------------------------------------------------------------- #

def test_v244_tagger_window_has_no_mode_checkboxes():
    import inspect
    import importlib.util

    module_path = os.path.join(os.path.dirname(__file__), "tlo-ggi.py")
    spec = importlib.util.spec_from_file_location("tlo_ggi_gui_v244", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    build_source = inspect.getsource(module.TaggerWindow._build)
    start_source = inspect.getsource(module.TaggerWindow._start_tagging)

    assert "ttk.Checkbutton" not in build_source
    assert "tag_copy_var" not in build_source
    assert "tag_in_place_var" not in build_source
    assert "rename_compliantly_var" not in build_source
    assert "tag_copy = bool(self.tag_copy)" in start_source
    assert "tag_in_place=bool(self.tag_in_place)" in start_source
    assert "rename_compliantly=bool(self.rename_compliantly)" in start_source
    assert "tag_copy_var" not in start_source
    assert "rename_compliantly_var" not in start_source


def test_v244_open_tagger_passes_main_window_values_to_tagger_window():
    from pathlib import Path

    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    method_start = source.index("    def _open_tagger(self):")
    call_start = source.index("        TaggerWindow(", method_start)
    snippet = source[call_start:source.index("\n        )", call_start) + len("\n        )")]

    assert 'tag_in_place = bool(self.bool_vars["tag_during_inventory"].get())' in source[method_start:call_start]
    assert 'tag_copy = bool(self.bool_vars["tag_copy_during_inventory"].get())' in source[method_start:call_start]
    assert 'tag_in_place=tag_in_place' in snippet
    assert 'tag_copy=tag_copy' in snippet
    assert 'rename_compliantly=rename_compliantly' in snippet
    assert 'convert_shn=bool(self.bool_vars["convert_shn"].get())' in snippet


# --------------------------------------------------------------------------- #
# v245 - Main GUI removes Silent checkbox, repositions Convert shn, shrinks console,
#        and reduces setlist export progress chatter.
# --------------------------------------------------------------------------- #

def test_v245_silent_kept_cli_only_and_convert_shn_uses_former_silent_slot():
    from tlo_options import GUI_CHECKBOX_OPTIONS, OPTIONS_BY_FIELD

    assert OPTIONS_BY_FIELD["silent"].flag == "--silent"
    assert OPTIONS_BY_FIELD["silent"].gui is None
    assert "silent" not in {opt.config_field for opt in GUI_CHECKBOX_OPTIONS}

    convert = OPTIONS_BY_FIELD["convert_shn"]
    assert convert.gui == "checkbox"
    assert convert.gui_row == 1
    assert convert.gui_col == 3


def test_v245_gui_build_config_takes_silent_from_cli_not_checkbox():
    from pathlib import Path

    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    build_config = source[source.index("    def _build_config(self, *, for_add_shows=False):"):source.index("    def _pause_inventory(self):")]
    build_method = source[source.index("    def _build(self):"):source.index("    def _enable_search_path_drag_drop(self):")]

    assert 'silent = bool(getattr(self.cli_args, "silent", False))' in build_config
    assert 'self.bool_vars["silent"]' not in build_config
    assert 'height=21' in build_method


def test_v245_postprocess_setlist_progress_is_throttled():
    from pathlib import Path

    source = Path(__file__).with_name("tlo_postprocess.py").read_text(encoding="utf-8")
    assert "progress_interval = max(1000, total_records // 10) if total_records else 0" in source
    assert "processed == len(group)" not in source
    assert "processed <= group_size" not in source

# --------------------------------------------------------------------------- #
# v246 - Add Shows inherits main-window Compliant/Rename Compliantly and ignores
#        Tag in Place / Tag Copy; Rename Compliantly requires a tag mode for
#        Tag and Full Inventory.
# --------------------------------------------------------------------------- #

def test_v246_add_shows_window_has_no_compliant_checkbox_and_does_not_mutate_compliant():
    import inspect
    import importlib.util

    module_path = os.path.join(os.path.dirname(__file__), "tlo-ggi.py")
    spec = importlib.util.spec_from_file_location("tlo_ggi_gui_v246_addshows", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    build_source = inspect.getsource(module.AddToInventoryWindow._build)
    refresh_source = inspect.getsource(module.AddToInventoryWindow._refresh_config)

    assert "compliant_var" not in build_source
    assert 'ttk.Checkbutton(frm, text="Compliant"' not in build_source
    assert "Mode: {'Compliant'" in build_source
    assert "self.config.compliant" not in refresh_source


def test_v246_open_add_shows_uses_add_shows_config_mode():
    from pathlib import Path

    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    method_start = source.index("    def _open_add_to_inventory(self):")
    method_end = source.index("    def _show_backup_alert", method_start)
    snippet = source[method_start:method_end]
    assert "config = self._build_config(for_add_shows=True)" in snippet


def test_v246_build_config_add_shows_keeps_rename():
    from pathlib import Path

    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    build_config = source[source.index("    def _build_config(self, *, for_add_shows=False):"):source.index("    def _pause_inventory(self):")]

    assert "if for_add_shows:" in build_config
    assert "rename_compliantly=rename_compliantly" in build_config


def test_v246_rename_compliantly_validation_is_superseded_by_v303(tmp_path):
    from inventory_parser_lib import _validate_tag_copy_values
    import tlo_tag_lib as T

    _validate_tag_copy_values({"rename_compliantly": True})
    home = tmp_path / "TLOHome"
    home.mkdir()
    config = T.build_tagger_config(tlo_home=str(home), tag_in_place=False, tag_copy=False, rename_compliantly=True)
    assert config.rename_compliantly is True


def test_v246_add_shows_rename_compliantly_renames_ready_folder_in_place(tmp_path):
    import json
    from types import SimpleNamespace
    import tlo_inventory_update as U

    folder = tmp_path / "bad folder"
    folder.mkdir()
    info = folder / "info.txt"
    info.write_text("01 Song\n", encoding="utf-8")
    record = {
        "show_name": "Artist 2001-02-03 Venue Boston MA",
        "main_dir_path": str(folder),
        "setlist_file": str(info),
        "setlist_files_json": json.dumps([str(info)]),
        "music_dirs_json": json.dumps([str(folder)]),
    }

    new_folder = U._rename_add_shows_folder_compliantly(SimpleNamespace(rename_compliantly=True), str(folder), record)
    expected = tmp_path / "Artist 2001-02-03 Venue Boston MA"

    assert new_folder == os.path.normpath(str(expected))
    assert expected.is_dir()
    assert not folder.exists()
    assert record["main_dir_path"] == os.path.normpath(str(expected))
    assert record["setlist_file"] == os.path.normpath(str(expected / "info.txt"))
    assert json.loads(record["music_dirs_json"]) == [os.path.normpath(str(expected))]

# --------------------------------------------------------------------------- #
# v247 - Updater window title bar/banner cleanup.
# --------------------------------------------------------------------------- #

def test_v247_updater_window_title_bar_and_banner_are_not_duplicated():
    from pathlib import Path

    gui_source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    update_source = Path(__file__).with_name("tlo_inventory_update.py").read_text(encoding="utf-8")
    build_source = gui_source[gui_source.index("class AddToInventoryWindow:"):gui_source.index("class DuplicateHandlerWindow:")]

    assert 'UPDATER_TITLE = "Traders Little Helper™ Inventory Update App"' in update_source
    assert 'UPDATER_DISPLAY_VERSION = versioned_title("TLO Inventory Updater")' in update_source
    assert "self.window.title(UPDATER_DISPLAY_VERSION)" in build_source
    assert "text=UPDATER_TITLE, font=title_font" in build_source
    assert "text=UPDATER_DISPLAY_VERSION, font=title_font" not in build_source
    assert "text=UPDATER_TITLE).grid" not in build_source

# --------------------------------------------------------------------------- #
# v248 - Do not let duration/sample-rate technical lines inflate setlist track
#        counts before falling back to empty title tags.
# --------------------------------------------------------------------------- #

def test_v248_setlist_parser_skips_duration_and_sample_rate_metadata(tmp_path):
    import tlo_tag_lib as T

    assert T._parse_track_line("40:18") is None
    assert T._parse_track_line("24bit/48kHz") is None
    assert T._parse_track_line("44.1kHz/16bit") is None
    assert T._parse_track_line("96khz24bit") is None
    assert T._parse_track_line("01. intro") == (1, "intro")

    setlist = tmp_path / "devo1977-12-31.txt"
    setlist.write_text(
        """DEVO
December 31, 1977
Santa Monica Civic Auditorium
Santa Monica, CA

SOURCE:
unknown > unknown

GENERATION:
ANA(x) > WAV [44.1kHz/16bit] > FLAC [Level 8]

LENGTH:
40:18

TRACKS:
01. intro
02. Jocko Homo
03. Satisfaction
04. Too Much Paranoias
05. Wiggly World
06. Uncontrollable Urge
07. Mongoloid
08. Smart Patrol
09. Mr. DNA
10. Sloppy
11. Come Back Jonee
12. Clockout

MD5 FINGERPRINTS:
22694bacb00afad7bf9eb78c4ae29d90 *devo1977-12-31t01.flac
""",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == [
        "intro",
        "Jocko Homo",
        "Satisfaction",
        "Too Much Paranoias",
        "Wiggly World",
        "Uncontrollable Urge",
        "Mongoloid",
        "Smart Patrol",
        "Mr. DNA",
        "Sloppy",
        "Come Back Jonee",
        "Clockout",
    ]


def test_v248_setlist_parser_accepts_numbered_tracks_after_sample_rate_without_tracks_header(tmp_path):
    import tlo_tag_lib as T

    setlist = tmp_path / "devo rcmh 1981-10-31.txt"
    setlist.write_text(
        """devo

radio city music hall
new york, ny

october 31, 1981

lineage:
master audience cassette

sample rate:
24bit/48kHz

processing/conversion:
wav>adobe audition (fades, normalize)>flac frontend (level 8)

01. Going Under
02. Through Being Cool
03. Jerkin' Back 'N' Forth
04. Soft Things
05. Pity You
06. Girl U Want
07. Planet Earth
08. Whip It
09. Race Of Doom
10. Super Thing
11. Uncontrollable Urge
12. Mongoloid
13. Jocko Homo
14. Smart Patrol > Mr. DNA
15. Gut Feeling
16. Gates Of Steel
17. Beautiful World
18. Workin' In A Coal Mine
19. DEVO Corporate Anthem
""",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))
    assert len(tracks) == 19
    assert tracks[0]["title"] == "Going Under"
    assert tracks[13]["title"] == "Smart Patrol > Mr. DNA"
    assert tracks[-1]["title"] == "DEVO Corporate Anthem"

# --------------------------------------------------------------------------- #
# v249 - Broader tagging title recovery from non-standard setlists and filenames
# --------------------------------------------------------------------------- #

def test_v249_parse_m3u_extinf_tracks_without_duplicate_file_rows(tmp_path):
    setlist = tmp_path / "playlist.m3u"
    setlist.write_text(
        "#EXTM3U\n"
        "#EXTINF:139,[01] Intro\n"
        "CD1\\[01] Intro.flac\n"
        "#EXTINF:211,[02] It's So Easy\n"
        "CD1\\[02] It's So Easy.flac\n"
        "#EXTINF:577,[01] Coma\n"
        "CD2\\[01] Coma.flac\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == ["Intro", "It's So Easy", "Coma"]


def test_v249_parse_plain_unnumbered_song_block_with_colons(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "DEEP PURPLE\n1996-11-23\n\nSETLIST:\n\n"
        "Hush\n"
        "Vavoom: Ted the Mechanic\n"
        "Cascades: I'm Not Your Lover\n"
        "Highway Star\n\n"
        "Lineage: DAT > FLAC\n",
        encoding="utf-8",
    )
    tracks, source = T.parse_unstructured_unnumbered_tracks(str(setlist), 4)
    assert source == "unnumbered-lines"
    assert [track["title"] for track in tracks] == [
        "Hush",
        "Vavoom: Ted the Mechanic",
        "Cascades: I'm Not Your Lover",
        "Highway Star",
    ]


def test_v249_fill_blank_numbered_rows_and_stop_before_hash_tables(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "The Setlist:\n"
        "01. Prove My Love\n"
        "02. Breakfast at Volo's\n"
        "03.\n"
        "04. -\n"
        "05. Getchall '20\n\n"
        "All Checksums and Such Created and Verified\n"
        "59a84ffc8c1922cf81d498448a9a5f7e  [shntool]  01. Prove My Love.flac\n"
        "     3:41.20       39032096 B   -b-   --   ---xx   flac  0.5359  01. Prove My Love.flac\n",
        encoding="utf-8",
    )
    audio = []
    for idx in range(1, 6):
        path = tmp_path / f"track{idx:02d}.flac"
        path.write_bytes(b"fake")
        audio.append(str(path))
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Deep Banana", "setlist_file": str(setlist), "music_files": audio}
    config = SimpleNamespace(etree_lookup=False, tag_during_inventory=True)
    tracks, source, problem = T._select_tracks_for_tagging(config, group, audio, emit=lambda _text: None, fallback_to_filenames_on_track_problem=True, record=None)
    assert source == "setlist"
    assert problem is None
    assert [track["title"] for track in tracks] == ["Prove My Love", "Breakfast at Volo's", "Unknown", "Unknown", "Getchall '20"]


def test_v249_no_setlist_uses_filename_titles_before_empty_title_tags(tmp_path, monkeypatch):
    audio = []
    for name in [
        "101-Introduction 11-26.flac",
        "102-Got To Get Better In A Little While 11-26.flac",
        "201-Why Does Love Got To Be So Sad 11-26.flac",
    ]:
        path = tmp_path / name
        path.write_bytes(b"fake")
        audio.append(str(path))
    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda _path: "")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "No Setlist", "setlist_file": "", "music_files": audio}
    config = SimpleNamespace(etree_lookup=False, tag_during_inventory=True)
    tracks, source, problem = T._select_tracks_for_tagging(config, group, audio, emit=lambda _text: None, fallback_to_filenames_on_track_problem=True, record=None)
    assert source == "filenames"
    assert problem is None
    assert [track["title"] for track in tracks] == [
        "Introduction",
        "Got To Get Better In A Little While",
        "Why Does Love Got To Be So Sad",
    ]


# --------------------------------------------------------------------------- #
# v250 - eTreeDB same-date performance best-fit and marker-only generated setlists
# --------------------------------------------------------------------------- #

def test_etreedb_venue_location_multi_match_uses_setlist_text_best_fit(tmp_path, monkeypatch):
    setlist = tmp_path / "info.txt"
    setlist.write_text("Artist\n1981-10-31\nRadio City Music Hall\nNew York, NY\n\n01. Song\n", encoding="utf-8")
    wrong = SimpleNamespace(performance_id=1, venue="The Ritz", city="New York", state="NY", title="Late Show")
    right = SimpleNamespace(performance_id=2, venue="Radio City Music Hall", city="New York", state="NY", title="Halloween")
    monkeypatch.setattr(P, "lookup_venue_and_location", lambda *args, **kwargs: [wrong, right])
    record = P.ShowMetadata(
        group_number=1,
        main_dir_name="Artist 1981-10-31",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        setlist_files=[str(setlist)],
        music_file_count=1,
        artist="Artist",
        date="1981-10-31",
    )
    observations = []
    assert P._apply_etree_lookup_to_record(SimpleNamespace(etree_lookup=True, debug=False), record, {}, observations) is True
    assert record.venue == "Radio City Music Hall"
    assert record.city == "New York"
    assert record.region == "NY"
    assert any("selected best setlist-text fit performance id 2" in line for line in observations)


def test_tagger_etreedb_multiple_performances_uses_exact_track_count(monkeypatch, tmp_path):
    wrong = SimpleNamespace(performance_id=10)
    right = SimpleNamespace(performance_id=20)
    monkeypatch.setattr(
        T,
        "lookup_setlists_by_performance",
        lambda *args, **kwargs: [
            (wrong, ["01 Wrong One\n02 Wrong Two\n03 Extra"]),
            (right, ["01 Correct One\n02 Correct Two"]),
        ],
    )
    messages = []
    config = T.Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, etree_lookup=True)
    record = SimpleNamespace(artist="Artist", date="1981-10-31")
    tracks = T.tracks_from_etreedb_setlist(config, record, 2, str(tmp_path), emit=messages.append)
    assert [track["title"] for track in tracks] == ["Correct One", "Correct Two"]
    assert any("selected performance id 20" in line for line in messages)

# --------------------------------------------------------------------------- #
# v251 - Tag title recovery from damaged rows, samples, and bad files
# --------------------------------------------------------------------------- #

def test_v251_st_song_titles_are_not_rejected_as_ordinals(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "Setlist:\n"
        "10.Trane >\n"
        "11.St. Stephen >\n"
        "12.Eternity's Breath >\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == ["Trane >", "St. Stephen >", "Eternity's Breath >"]


def test_v251_missing_numbered_row_uses_audio_filename_title(tmp_path):
    setlist = tmp_path / "1973.11.03.txt"
    setlist.write_text(
        "01. Intro\n"
        "02. Highway Star\n"
        "03. Smoke On The Water\n"
        "04. Strange Kind Of Woman\n"
        "05. Mary Long\n"
        "0+. Keybords solo - Lazy\n"
        "07. Drums Solo ~ The Mule\n"
        "08. Space Truckin'\n"
        "09. Black Night\n",
        encoding="utf-8",
    )
    audio = []
    for name in [
        "01 Intro.flac",
        "02 Highway Star.flac",
        "03 Smoke On The Water.flac",
        "04 Strange Kind Of Woman.flac",
        "05 Mary Long.flac",
        "06 Keyboards Solo ~ Lazy.flac",
        "07 Drums Solo ~ The Mule.flac",
        "08 Space Truckin'.flac",
        "09 Black Night.flac",
    ]:
        path = tmp_path / name
        path.write_bytes(b"fake")
        audio.append(str(path))
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Show", "setlist_file": str(setlist), "music_files": audio}
    config = SimpleNamespace(etree_lookup=False, tag_during_inventory=True)
    tracks, source, problem = T._select_tracks_for_tagging(config, group, audio, emit=lambda _text: None, fallback_to_filenames_on_track_problem=True, record=None)
    assert problem is None
    assert source == "setlist"
    assert [track["title"] for track in tracks][5] == "Keyboards Solo ~ Lazy"
    assert len(tracks) == 9


def test_v251_sample_audio_files_are_skipped_before_track_count_comparison(tmp_path):
    audio = []
    for name in ["show t01.flac", "show t02.flac", "show sample.mp3"]:
        path = tmp_path / name
        path.write_bytes(b"fake")
        audio.append(str(path))
    group = {"main_dir_path": str(tmp_path), "music_files": audio}
    messages = []
    config = SimpleNamespace(convert_shn=False)
    prepared, errors = T._prepare_audio_files_for_tagging(config, group, audio, emit=messages.append)
    assert errors == 0
    assert [Path(path).name for path in prepared] == ["show t01.flac", "show t02.flac"]
    assert any("SKIP SAMPLE AUDIO" in message for message in messages)


def test_v251_bad_audio_file_write_is_not_fatal_to_remaining_tracks(tmp_path, monkeypatch):
    audio = []
    for idx in range(1, 4):
        path = tmp_path / f"{idx:02d} Song {idx}.flac"
        path.write_bytes(b"fake")
        audio.append(str(path))
    setlist = tmp_path / "info.txt"
    setlist.write_text("01. Song 1\n02. Song 2\n03. Song 3\n", encoding="utf-8")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Show", "setlist_file": str(setlist), "music_files": audio}
    record = SimpleNamespace(artist="Artist", show_name="Artist 2000-01-01 Venue City ST", date="2000-01-01", venue="Venue", city="City", region="ST", country="")
    calls = []
    def fake_write(path_name, artist, album, track_number, title, total_tracks=0):
        calls.append((Path(path_name).name, title))
        if Path(path_name).name.startswith("02"):
            raise RuntimeError("file said 4 bytes, read 0 bytes")
    monkeypatch.setattr(T, "write_audio_tags", fake_write)
    stats = T.tag_group_with_record(SimpleNamespace(etree_lookup=False, convert_shn=False, debug=False), group, record, emit=lambda _text: None)
    assert stats["tagged"] == 2
    assert stats["errors"] == 1
    assert [item[0] for item in calls] == ["01 Song 1.flac", "02 Song 2.flac", "03 Song 3.flac"]

# --------------------------------------------------------------------------- #
# v253 - setlist.fm cached setlist titles from the venue/location API response
# --------------------------------------------------------------------------- #

def test_v253_setlistfm_result_extracts_set_titles_from_search_payload():
    import tlo_setlistfm_lookup as S

    payload = {
        "artist": {"name": "Devo"},
        "eventDate": "31-10-1981",
        "url": "https://www.setlist.fm/setlist/devo/example.html",
        "venue": {
            "name": "Radio City Music Hall",
            "city": {
                "name": "New York",
                "state": "New York",
                "stateCode": "NY",
                "country": {"name": "United States", "code": "US"},
            },
        },
        "sets": {
            "set": [
                {"song": [{"name": "Going Under"}, {"name": "Through Being Cool"}]},
                {"encore": 1, "song": [{"name": "Whip It"}]},
            ]
        },
    }
    result = S.parse_result(payload)
    assert result.venue == "Radio City Music Hall"
    assert result.location == "New York NY"
    assert result.setlists_in_order == ["01 Going Under\n02 Through Being Cool\n03 Whip It"]


def test_v253_setlistfm_lookup_stores_cached_setlists_without_second_request(monkeypatch, tmp_path):
    import tlo_setlistfm_lookup as S

    result = S.SetlistFMResult(
        artist="Devo",
        event_date="31-10-1981",
        venue="Radio City Music Hall",
        location="New York NY",
        city="New York",
        state="New York",
        state_code="NY",
        country="United States",
        country_code="US",
        setlist_url="https://www.setlist.fm/setlist/devo/example.html",
        venue_url="",
        setlists=("01 Going Under\n02 Through Being Cool",),
    )
    calls = {"count": 0}
    def fake_lookup(*args, **kwargs):
        calls["count"] += 1
        return [result]
    monkeypatch.setattr(P, "lookup_setlistfm_venue_and_location", fake_lookup)
    record = P.ShowMetadata(
        group_number=1,
        main_dir_name="Devo 1981-10-31",
        main_dir_path=str(tmp_path),
        setlist_file="",
        music_file_count=2,
        artist="Devo",
        date="1981-10-31",
    )
    observations = []
    assert P._apply_setlistfm_lookup_to_record(SimpleNamespace(setlistfm_lookup=True, debug=False), record, {}, observations) is True
    assert calls["count"] == 1
    assert record.venue == "Radio City Music Hall"
    assert record.setlistfm_setlist_candidates[0]["setlists"] == ["01 Going Under\n02 Through Being Cool"]
    assert any("cached setlist text in same API response" in line for line in observations)


def test_v253_tagger_uses_cached_setlistfm_exact_track_count(tmp_path):
    audio1 = tmp_path / "01 Unknown.flac"
    audio2 = tmp_path / "02 Unknown.flac"
    audio1.write_bytes(b"not real audio; write_audio_tags is patched")
    audio2.write_bytes(b"not real audio; write_audio_tags is patched")
    record = SimpleNamespace(
        artist="Devo",
        date="1981-10-31",
        setlistfm_setlist_candidates=[
            {"url": "wrong", "setlists": ["01 Wrong\n02 Wrong\n03 Extra"]},
            {"url": "right", "setlists": ["01 Going Under\n02 Through Being Cool"]},
        ],
    )
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Cached", "setlist_file": "", "music_files": [str(audio1), str(audio2)]}
    messages = []
    tracks, source, problem = T._select_tracks_for_tagging(
        SimpleNamespace(etree_lookup=False, tag_during_inventory=True),
        group,
        [str(audio1), str(audio2)],
        emit=messages.append,
        fallback_to_filenames_on_track_problem=True,
        record=record,
    )
    assert problem is None
    assert source == "setlist.fm"
    assert [track["title"] for track in tracks] == ["Going Under", "Through Being Cool"]
    assert any("using cached setlist.fm" in line for line in messages)


# --------------------------------------------------------------------------- #
# v254 - no-space comma-separated setlist lines
# --------------------------------------------------------------------------- #

def test_v254_comma_items_without_spaces_and_with_footnote_marker_match_audio_count(tmp_path):
    line = "Who Are You*,How Fine Is That,Freedom,Los Los,The Answer,The Bridge,Because of Her Beauty"
    setlist = tmp_path / "info.txt"
    setlist.write_text(line + "\n", encoding="utf-8")

    tracks, source = T.parse_unnumbered_comma_tracks(str(setlist), 7)

    assert source == "comma-items"
    assert [track["title"] for track in tracks] == [
        "Who Are You",
        "How Fine Is That",
        "Freedom",
        "Los Los",
        "The Answer",
        "The Bridge",
        "Because of Her Beauty",
    ]


# --------------------------------------------------------------------------- #
# v255 - mixed-case comma items and unnumbered CD/Set title blocks
# --------------------------------------------------------------------------- #

def test_v255_comma_items_accept_mixed_case_without_spaces(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text("first song,Second Song,THIRD Song,Fourth,FiFtH Tune,Sixth Number\n", encoding="utf-8")

    tracks, source = T.parse_unnumbered_comma_tracks(str(setlist), 6)

    assert source == "comma-items"
    assert [track["title"] for track in tracks] == [
        "first song",
        "Second Song",
        "THIRD Song",
        "Fourth",
        "FiFtH Tune",
        "Sixth Number",
    ]


def test_v255_unnumbered_section_tracks_accept_punctuated_cd_headers(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "Derek & The Dominos\n\n"
        " -- CD 01 -- \n"
        "Why Does Love Got To Be So Sad\n"
        "Got To Get Better In A Little While\n\n"
        " – Disc Two – \n"
        "Tell The Truth\n"
        "Let It Rain\n",
        encoding="utf-8",
    )

    tracks, source = T.parse_unnumbered_section_tracks(str(setlist), 4)

    assert source == "unnumbered-sections"
    assert [track["title"] for track in tracks] == [
        "Why Does Love Got To Be So Sad",
        "Got To Get Better In A Little While",
        "Tell The Truth",
        "Let It Rain",
    ]


def test_v255_unstructured_short_title_blocks_can_be_combined(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "Artist Name\n\n"
        "Opening Song\n"
        "Second Tune\n\n"
        "Third Number\n"
        "Closing Jam\n\n"
        "Lineage: cassette > wav > flac\n",
        encoding="utf-8",
    )

    tracks, source = T.parse_unstructured_unnumbered_tracks(str(setlist), 4)

    assert source == "unnumbered-line-blocks"
    assert [track["title"] for track in tracks] == [
        "Opening Song",
        "Second Tune",
        "Third Number",
        "Closing Jam",
    ]

# v256 - title recovery from new debug samples

def test_v256_unstructured_block_ignores_numbered_venue_and_keeps_numeric_song(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "Deep Purple - 1999-06-13 - Copenhagen, Denmark\n"
        "Venue: 5-øren Amager, Copenhagen, Denmark\n\n"
        "Sound quality: quite good if you can live with the chatters\n\n"
        "The Boys Are Back In Town\n"
        "Pictures Of Home\n"
        "vavoom: Ted The Mechanic\n"
        "Strange Kind Of Woman\n"
        "Bloodsucker\n"
        "69\n"
        "Woman From Tokyo\n"
        "Sometimes I Feel Like Screaming\n"
        "Watching The Sky\n"
        "Space Truckin'\n"
        "Cascades: I'm Not Your Lover\n"
        "Lazy\n"
        "Riff Raff\n"
        "Smoke On The Water\n"
        "Keyboard Solo\n"
        "Perfect Strangers\n"
        "Speed King\n"
        "Black Night\n"
        "Highway Star\n\n"
        "Lineage: audience master\n",
        encoding="utf-8",
    )
    assert T.parse_setlist_tracks(str(setlist)) == []
    tracks, source = T.parse_unstructured_unnumbered_tracks(str(setlist), 19)
    assert source == "unnumbered-lines"
    assert [track["title"] for track in tracks][0:6] == [
        "The Boys Are Back In Town",
        "Pictures Of Home",
        "vavoom: Ted The Mechanic",
        "Strange Kind Of Woman",
        "Bloodsucker",
        "69",
    ]
    assert tracks[-1]["title"] == "Highway Star"


def test_v256_embedded_disc_track_tokens_sort_by_disc_then_track(tmp_path):
    files = []
    for name in [
        "kdtu2002-12-30d1t01.flac",
        "kdtu2002-12-30d2t01.flac",
        "kdtu2002-12-30d1t02.flac",
        "decemberists2004-01-23_sbd_d2Track01.flac",
        "decemberists2004-01-23_sbd_d1Track15.flac",
    ]:
        path = tmp_path / name
        path.write_bytes(b"x")
        files.append(str(path))
    ordered = [Path(path).name for path in sorted(files, key=T._audio_track_order)]
    assert ordered == [
        "kdtu2002-12-30d1t01.flac",
        "kdtu2002-12-30d1t02.flac",
        "decemberists2004-01-23_sbd_d1Track15.flac",
        "decemberists2004-01-23_sbd_d2Track01.flac",
        "kdtu2002-12-30d2t01.flac",
    ]


def test_v256_unnumbered_blocks_allow_blank_separated_single_song_encore(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "Song One\nSong Two\nSong Three\n\nEncore Song\n\nLineage: DAT > FLAC\n",
        encoding="utf-8",
    )
    tracks, source = T.parse_unstructured_unnumbered_tracks(str(setlist), 4)
    assert source == "unnumbered-line-blocks"
    assert [track["title"] for track in tracks] == ["Song One", "Song Two", "Song Three", "Encore Song"]


def test_v256_title_tag_unknown_can_be_filled_from_local_comma_position():
    tracks = [
        {"original_number": 1, "normalized_number": 1, "title": "Unknown"},
        {"original_number": 2, "normalized_number": 2, "title": "Existing Tag"},
    ]
    candidates = [
        {"title": "Who Are You", "source_line": "Who Are You,Existing Tag"},
        {"title": "Existing Tag", "source_line": "Who Are You,Existing Tag"},
    ]
    filled = T._fill_unknown_title_tracks_from_position_candidate(tracks, candidates, "folder", emit=lambda _text: None)
    assert [track["title"] for track in filled] == ["Who Are You", "Existing Tag"]

# v257 - literal unknown/?? setlist placeholders are not tag failures

def test_v257_numbered_question_mark_placeholder_counts_as_supplied_unknown(tmp_path):
    setlist = tmp_path / "info.txt"
    setlist.write_text(
        "Set list\n"
        "01 Hungry Freaks Daddy\n"
        "02 Lonely Little Girl\n"
        "03 ??\n"
        "04 Wowie Zowie\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert len(tracks) == 4
    assert tracks[2]["title"] == "unknown"
    assert T._is_unknown_title_debug_track(tracks[2], "setlist") is False


def test_v257_grandmothers_question_mark_row_does_not_emit_unknown_debug(tmp_path):
    setlist = tmp_path / "notes-Grandmothers.txt"
    setlist.write_text(
        "The Grandmothers\nVictor's, San Diego, CA\nJuly 11, 2003\n\n"
        "Set list\n"
        "01 Hungry Freaks Daddy\n"
        "02 Lonely Little Girl\n"
        "03 Take Your Clothes Off When You Dance\n"
        "04 What's the Ugliest Part of Your Body\n"
        "05 20 Small Cigars\n"
        "06 Oh No\n"
        "07 Son of Orange County\n"
        "08 Trouble Coming Everyday\n"
        "09 Lamont's Lament\n"
        "10 Horta Babies\n"
        "11 Immaculate Deception\n"
        "12 Idiot Bastard Son\n"
        "13 Carolina Hardcore Ecstasy\n"
        "14 Eric Dolphy Memorial BBQ\n"
        "15 Peace For All\n"
        "16 How Could I Be Such a Fool\n"
        "17 ??\n"
        "18 I Ain't Got No Heart\n"
        "19 I'm Not Satisfied\n"
        "20 The Eternal Question\n"
        "21 Montana\n"
        "22 Village of the Sun\n"
        "23 Echidna's Arf\n"
        "24 Banter\n"
        "25 Mother People\n"
        "26 Banter\n"
        "27 Wowie Zowie\n\n"
        "Band\nDon Preston: Keyboards\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert len(tracks) == 27
    assert tracks[16]["title"] == "unknown"
    assert not any(T._is_unknown_title_debug_track(track, "setlist") for track in tracks)


# --------------------------------------------------------------------------- #
# v258 - debug/tag logs capture anomalies, not routine success rows
# --------------------------------------------------------------------------- #

def test_v258_etree_debug_does_not_dump_each_raw_performance(monkeypatch, capsys):
    from tlo_etree_lookup import PerformanceResult, lookup_venue_location_and_setlists
    import tlo_etree_lookup as E

    perf = PerformanceResult(
        artist_id=1,
        artist="Artist",
        performance_id=1,
        raw_date="07/15/83",
        normalized_date="1983-07-15",
        title="",
        venue="4th Avenue Tavern",
        city="Olympia",
        state="WA",
        year=1983,
        set1="Song One",
    )
    monkeypatch.setattr(E, "fetch_exact_artist_year_performances", lambda requested_artist, year, debug=False: [perf])
    results = lookup_venue_location_and_setlists("Artist", "1983-07-15", debug=True)
    captured = capsys.readouterr()
    assert results == [perf]
    assert "raw_date=" not in captured.err
    assert "4th Avenue Tavern" not in captured.err


def test_v258_successful_tag_writes_do_not_emit_per_file_progress(tmp_path, monkeypatch):
    setlist = tmp_path / "show.txt"
    setlist.write_text("01 Song One\n02 Song Two\n", encoding="utf-8")
    audio1 = tmp_path / "01 Song One.flac"
    audio2 = tmp_path / "02 Song Two.flac"
    audio1.write_bytes(b"x")
    audio2.write_bytes(b"x")
    group = {
        "show_name": "Artist 1977-05-08 Venue City ST",
        "main_dir_path": str(tmp_path),
        "setlist_file": str(setlist),
        "music_dirs": [str(tmp_path)],
        "music_files": [str(audio1), str(audio2)],
        "artist": "Artist",
        "date": "1977-05-08",
        "venue": "Venue",
        "location": "City ST",
        "album_name": "1977-05-08 Venue City ST",
    }
    from inventory_parser_lib import Config
    config = Config(debug=True, silent=True, TLOHome=str(tmp_path))
    fake_record = SimpleNamespace(artist="Artist", date="1977-05-08", venue="Venue", location="City ST", show_name="Artist 1977-05-08 Venue City ST")
    monkeypatch.setattr(T, "_extract_metadata_for_group", lambda *args, **kwargs: (fake_record, [], []))
    monkeypatch.setattr(T, "write_audio_tags", lambda *args, **kwargs: None)
    messages = []
    stats = T.process_tagging_group(config, group, object(), emit=messages.append)
    assert stats["tagged"] == 2
    joined = "\n".join(messages)
    assert "TAGGING:" not in joined
    assert "tagged 01:" not in joined
    assert "tagged 02:" not in joined
    assert "ERROR" not in joined

# --------------------------------------------------------------------------- #
# v259 - numbered song lists must prove they start at 0/1 and continue in order
# --------------------------------------------------------------------------- #

def test_v259_numbered_song_list_ignores_prose_number_before_set_header(tmp_path):
    setlist = tmp_path / "dinosaurs.txt"
    setlist.write_text(
        "Dinosaurs\n"
        "20 feet away,right side balcony,hat on rail\n\n"
        "set 1  cd1\n\n"
        "01) tuning [00:53]\n"
        "02) New York Town [06:21]\n"
        "03) I Can't Dance [05:14]\n"
        "04) The Dance/ [12:25] tape flip\n"
        "05) /The Dance [02:01]\n\n"
        "set 2  cd2\n\n"
        "01) Good Old Rock and Roll [03:15]\n"
        "02) I Got Love [04:59]\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == [
        "tuning",
        "New York Town",
        "I Can't Dance",
        "The Dance",
        "The Dance",
        "Good Old Rock and Roll",
        "I Got Love",
    ]


def test_v259_first_one_match_is_discarded_when_next_number_restarts_at_one(tmp_path):
    setlist = tmp_path / "false-first.txt"
    setlist.write_text(
        "1 This is a stray numbered note\n"
        "1 Real Opener\n"
        "2 Real Second Song\n"
        "3 Real Third Song\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == ["Real Opener", "Real Second Song", "Real Third Song"]


def test_v259_numbered_song_list_ignores_initial_greater_than_one_line(tmp_path):
    setlist = tmp_path / "greater-than-one.txt"
    setlist.write_text(
        "5-øren Copenhagen Denmark\n"
        "1 Song One\n"
        "2 Song Two\n"
        "3 Song Three\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == ["Song One", "Song Two", "Song Three"]

# v260 - mixed re-inventory/new search paths must not crash postprocess scope resolution

def test_v260_overwrite_path_scopes_ignores_new_and_skip_actions():
    import tlo_postprocess as PP
    from types import SimpleNamespace

    config = SimpleNamespace(
        inventory_path_actions=[
            {"volume": "BillC&D Pt3", "path": "/mnt/d/B-J/D/Dinosaurs", "action": "reinventory"},
            {"volume": "BillC&D Pt3", "path": "/mnt/d/B-J/D/Donovan", "action": "new"},
            {"volume": "BillC&D Pt3", "path": "/mnt/d/B-J/D/Ducks", "action": "skip"},
        ],
        inventory_volume_actions={"billc&d pt3": "new"},
    )

    scopes = PP._overwrite_path_scopes(config)
    assert len(scopes) == 1
    assert scopes[0]["path"] == "/mnt/d/B-J/D/Dinosaurs"


def test_v260_existing_rows_keep_new_non_overlapping_path_when_mixed_with_reinventory(tmp_path):
    from types import SimpleNamespace
    import tlo_postprocess as PP
    from tlo_bootlist_volume_policy import write_bootlist_rows

    home = str(tmp_path)
    write_bootlist_rows(home, [
        {"Show": "Old Dinosaurs", "Volume": "BillC&D Pt3", "Path": "/mnt/d/B-J/D/Dinosaurs/old"},
        {"Show": "Old Donovan", "Volume": "BillC&D Pt3", "Path": "/mnt/d/B-J/D/Donovan/old"},
    ])
    config = SimpleNamespace(
        TLOHome=home,
        inventory_path_actions=[
            {"volume": "BillC&D Pt3", "path": "/mnt/d/B-J/D/Dinosaurs", "action": "reinventory"},
            {"volume": "BillC&D Pt3", "path": "/mnt/d/B-J/D/Donovan", "action": "new"},
        ],
        inventory_volume_actions={"billc&d pt3": "new"},
    )

    kept, replaced = PP._existing_rows_for_postprocess(config)
    assert [row["Show"] for row in kept] == ["Old Donovan"]
    assert [row["Show"] for row in replaced] == ["Old Dinosaurs"]

# v261 - Windows drive paths with comma-bearing artist folders must keep full root

def test_v261_windows_path_with_comma_artist_folder_normalizes_to_full_wsl_path():
    import inventory_list_lib as IL

    raw = r"D:\B-J\D\Dudek, Les"
    assert IL._normalize_input_path(raw) == "/mnt/d/B-J/D/Dudek, Les"


def test_v261_wsl_mount_prefix_is_not_metadata_path_part():
    import tlo_phase23_v2 as P

    parts = P._path_parts("/mnt/d/B-J/D/Dudek, Les/1978-01-02 Venue City ST")
    assert parts[:3] == ["B-J", "D", "Dudek, Les"]
    assert "mnt" not in parts
    assert parts[0] != "d"


def test_v261_candidate_parts_preserve_dudek_les_not_mount_root():
    import tlo_phase23_v2 as P

    candidates = P._candidate_path_parts("/mnt/d/B-J/D/Dudek, Les")
    names = [name for name, _path in candidates]
    assert names[0] == "Dudek, Les"
    assert "mnt" not in names
    assert "/mnt/d" not in [path for _name, path in candidates]

# v262 - Strip list-position and t/track prefixes from song-title tags

def test_v262_strip_of_total_prefix_from_setlist_and_title_tag(tmp_path):
    setlist = tmp_path / "of-total.txt"
    setlist.write_text(
        "1 of 28 Opening Song\n"
        "2 of 28 Second Song\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == ["Opening Song", "Second Song"]
    assert T._usable_title_from_audio_title_tag("4 of 28 Song Title") == ("Song Title", True)


def test_v262_strip_t_or_track_prefix_from_setlist_rows(tmp_path):
    setlist = tmp_path / "t-prefix.txt"
    setlist.write_text(
        "t01 - First Song\n"
        "track02 - Second Song\n"
        "trk03: Third Song\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == ["First Song", "Second Song", "Third Song"]

# v263 - Tag Copy and Delete Path moves/copies processed inventory folders

def test_v263_option_registry_adds_tag_copy_and_delete_path(tmp_path):
    from tlo_options import OPTIONS_BY_FIELD

    option = OPTIONS_BY_FIELD["tag_copy_and_delete_path"]
    assert option.flag == "--tag-copy-and-delete"
    assert option.gui_label == "Tag Copy/Delete Original\n-- Destination Path"

    values = {"tag_copy_and_delete_path": str(tmp_path)}
    IPL._validate_tag_copy_values(values)
    assert values["tag_copy_and_delete_path"] == os.path.normpath(str(tmp_path))

    with pytest.raises(ValueError):
        IPL._validate_tag_copy_values({"tag_copy_and_delete_path": "relative/path"})


def test_v263_prepare_inventory_copy_delete_moves_same_partition_without_mutating_inventory_record(tmp_path):
    source = tmp_path / "Artist 1970-01-01 Venue City ST"
    source.mkdir()
    (source / "01 Song.flac").write_bytes(b"abc")
    destination = tmp_path / "processed"
    destination.mkdir()
    record = SimpleNamespace(
        main_dir_path=str(source),
        main_dir_name=source.name,
        setlist_file="",
        music_dirs=[str(source)],
        setlist_files=[],
    )
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(source / "01 Song.flac")],
        "setlist_files": [],
        "txt_files": [],
    }
    config = IPL.Config(debug=False, silent=True, TLOHome=str(tmp_path), tag_copy_and_delete_path=str(destination))
    messages = []

    moved_group, moved_record = T.prepare_inventory_copy_delete_target(config, group, record, emit=messages.append)

    assert not source.exists()
    moved_root = destination / source.name
    assert moved_root.is_dir()
    assert (moved_root / "01 Song.flac").read_bytes() == b"abc"
    assert record.main_dir_path == str(source)
    assert group["main_dir_path"] == str(source)
    assert moved_record.main_dir_path == str(moved_root)
    assert moved_group["music_files"] == [str(moved_root / "01 Song.flac")]
    assert any(message.startswith("TAG_COPY_DELETE_MOVE:") for message in messages)


def test_v263_prepare_inventory_copy_delete_copy_verifies_sizes_and_deletes_original(tmp_path, monkeypatch):
    source = tmp_path / "Cross Partition Show"
    source.mkdir()
    (source / "01 Song.flac").write_bytes(b"abc")
    (source / "02 Song.flac").write_bytes(b"defgh")
    destination = tmp_path / "processed"
    destination.mkdir()
    record = SimpleNamespace(
        main_dir_path=str(source),
        main_dir_name=source.name,
        setlist_file="",
        music_dirs=[str(source)],
        setlist_files=[],
    )
    group = {"main_dir_path": str(source), "main_dir_name": source.name, "music_dirs": [str(source)], "music_files": [str(source / "01 Song.flac"), str(source / "02 Song.flac")], "setlist_files": [], "txt_files": []}
    config = IPL.Config(debug=False, silent=True, TLOHome=str(tmp_path), tag_copy_and_delete_path=str(destination))
    monkeypatch.setattr(T, "_paths_on_same_filesystem", lambda _a, _b: False)
    messages = []

    copied_group, copied_record = T.prepare_inventory_copy_delete_target(config, group, record, emit=messages.append)

    copied_root = destination / source.name
    assert copied_root.is_dir()
    assert not source.exists()
    assert (copied_root / "01 Song.flac").stat().st_size == 3
    assert (copied_root / "02 Song.flac").stat().st_size == 5
    assert record.main_dir_path == str(source)
    assert copied_record.main_dir_path == str(copied_root)
    assert copied_group["music_files"] == [str(copied_root / "01 Song.flac"), str(copied_root / "02 Song.flac")]
    assert any(message.startswith("TAG_COPY_DELETE_COPY:") for message in messages)


# v264 - Tag Copy and Delete Path satisfies Rename Compliantly validation

def test_v264_rename_compliantly_allows_tag_copy_and_delete_path(tmp_path):
    values = {
        "rename_compliantly": True,
        "tag_during_inventory": False,
        "tag_copy_during_inventory": False,
        "tag_copy_and_delete_path": str(tmp_path),
    }
    IPL._validate_tag_copy_values(values)
    assert values["tag_copy_and_delete_path"] == os.path.normpath(str(tmp_path))


def test_v264_rename_compliantly_alert_requirement_is_superseded_by_v303():
    from pathlib import Path

    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    assert "either Tag in Place, Tag Copy, or Tag Copy/Delete Original must be available" not in source
    assert "_show_rename_requires_tag_mode_alert" not in source


# v265 - Unidentified shows must remain untouched by tag/copy/delete/rename

def test_v265_inventory_leaves_unidentified_show_in_place_before_copy_delete_or_tag(tmp_path, monkeypatch):
    from tlo_models import ShowMetadata

    source = tmp_path / "mystery folder"
    source.mkdir()
    audio = source / "track01.flac"
    audio.write_bytes(b"fake")
    destination = tmp_path / "processed"
    destination.mkdir()
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "setlist_files": [],
        "txt_files": [],
    }
    record = ShowMetadata(
        group_number=1,
        main_dir_name=source.name,
        main_dir_path=str(source),
        setlist_file="",
        music_file_count=1,
        artist="",
        date="",
        show_name="",
        music_dirs=[str(source)],
        setlist_files=[],
    )

    class CaptureLogs:
        def __init__(self):
            self.tag_messages = []
            self.conflict_messages = []

        def tag(self, fmt, *args):
            self.tag_messages.append(fmt % args if args else fmt)

        def conflicts(self, fmt, *args):
            self.conflict_messages.append(fmt % args if args else fmt)

    logs = CaptureLogs()
    config = IPL.Config(
        debug=False,
        silent=True,
        TLOHome=str(tmp_path),
        current_search_path=str(source),
        tag_during_inventory=True,
        tag_copy_and_delete_path=str(destination),
        rename_compliantly=True,
    )
    config.logs = logs

    monkeypatch.setattr(P, "_build_groups_from_search_path", lambda _config, _path: [group])
    monkeypatch.setattr(P, "_log_group", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(P, "_log_show_metadata", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(P, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], ["unable to create show name"]))
    monkeypatch.setattr(T, "prepare_inventory_copy_delete_target", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("copy/delete should not run")))
    monkeypatch.setattr(T, "prepare_inventory_tagging_target", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("rename/tag target prep should not run")))
    monkeypatch.setattr(T, "tag_group_with_record", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("tagging should not run")))

    records = P.process_groups_for_search_path_v2(config, artist_matcher=None)

    assert records == [record]
    assert source.is_dir()
    assert audio.is_file()
    assert list(destination.iterdir()) == []
    assert record.main_dir_path == str(source)
    assert any("TAG_COPY_AND_DELETE_SKIP" in message for message in logs.tag_messages)
    assert any("TAG_SKIP" in message for message in logs.tag_messages)


def test_v265_standalone_tagger_does_not_rename_unidentified_group(tmp_path, monkeypatch):
    from tlo_models import ShowMetadata

    source = tmp_path / "bad unidentified name"
    source.mkdir()
    audio = source / "track01.flac"
    audio.write_bytes(b"fake")
    group = {"main_dir_path": str(source), "main_dir_name": source.name, "music_dirs": [str(source)], "music_files": [str(audio)], "setlist_files": [], "txt_files": []}
    record = ShowMetadata(group_number=1, main_dir_name=source.name, main_dir_path=str(source), setlist_file="", music_file_count=1, artist="", show_name="")
    config = IPL.Config(debug=False, silent=True, TLOHome=str(tmp_path), tag_during_inventory=True, rename_compliantly=True)
    messages = []

    monkeypatch.setattr(T, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], ["unable to create show name"]))
    monkeypatch.setattr(T, "prepare_inventory_tagging_target", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("rename should not run")))

    stats = T.process_tagging_group(config, group, artist_matcher=None, emit=messages.append)

    assert source.is_dir()
    assert not (tmp_path / "Unknown").exists()
    assert stats["skipped"] == 1
    assert any("unable to create show name" in message for message in messages)

# v266 - Tag Copy and Delete is a full tag mode and applies compliant destination names

def test_v266_copy_delete_uses_compliant_show_name_when_rename_enabled(tmp_path):
    source = tmp_path / "raw bad source folder"
    source.mkdir()
    (source / "01 Song.flac").write_bytes(b"abc")
    destination = tmp_path / "processed"
    destination.mkdir()
    record = SimpleNamespace(
        main_dir_path=str(source),
        main_dir_name=source.name,
        show_name="Artist 1970-01-01 Venue City ST",
        setlist_file="",
        music_dirs=[str(source)],
        setlist_files=[],
    )
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(source / "01 Song.flac")],
        "setlist_files": [],
        "txt_files": [],
    }
    config = IPL.Config(
        debug=False,
        silent=True,
        TLOHome=str(tmp_path),
        tag_copy_and_delete_path=str(destination),
        rename_compliantly=True,
    )
    messages = []

    moved_group, moved_record = T.prepare_inventory_copy_delete_target(config, group, record, emit=messages.append)

    compliant_root = destination / "Artist 1970-01-01 Venue City ST"
    assert not source.exists()
    assert compliant_root.is_dir()
    assert (compliant_root / "01 Song.flac").read_bytes() == b"abc"
    assert record.main_dir_path == str(source)
    assert group["main_dir_path"] == str(source)
    assert moved_record.main_dir_path == str(compliant_root)
    assert moved_group["music_files"] == [str(compliant_root / "01 Song.flac")]
    assert any(str(compliant_root) in message for message in messages)


def test_v266_inventory_copy_delete_tags_transferred_compliant_folder(tmp_path, monkeypatch):
    from tlo_models import ShowMetadata

    source = tmp_path / "raw folder name"
    source.mkdir()
    audio = source / "01 Song.flac"
    audio.write_bytes(b"abc")
    destination = tmp_path / "processed"
    destination.mkdir()
    compliant_name = "Artist 1970-01-01 Venue City ST"
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "setlist_files": [],
        "txt_files": [],
    }
    record = ShowMetadata(
        group_number=1,
        main_dir_name=source.name,
        main_dir_path=str(source),
        setlist_file="",
        music_file_count=1,
        artist="Artist",
        date="1970-01-01",
        venue="Venue",
        city="City",
        region="ST",
        location="City ST",
        show_name=compliant_name,
        music_dirs=[str(source)],
        setlist_files=[],
    )

    class CaptureLogs:
        def __init__(self):
            self.tag_messages = []
            self.conflict_messages = []

        def tag(self, fmt, *args):
            self.tag_messages.append(fmt % args if args else fmt)

        def conflicts(self, fmt, *args):
            self.conflict_messages.append(fmt % args if args else fmt)

    logs = CaptureLogs()
    config = IPL.Config(
        debug=False,
        silent=True,
        TLOHome=str(tmp_path),
        current_search_path=str(source),
        tag_copy_and_delete_path=str(destination),
        rename_compliantly=True,
    )
    config.logs = logs
    captured = {}

    monkeypatch.setattr(P, "_build_groups_from_search_path", lambda _config, _path: [group])
    monkeypatch.setattr(P, "_log_group", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(P, "_log_show_metadata", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(P, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], []))

    def fake_tag_group(config_arg, group_arg, record_arg, **kwargs):
        captured["group"] = group_arg
        captured["record"] = record_arg
        captured["kwargs"] = kwargs
        return {"groups": 1, "tagged": 1, "skipped": 0, "errors": 0}

    monkeypatch.setattr(T, "tag_group_with_record", fake_tag_group)

    records = P.process_groups_for_search_path_v2(config, artist_matcher=None)

    compliant_root = destination / compliant_name
    assert records[0].main_dir_path == str(compliant_root)
    assert record.main_dir_path == str(source)
    assert not source.exists()
    assert compliant_root.is_dir()
    assert captured["group"]["main_dir_path"] == str(compliant_root)
    assert captured["record"].main_dir_path == str(compliant_root)
    assert captured["kwargs"]["allow_unknown_metadata"] is True
    assert any("mode=copy-and-delete" in message for message in logs.tag_messages)
    assert any("TAG_COPY_DELETE_MOVE:" in message and str(compliant_root) in message for message in logs.tag_messages)


# v267 - remove noisy exact-artist eTreeDB debug lines
def test_v267_etree_exact_artist_debug_noise_removed():
    source = Path("tlo_etree_lookup.py").read_text(encoding="utf-8")
    assert "artist exact query" not in source
    assert "using exact artist" not in source



# v268 - normalize song-title tags to regular printable characters
def test_v268_tag_title_printable_normalization():
    assert T.normalize_tag_title_printable('Song\u00a0Title “A” — Part\u200bOne…\x00\ufffd') == 'Song Title "A" - PartOne...'
    assert T.normalize_tag_title_printable("Café ﬂight – isn't it?") == "Cafe flight - isn't it?"


def test_v268_write_audio_tags_normalizes_title_before_writer(monkeypatch, tmp_path):
    audio_path = tmp_path / 'track01.flac'
    audio_path.write_bytes(b'not real audio; writer is patched')
    captured = {}

    monkeypatch.setattr(T, '_is_taggable_audio_file', lambda path: True)

    def fake_easy_writer(path, artist, album, track_number, title):
        captured['title'] = title

    monkeypatch.setattr(T, '_write_easy_tags', fake_easy_writer)
    T.write_audio_tags(str(audio_path), 'Artist', 'Album', '01', 'Bad\u00a0Title’s — Finale\u200b\x00\ufffd')

    assert captured['title'] == "Bad Title's - Finale"


# v269 - TLO-written names and tags use standard ASCII
def test_v269_standard_ascii_text_transliterates_non_english_characters():
    from tlo_text_utils import standard_ascii_text
    assert standard_ascii_text("Mötley Crüe – Düsseldorf, São Paulo, Łódź…") == "Motley Crue - Dusseldorf, Sao Paulo, Lodz..."


def test_v269_show_name_metadata_is_ascii_normalized():
    from tlo_models import ShowMetadata
    rec = ShowMetadata(group_number=1, main_dir_name="", main_dir_path="", setlist_file="", music_file_count=0, artist="Mötley Crüe", date="1984-02-01", venue="Philipshalle", location="Düsseldorf Germany")
    rec.show_name = P._build_show_name(rec)
    P._normalize_record_ascii_for_output(rec)
    assert rec.show_name == "Motley Crue 1984-02-01 Philipshalle Dusseldorf Germany"


def test_v269_compliant_folder_names_are_ascii_normalized():
    assert T.safe_compliant_folder_name("Mötley Crüe 1984-02-01 Düsseldorf") == "Motley Crue 1984-02-01 Dusseldorf"


def test_v269_tag_titles_are_ascii_normalized():
    assert T.normalize_tag_title_printable("Beyoncé – Café München") == "Beyonce - Cafe Munchen"



# v271 - Foreign-language unknown artist tags are not usable metadata
def test_v271_noncompliant_foreign_unknown_artist_tags_are_blank():
    from tlo_models import ShowMetadata

    rec = ShowMetadata(
        group_number=1,
        main_dir_name="Dr John Super Jam Bonnaroo 2003",
        main_dir_path="/music/Dr John Super Jam Bonnaroo 2003",
        setlist_file="",
        music_file_count=1,
        flac_tag_samples=[{"artist": "Artiste inconnu", "albumartist": ""}],
        flac_tag_artist_values=["Artiste inconnu"],
        flac_tag_albumartist_values=[],
    )
    observations = []

    P._blank_unusable_artist_tags_for_noncompliant(rec, observations)

    assert rec.flac_tag_samples[0]["artist"] == ""
    assert rec.flac_tag_artist_values == []
    assert any("Artiste inconnu" in item for item in observations)


def test_v271_foreign_unknown_artist_tag_does_not_win_artist_resolution():
    from tlo_models import ShowMetadata

    rec = ShowMetadata(
        group_number=1,
        main_dir_name="Dr John Super Jam Bonnaroo 2003",
        main_dir_path="/music/Dr John Super Jam Bonnaroo 2003",
        setlist_file="",
        music_file_count=1,
        flac_tag_samples=[{"artist": "Artiste inconnu", "albumartist": ""}],
        flac_tag_artist_values=["Artiste inconnu"],
        flac_tag_albumartist_values=[],
    )
    observations = []
    evidence = {}
    conflicts = []

    P._blank_unusable_artist_tags_for_noncompliant(rec, observations)
    resolved = P._resolve_artist_from_tags(rec, None, evidence, conflicts, observations)

    assert resolved == ""
    assert "artist" not in evidence

# v270 - release hygiene and deterministic extreme Max Workers behavior

def test_v270_all_python_files_have_current_version_stamp():
    import re
    import tlo_version

    current_version = tlo_version.VERSION
    root = Path(__file__).resolve().parent
    for source_file in sorted(root.glob("*.py")):
        text = source_file.read_text(encoding="utf-8")
        literal = re.search(r"^__version__\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE)
        via_constant = re.search(r"^__version__\s*=\s*VERSION\b", text, re.MULTILINE)
        assert literal or via_constant, f"missing __version__ in {source_file.name}"
        if literal:
            allowed_versions = {current_version}
            if source_file.name == "build_tlo_release.py":
                allowed_versions.add(tlo_version.DISPLAY_VERSION)
            assert literal.group(1) in allowed_versions, source_file.name
        else:
            assert source_file.name == "tlo_version.py"


def test_v270_public_metadata_helper_aliases_remain_available():
    assert M.explicit_metadata_match("Venue: Fillmore West") == M._explicit_metadata_match("Venue: Fillmore West")
    assert M.is_setlist_metadata_scan_boundary("01 Opening Song") == M._is_setlist_metadata_scan_boundary("01 Opening Song")
    assert M.looks_like_sentence_prose_line("this was recorded on a rainy night in the city.") == M._looks_like_sentence_prose_line("this was recorded on a rainy night in the city.")


# v272 - standalone foreign-language unknown words are blank artist tags

def test_v272_standalone_foreign_unknown_artist_words_are_blankable():
    cases = [
        "sconosciuto",
        "Sconosciuta",
        "desconocido",
        "desconocida",
        "desconhecido",
        "desconhecida",
        "inconnu",
        "inconnue",
        "unbekannt",
        "onbekend",
        "ukjent",
    ]
    for value in cases:
        assert P._contains_blankable_noncompliant_artist_tag(value), value


def test_v272_standalone_sconosciuto_tag_does_not_win_artist_resolution():
    from tlo_models import ShowMetadata

    rec = ShowMetadata(
        group_number=1,
        main_dir_name="Example Artist 2001-02-03 Example Venue",
        main_dir_path="/music/Example Artist/Example Artist 2001-02-03 Example Venue",
        setlist_file="",
        music_file_count=1,
        flac_tag_samples=[{"artist": "sconosciuto", "albumartist": ""}],
        flac_tag_artist_values=["sconosciuto"],
        flac_tag_albumartist_values=[],
    )
    observations = []
    evidence = {}
    conflicts = []

    P._blank_unusable_artist_tags_for_noncompliant(rec, observations)
    resolved = P._resolve_artist_from_tags(rec, None, evidence, conflicts, observations)

    assert resolved == ""
    assert rec.flac_tag_artist_values == []
    assert any("sconosciuto" in item for item in observations)


def test_v273_standalone_ukjent_tag_does_not_win_artist_resolution():
    from tlo_models import ShowMetadata

    rec = ShowMetadata(
        group_number=1,
        main_dir_name="Norwegian Artist 2001-02-03 Example Venue",
        main_dir_path="/music/Norwegian Artist/Norwegian Artist 2001-02-03 Example Venue",
        setlist_file="",
        music_file_count=1,
        flac_tag_samples=[{"artist": "ukjent", "albumartist": ""}],
        flac_tag_artist_values=["ukjent"],
        flac_tag_albumartist_values=[],
    )
    observations = []
    evidence = {}
    conflicts = []

    P._blank_unusable_artist_tags_for_noncompliant(rec, observations)
    resolved = P._resolve_artist_from_tags(rec, None, evidence, conflicts, observations)

    assert resolved == ""
    assert rec.flac_tag_artist_values == []
    assert any("ukjent" in item for item in observations)

# v274 - setlist.fm is strictly an eTreeDB fallback, not a second online validator

def test_v274_setlistfm_is_not_queried_after_successful_etreedb(monkeypatch):
    from tlo_models import ShowMetadata

    record = ShowMetadata(
        group_number=1,
        main_dir_name="Artist 2001-02-03 Venue City ST",
        main_dir_path="/music/Artist 2001-02-03 Venue City ST",
        setlist_file="",
        music_file_count=1,
        artist="Artist",
        date="2001-02-03",
    )
    etree_result = SimpleNamespace(performance_id="123", venue="eTree Hall", city="Boston", state="MA")
    monkeypatch.setattr(P, "lookup_venue_and_location", lambda *args, **kwargs: [etree_result])
    monkeypatch.setattr(P, "lookup_setlistfm_venue_and_location", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("setlist.fm should not be queried after eTreeDB success")))

    config = SimpleNamespace(etree_lookup=True, setlistfm_lookup=True, debug=False)
    evidence = {}
    observations = []
    etree_key = P._online_lookup_key(record)
    etree_success = P._apply_etree_lookup_to_record(config, record, evidence, observations)
    assert etree_success is True

    P._apply_setlistfm_only_after_etree_fallback(config, record, evidence, observations, etree_success, etree_key)

    assert record.venue == "eTree Hall"
    assert record.location == "Boston, MA"
    assert not any("setlist.fm lookup" in item for item in observations)


def test_v274_setlistfm_fallback_retries_etreedb_when_setlist_metadata_supplies_new_key(monkeypatch):
    from tlo_models import ShowMetadata

    record = ShowMetadata(
        group_number=1,
        main_dir_name="Album folder",
        main_dir_path="/music/Album folder",
        setlist_file="",
        music_file_count=1,
        artist="Artist",
        date="2001-02-03",
    )
    calls = {"etree": 0}

    def fake_etree(config, record, evidence, observations):
        calls["etree"] += 1
        record.venue = "Retried eTree Hall"
        record.city = "Boston"
        record.region = "MA"
        record.location = "Boston MA"
        return True

    monkeypatch.setattr(P, "_apply_etree_lookup_to_record", fake_etree)
    monkeypatch.setattr(P, "_apply_setlistfm_lookup_to_record", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("setlist.fm should not run when the eTreeDB retry succeeds")))

    config = SimpleNamespace(etree_lookup=True, setlistfm_lookup=True, debug=False)
    evidence = {}
    observations = []

    etree_success, etree_key = P._apply_setlistfm_only_after_etree_fallback(config, record, evidence, observations, False, None)

    assert etree_success is True
    assert etree_key == P._online_lookup_key(record)
    assert calls["etree"] == 1
    assert record.venue == "Retried eTree Hall"

# --------------------------------------------------------------------------- #
# v275 - numbered placeholder rows and safer unnumbered prose fallback
# --------------------------------------------------------------------------- #

def test_v275_numbered_placeholder_rows_preserve_full_order(tmp_path):
    setlist = tmp_path / "Al_Dimeola_1987-11-18.txt"
    setlist.write_text(
        "The Al Di Meola Project\n"
        "11-18-1989\n"
        "Park West\n"
        "Chicago, IL\n"
        "WXRT FM radio\n\n"
        "Filler: Go London 1976\n"
        "        Songs #10-12\n\n"
        "Disc 1 (79:17)\n"
        "01 Bashine Demons         7:40\n"
        "02 Traces of a Tear ->    5:06\n"
        "03 Piano Solo             7:25\n"
        "04 Arabella               9:21\n"
        "05 Band Intro             2:25\n"
        "06 Smile from a Stranger  6:40\n"
        "07 ?//Tape Flip           1:18\n\n"
        "08 Song with a View       9:52\n"
        "09 Song to the Phorah king 13:03\n\n"
        "   Go London 1976\n"
        "10 ?                      8:40\n"
        "11 Dfferent Band Intro    0:50\n"
        "   W/many people\n"
        "12 ?//                    6:52\n\n"
        "Band:\n"
        "Al Di Meola - Guitar\n"
        "Notes: This is a FM WRXT live radio show.\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert len(tracks) == 12
    assert [track["normalized_number"] for track in tracks] == list(range(1, 13))
    assert [track["title"] for track in tracks][:6] == [
        "Bashine Demons",
        "Traces of a Tear ->",
        "Piano Solo",
        "Arabella",
        "Band Intro",
        "Smile from a Stranger",
    ]
    assert tracks[6]["title"] == "unknown"
    assert tracks[9]["title"] == "unknown"
    assert tracks[10]["title"] == "Dfferent Band Intro"
    assert tracks[11]["title"] == "unknown"


def test_v275_unstructured_fallback_does_not_combine_header_lineage_and_notes(tmp_path):
    setlist = tmp_path / "Al_Dimeola_1987-11-18.txt"
    setlist.write_text(
        "The Al Di Meola Project\n"
        "11-18-1989\n"
        "Park West\n"
        "Chicago, IL\n"
        "WXRT FM radio\n\n"
        "Filler: Go London 1976\n"
        "        Songs #10-12\n\n"
        "WXRT Radio Show recorded on a nak\n"
        "deck with a Maxell XLII90 tape.\n\n"
        "NAK -> MC -> RME DIGI Interface ->\n"
        "Samplitude 6.0 -> Flac16\n\n"
        "By Patrick H. 02/20/2007\n"
        "From pjh analog tape collection\n\n"
        "Notes: This is a FM WRXT live radio show.\n"
        "A solid performace by the band and it\n"
        "is a very good sounding recording.\n",
        encoding="utf-8",
    )

    tracks, source = T.parse_unstructured_unnumbered_tracks(str(setlist), 12)

    assert tracks == []
    assert source == ""


def test_v275_bare_encore_heading_is_not_an_unnumbered_title(tmp_path):
    setlist = tmp_path / "encore_heading.txt"
    setlist.write_text(
        "Song One\n"
        "Song Two\n\n"
        "Encore\n"
        "Encore Song\n\n"
        "Lineage: DAT > FLAC\n",
        encoding="utf-8",
    )

    tracks, source = T.parse_unstructured_unnumbered_tracks(str(setlist), 3)

    assert source == "unnumbered-line-blocks"
    assert [track["title"] for track in tracks] == ["Song One", "Song Two", "Encore Song"]


# --------------------------------------------------------------------------- #
# v276 - explicit encore separator variants in unnumbered title parsing
# --------------------------------------------------------------------------- #

def test_v276_bare_encore_separator_variants_are_not_unnumbered_titles(tmp_path):
    variants = ["Encore -", "Encore>", "Encore >", "Encore-"]
    for variant in variants:
        setlist = tmp_path / f"encore_{variants.index(variant)}.txt"
        setlist.write_text(
            "Song One\n"
            "Song Two\n\n"
            f"{variant}\n"
            "Encore Song\n\n"
            "Lineage: DAT > FLAC\n",
            encoding="utf-8",
        )

        tracks, source = T.parse_unstructured_unnumbered_tracks(str(setlist), 3)

        assert source == "unnumbered-line-blocks", variant
        assert [track["title"] for track in tracks] == ["Song One", "Song Two", "Encore Song"]


def test_v276_title_bearing_encore_arrow_or_dash_prefix_is_stripped(tmp_path):
    setlist = tmp_path / "encore_title_prefixes.txt"
    setlist.write_text(
        "Song One\n"
        "Encore > Song Two\n"
        "Encore - Song Three\n",
        encoding="utf-8",
    )

    tracks, source = T.parse_unstructured_unnumbered_tracks(str(setlist), 3)

    assert source == "unnumbered-lines"
    assert [track["title"] for track in tracks] == ["Song One", "Song Two", "Song Three"]


# --------------------------------------------------------------------------- #
# v277/v278 - volume-style sibling release-part aggregation
# --------------------------------------------------------------------------- #

def _build_test_groups_from_tree(tmp_path, root):
    from initial_dir_walk_lib import initial_dir_walk

    home = tmp_path / "home"
    config = SimpleNamespace(TLOHome=str(home), performance_mode="balanced", silent=True, compliant=False)
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(root), 1, log_token="V")
    initial_dir_walk(config, str(root))
    return P._build_groups_from_search_path(config, str(root))


def test_v278_same_base_volume_suffix_siblings_remain_separate_rows(tmp_path):
    root = tmp_path / "music"
    base = "Bill Dickens 1987-03-14 Great Venue NY NY"
    vol1 = root / f"{base} (Volume 1)"
    vol2 = root / f"{base} (Vol. 2)"
    vol1.mkdir(parents=True)
    vol2.mkdir(parents=True)
    (vol1 / "01 Song One.flac").write_bytes(b"audio")
    (vol2 / "02 Song Two.flac").write_bytes(b"audio")
    (vol1 / "info.txt").write_text("01 Song One\n", encoding="utf-8")
    (vol2 / "info.txt").write_text("02 Song Two\n", encoding="utf-8")

    groups = _build_test_groups_from_tree(tmp_path, root)

    assert len(groups) == 2
    assert sorted(group["main_dir_path"] for group in groups) == sorted([os.path.normpath(str(vol1)), os.path.normpath(str(vol2))])
    assert all(not group.get("aggregate_album_name") for group in groups)
    assert all(len(group["music_dirs"]) == 1 for group in groups)
    for group in groups:
        required, optional = P._collect_pattern_matches_for_group(group)
        matches = required or optional
        assert any(match["string1"] == "Bill Dickens" and match["date_norm"] == "1987-03-14" and match["string2"] == "Great Venue NY NY" for match in matches)




def test_v278_same_base_volume_rows_use_size_aware_setlist_alternates(tmp_path):
    import tlo_postprocess as POST

    home = tmp_path / "home"
    setlists_dir = home / "setlists"
    setlists_dir.mkdir(parents=True)
    base = "Bill Dickens 1987-03-14 Great Venue NY NY"
    src1 = tmp_path / "src1.txt"
    src2 = tmp_path / "src2.txt"
    src1.write_text("01 Song One\n", encoding="utf-8")
    src2.write_text("02 Song Two\nlonger second setlist\n", encoding="utf-8")
    records = [
        {
            "show_name": base,
            "artist": "Bill Dickens",
            "date": "1987-03-14",
            "venue": "Great Venue",
            "location": "NY NY",
            "main_dir_path": str(tmp_path / "music" / f"{base} (Volume 1)"),
            "volume_label": "VOL",
            "setlist_file": str(src1),
        },
        {
            "show_name": base,
            "artist": "Bill Dickens",
            "date": "1987-03-14",
            "venue": "Great Venue",
            "location": "NY NY",
            "main_dir_path": str(tmp_path / "music" / f"{base} (Volume 2)"),
            "volume_label": "VOL",
            "setlist_file": str(src2),
        },
    ]

    rows, unidentified = POST._build_bootlist_rows(records, str(setlists_dir), config=SimpleNamespace(silent=True, performance_mode="balanced"))

    expected_base = "BillDickens1987-03-14GreatVenueNYNY"
    assert unidentified == []
    assert [row["Setlist"] for row in rows] == [f"{expected_base}(Volume1).txt", f"{expected_base}(Volume2).txt"]
    assert [row["Path"] for row in rows] == [record["main_dir_path"] for record in records]


def test_v279_show_name_parenthetical_is_preserved_in_setlist_filename(tmp_path):
    import tlo_postprocess as POST

    home = tmp_path / "home"
    setlists_dir = home / "setlists"
    setlists_dir.mkdir(parents=True)
    src = tmp_path / "src.txt"
    src.write_text("01 Song One\n", encoding="utf-8")
    record = {
        "show_name": "Bill Dickens 1987-03-14 Great Venue NY NY (SBD)",
        "artist": "Bill Dickens",
        "date": "1987-03-14",
        "venue": "Great Venue",
        "location": "NY NY",
        "main_dir_path": str(tmp_path / "music" / "Bill Dickens 1987-03-14 Great Venue NY NY (SBD)"),
        "volume_label": "VOL",
        "setlist_file": str(src),
    }

    rows, unidentified = POST._build_bootlist_rows([record], str(setlists_dir), config=SimpleNamespace(silent=True, performance_mode="balanced"))

    assert unidentified == []
    assert rows[0]["Setlist"] == "BillDickens1987-03-14GreatVenueNYNY(SBD).txt"


def test_v279_parenthetical_from_main_dir_is_preserved_when_metadata_base_was_stripped(tmp_path):
    import tlo_postprocess as POST

    home = tmp_path / "home"
    setlists_dir = home / "setlists"
    setlists_dir.mkdir(parents=True)
    src = tmp_path / "src.txt"
    src.write_text("01 Song One\n", encoding="utf-8")
    record = {
        "show_name": "Bill Dickens 1987-03-14 Great Venue NY NY",
        "artist": "Bill Dickens",
        "date": "1987-03-14",
        "venue": "Great Venue",
        "location": "NY NY",
        "main_dir_path": str(tmp_path / "music" / "Bill Dickens 1987-03-14 Great Venue NY NY (FM)"),
        "volume_label": "VOL",
        "setlist_file": str(src),
    }

    rows, unidentified = POST._build_bootlist_rows([record], str(setlists_dir), config=SimpleNamespace(silent=True, performance_mode="balanced"))

    assert unidentified == []
    assert rows[0]["Setlist"] == "BillDickens1987-03-14GreatVenueNYNY(FM).txt"

def test_v277_different_base_volume_suffix_siblings_aggregate_under_parent(tmp_path):
    root = tmp_path / "music"
    collection = root / "Bob Dylan - Collection"
    vol1 = collection / "Early Days (Vol 1)"
    vol2 = collection / "Latter Days (v.2)"
    vol1.mkdir(parents=True)
    vol2.mkdir(parents=True)
    (vol1 / "01 Song One.flac").write_bytes(b"audio")
    (vol2 / "02 Song Two.flac").write_bytes(b"audio")
    parent_setlist = collection / "setlist.txt"
    parent_setlist.write_text("01 Song One\n02 Song Two\n", encoding="utf-8")

    groups = _build_test_groups_from_tree(tmp_path, root)

    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == os.path.normpath(str(collection))
    assert groups[0]["main_dir_name"] == "Bob Dylan - Collection"
    assert groups[0]["aggregate_album_name"] == "Bob Dylan - Collection"
    assert groups[0]["aggregate_release_base"] == ""
    assert groups[0]["setlist_file"] == os.path.normpath(str(parent_setlist))
    assert sorted(os.path.basename(path) for path in groups[0]["music_dirs"]) == ["Early Days (Vol 1)", "Latter Days (v.2)"]

# --------------------------------------------------------------------------- #
# v281 - per-search-path copy directives and startup capacity checks
# --------------------------------------------------------------------------- #

def test_v281_inventory_line_accepts_slam_and_copy_directives_any_order(tmp_path):
    import inventory_list_lib as IL

    dest = tmp_path / "copies"
    dest.mkdir()
    inv = tmp_path / "toBeInventoried.txt"
    inv.write_text(
        f"/mnt/e/music --$copy {dest} --$slam Bob Dylan\n"
        f"/mnt/f/music --$slam Miles Davis --$copy-delete {dest}\n",
        encoding="utf-8",
    )

    parsed = IL._parse_inventory_file(str(inv))

    assert parsed[0] == ("/mnt/e/music", "/mnt/e/music", "Bob Dylan", "", "copy", str(dest))
    assert parsed[1] == ("/mnt/f/music", "/mnt/f/music", "Miles Davis", "", "copy-delete", str(dest))


def test_v281_inventory_line_rejects_copy_and_copy_delete_together(tmp_path):
    import pytest
    import inventory_list_lib as IL

    dest = tmp_path / "dest"
    dest.mkdir()
    inv = tmp_path / "toBeInventoried.txt"
    inv.write_text(f"/mnt/e/music --$copy {dest} --$copy-delete {dest}\n", encoding="utf-8")

    with pytest.raises(ValueError, match="mutually exclusive"):
        IL._parse_inventory_file(str(inv))


def test_v281_copy_capacity_sums_sources_by_destination(tmp_path, monkeypatch):
    import pytest
    import inventory_list_lib as IL
    from types import SimpleNamespace

    source_one = tmp_path / "source1"
    source_two = tmp_path / "source2"
    destination = tmp_path / "destination"
    source_one.mkdir()
    source_two.mkdir()
    destination.mkdir()
    (source_one / "a.flac").write_bytes(b"a" * 700)
    (source_two / "b.flac").write_bytes(b"b" * 700)

    monkeypatch.setattr(IL.shutil, "disk_usage", lambda _path: SimpleNamespace(total=2000, used=1000, free=1000))
    config = SimpleNamespace(tag_copy_and_delete_path="", tag_copy_during_inventory=False, tag_copy_destination="")

    with pytest.raises(ValueError) as excinfo:
        IL._validate_copy_destination_capacity(
            config,
            [
                (str(source_one), "", "VOL", "key1", "copy", str(destination)),
                (str(source_two), "", "VOL", "key2", "copy", str(destination)),
            ],
        )

    message = str(excinfo.value)
    assert str(destination) in message
    assert str(source_one) in message
    assert str(source_two) in message
    assert "Additional space needed" in message


def test_v281_command_line_rejects_copy_and_copy_delete_together(monkeypatch, tmp_path):
    import pytest
    import inventory_parser_lib as IPL

    home = tmp_path / "home"
    home.mkdir()
    search = tmp_path / "music"
    search.mkdir()
    dest = tmp_path / "dest"
    dest.mkdir()
    monkeypatch.setenv("TLOHome", str(home))
    monkeypatch.setattr(
        IPL.sys,
        "argv",
        ["tlo-gi.py", "--search-path", str(search), "--$copy", str(dest), "--$copy-delete", str(dest)],
    )

    with pytest.raises(SystemExit):
        IPL.parse_command_line()

# --------------------------------------------------------------------------- #
# v282 - GUI recovers from startup capacity-check failures.
# --------------------------------------------------------------------------- #

def test_v282_gui_finish_clears_worker_before_refreshing_button_states():
    gui = _load_tlo_ggi_module()
    finish_source = inspect.getsource(gui.App._finish_inventory_thread)
    assert "self.full_inventory_active = False" in finish_source
    assert "self.worker = None" in finish_source
    assert finish_source.index("self.full_inventory_active = False") < finish_source.index("self.worker = None")
    assert finish_source.index("self.worker = None") < finish_source.index("self._update_main_action_states()")


def test_v282_gui_inventory_worker_catches_startup_errors_and_schedules_finish():
    gui = _load_tlo_ggi_module()
    start_source = inspect.getsource(gui.App._start)
    assert "except Exception as exc:" in start_source
    assert 'self.queue.put(f\"ERROR: {exc}\\n\")' in start_source
    assert "self.root.after(0, self._finish_inventory_thread)" in start_source


# --------------------------------------------------------------------------- #
# v283 - Copy-capacity sizing announces the preflight pause.
# --------------------------------------------------------------------------- #

def test_v283_copy_capacity_prints_note_before_size_walk(tmp_path, monkeypatch, capsys):
    import inventory_list_lib as IL
    from types import SimpleNamespace

    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    destination.mkdir()
    (source / "a.flac").write_bytes(b"a" * 10)

    monkeypatch.setattr(IL.shutil, "disk_usage", lambda _path: SimpleNamespace(total=100000, used=1000, free=99000))
    config = SimpleNamespace(tag_copy_and_delete_path="", tag_copy_during_inventory=False, tag_copy_destination="", silent=False)

    IL._validate_copy_destination_capacity(config, [(str(source), "", "VOL", "key", "copy", str(destination))])

    output = capsys.readouterr().out
    assert "Note: checking source folder sizes" in output
    assert "Copy destination capacity check passed" in output

# v284 - Tagger accepts CD/set-prefixed setlist row numbers and common track labels.

def test_v284_parse_cd_set_prefixed_numbered_tracks(tmp_path):
    setlist = tmp_path / "cd_prefixed_tracks.txt"
    setlist.write_text(
        "CD1 - first set - 51:34\n"
        "101 [0:26] intro\n"
        "102 [2:08] Mr. Eliminator >\n"
        "103 [1:46] Surf Beat >\n"
        "104 [1:58] Green Onions >\n"
        "105 [1:26] Firing Up >\n"
        "106 [1:52] Linda Lou >\n"
        "107 [1:55] Rumble\n"
        "\n"
        "CD2 - second set - 38:40\n"
        "201 [1:43] Taco Wagon\n"
        "202 [4:27] Eating Masa\n"
        "203 [1:16] Eight Til Midnight\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == [
        "intro",
        "Mr. Eliminator >",
        "Surf Beat >",
        "Green Onions >",
        "Firing Up >",
        "Linda Lou >",
        "Rumble",
        "Taco Wagon",
        "Eating Masa",
        "Eight Til Midnight",
    ]
    assert [track["normalized_number"] for track in tracks] == list(range(1, 11))
    assert [track["original_number"] for track in tracks[:2]] == [101, 102]
    assert [track["original_number"] for track in tracks[-3:]] == [201, 202, 203]


def test_v284_parse_track_word_and_disc_track_label_rows(tmp_path):
    setlist = tmp_path / "track_labels.txt"
    setlist.write_text(
        "track 1 First Song\n"
        "track 2 - Second Song\n"
        "d1t03 Third Song\n"
        "cd1t04 - Fourth Song\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [track["title"] for track in tracks] == ["First Song", "Second Song", "Third Song", "Fourth Song"]
    assert [track["normalized_number"] for track in tracks] == [1, 2, 3, 4]


# --------------------------------------------------------------------------- #
# v285 - Invalid FLAC tagging errors are concise full-path messages.
# --------------------------------------------------------------------------- #

def test_v285_invalid_flac_tag_error_uses_concise_full_path(tmp_path):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio = tmp_path / "Track08.flac"
    audio.write_bytes(b"not really a flac file")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Song One\n", encoding="utf-8")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=False)
    record = ShowMetadata(
        group_number=8,
        main_dir_name="Roger Daltrey 1985-12-08 Orpheum Theater Boston, MA",
        main_dir_path=str(tmp_path),
        setlist_file=str(setlist),
        music_file_count=1,
        artist="Roger Daltrey",
        date="1985-12-08",
        venue="Orpheum Theater",
        location="Boston MA",
        show_name="Roger Daltrey 1985-12-08 Orpheum Theater Boston MA",
    )
    group = {"main_dir_path": str(tmp_path), "main_dir_name": record.main_dir_name, "setlist_file": str(setlist), "music_files": [str(audio)]}
    messages = []

    stats = T.tag_group_with_record(
        config,
        group,
        record,
        emit=messages.append,
        allow_unknown_metadata=False,
        fallback_to_filenames_on_track_problem=False,
        metadata_problems=[],
        meta_log_entry="SHOW_NAME: Roger Daltrey 1985-12-08 Orpheum Theater Boston MA\nEND_SHOW_METADATA\n",
    )

    assert stats["errors"] == 1
    expected = f"ERROR_AUDIO_FILE: '{audio}' - Not a valid FLAC file"
    assert any(expected in str(message) for message in messages)
    assert not any(" | Track08.flac | " in str(message) for message in messages)


def test_v285_generic_tag_write_error_uses_concise_full_path(tmp_path):
    audio = tmp_path / "dickdale1995-05-10d1trk09.flac"
    audio.write_bytes(b"bad")
    line = T._format_tag_file_error_line(str(audio), "file said 4 bytes, read 0 bytes")
    assert line == f"ERROR_AUDIO_FILE: '{audio}' - file said 4 bytes, read 0 bytes"
    assert " | " not in line


# --------------------------------------------------------------------------- #
# v286 - Tag Copy/Delete Original inventories destination copies.
# --------------------------------------------------------------------------- #

def test_v286_copy_delete_existing_volume_policy_uses_destination_scope(tmp_path, monkeypatch):
    import inventory_list_lib as IL
    from types import SimpleNamespace

    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    source = tmp_path / "src" / "music"
    source.mkdir(parents=True)
    (source / "01.flac").write_bytes(b"abc")
    dest = tmp_path / "dest"
    dest.mkdir()
    (logs_dir / "groupsX.log").write_text(f"SEARCH_PATH: [DESTVOL] {dest}\nold group text\n", encoding="utf-8")
    monkeypatch.setattr(IL, "_volume_identity_for_physical_path", lambda path: ("DESTVOL", "destkey"))
    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        silent=True,
        tag_copy_and_delete_path=str(dest),
        tag_copy_during_inventory=False,
        tag_copy_destination="",
    )

    prepared = IL.apply_existing_volume_actions(config, [(str(source), "", "SRCVOL", "srckey")])

    assert prepared == [(str(source), "", "DESTVOL", "destkey", "X", "w", "copy-delete", str(dest), str(dest))]
    assert config.inventory_path_actions[0]["path"] == str(dest)
    assert config.inventory_path_actions[0]["source_path"] == str(source)


def test_v286_process_groups_returns_destination_record_for_copy_delete(tmp_path, monkeypatch):
    from tlo_models import ShowMetadata
    import inventory_parser_lib as IPL
    import tlo_phase23_v2 as P
    import tlo_tag_lib as T

    source = tmp_path / "raw folder"
    source.mkdir()
    audio = source / "01 Song.flac"
    audio.write_bytes(b"abc")
    destination = tmp_path / "processed"
    destination.mkdir()
    show_name = "Artist 1970-01-01 Venue City ST"
    group = {"main_dir_path": str(source), "main_dir_name": source.name, "music_dirs": [str(source)], "music_files": [str(audio)], "music_file_count": 1, "setlist_file": "", "setlist_files": [], "txt_files": []}
    record = ShowMetadata(group_number=1, main_dir_name=source.name, main_dir_path=str(source), setlist_file="", music_file_count=1, artist="Artist", date="1970-01-01", venue="Venue", city="City", region="ST", location="City ST", show_name=show_name, music_dirs=[str(source)], setlist_files=[])

    class Logs:
        def __init__(self):
            self.tag_messages = []
            self.conflict_messages = []
            self.group_messages = []
            self.meta_messages = []
            self.paths = type("Paths", (), {"complete_paths": str(tmp_path / "comp.log")})()
        def tag(self, fmt, *args): self.tag_messages.append(fmt % args if args else fmt)
        def conflicts(self, fmt, *args): self.conflict_messages.append(fmt % args if args else fmt)
        def groups(self, fmt, *args): self.group_messages.append(fmt % args if args else fmt)
        def show_metadata(self, fmt, *args): self.meta_messages.append(fmt % args if args else fmt)

    logs = Logs()
    (tmp_path / "comp.log").write_text(f"# completePathLog for search path: []\nSEARCH_PATH: []\n{audio}\n", encoding="utf-8")
    config = IPL.Config(debug=False, silent=True, TLOHome=str(tmp_path), current_search_path=str(source), tag_copy_and_delete_path=str(destination), rename_compliantly=True)
    config.logs = logs

    monkeypatch.setattr(P, "_build_groups_from_search_path", lambda _config, _path: [group])
    monkeypatch.setattr(P, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], []))
    monkeypatch.setattr(T, "tag_group_with_record", lambda *_args, **_kwargs: {"groups": 1, "tagged": 1, "skipped": 0, "errors": 0})

    records = P.process_groups_for_search_path_v2(config, artist_matcher=None)

    dest_root = destination / show_name
    assert records[0].main_dir_path == str(dest_root)
    assert not source.exists()
    assert dest_root.is_dir()
    assert any(str(dest_root) in line for line in logs.group_messages)
    assert any(str(dest_root) in line for line in logs.meta_messages)
    assert str(dest_root / "01 Song.flac") in (tmp_path / "comp.log").read_text(encoding="utf-8")

# --------------------------------------------------------------------------- #
# v287 - unnumbered Disc/Show section headings and Encore separators.
# --------------------------------------------------------------------------- #

def test_v287_parse_disc_show_unnumbered_section_and_skip_encore_separator(tmp_path):
    setlist = tmp_path / "rick_danko_richard_manuel_1985-12-13_late_show.txt"
    setlist.write_text(
        "Rick Danko and Richard Manuel\n"
        "Otooles Bar\n"
        "Scranton, Pa.\n"
        "December 13, 1985\n"
        "Late Show\n\n"
        "Source: *Soundboard>Sony D5M(TDK SA-X90 Master Cassette)\n"
        "Transfer: Nak CR5A>Lunatec V3(analog out)>722@24/96\n"
        "Editing: Adobe Audition 2.0 dither and resample 16Bit>Cdwav/tracking>flac16\n"
        "Taper: Tony Suraci\n"
        "Transfer and upload by Tony Suraci aka nak700\n\n"
        "Disc One/Late Show:\n"
        "Intro\n"
        "C. C. Rider\n"
        "My Love\n"
        "Whistle Stop\n"
        "Unfaithful Servant\n"
        "She Knows\n"
        "Honest I do\n"
        "King Harvest\n"
        "It Makes No Difference\n"
        "Banter\n"
        "Chest Fever\n"
        "Encore:\n"
        "Everynight and Everyday\n\n"
        "*Thanks Mike E. for knowing everyone in Scranton and getting me this\n"
        "SBD patch.\n\n"
        "Notes: This is the 16Bit version.\n",
        encoding="utf-8",
    )

    tracks, source = T.parse_unnumbered_section_tracks(str(setlist), 12)

    assert source == "unnumbered-sections"
    assert [track["title"] for track in tracks] == [
        "Intro",
        "C. C. Rider",
        "My Love",
        "Whistle Stop",
        "Unfaithful Servant",
        "She Knows",
        "Honest I do",
        "King Harvest",
        "It Makes No Difference",
        "Banter",
        "Chest Fever",
        "Everynight and Everyday",
    ]
    assert "Encore" not in [track["title"] for track in tracks]

# --------------------------------------------------------------------------- #
# v288 - Disc-track dash rows are parsed before unnumbered revision fallback.
# --------------------------------------------------------------------------- #

def test_v288_parse_disc_dash_track_rows_and_ignore_revision_notes(tmp_path):
    setlist = tmp_path / "md1982-05-30-info.txt"
    setlist.write_text(
        "Miles Davis\n"
        "1982-05-30 First Concert\n"
        "Kool Jazz Festival\n"
        "Kennedy Center\n"
        "Washington, D.C., USA\n\n"
        "1cdr, Mcas>cdr, 49:10\n"
        "- very good audience recording\n\n"
        "Recording Equipment: Nak300 microphones > Sony TCD5\n\n"
        "Miles Davis (tp, synth); Bill Evans (ss, ts, fl); Mike Stern (g); Marcus Miller (elb); Al Foster (d); Mino Cinelu (pc)\n\n"
        "First Concert [49:06]\n"
        "1-1 Back Seat Betty 8:29\n"
        "1-2 Ife 13:13\n"
        "1-3 Aida 15:02\n"
        "1-4 Jean Pierre [nc] 12:20 (end cut)\n\n"
        "Revision A\n"
        "- repaired 2 brief, left-channel drops out\n"
        "- gain noarmalized and tracked\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["original_number"] for track in tracks] == [101, 102, 103, 104]
    assert [track["normalized_number"] for track in tracks] == [1, 2, 3, 4]
    assert [track["title"] for track in tracks] == [
        "Back Seat Betty",
        "Ife",
        "Aida",
        "Jean Pierre [nc]",
    ]
    assert "Revision A" not in [track["title"] for track in tracks]


def test_v288_disc_dash_rows_can_continue_to_next_disc_without_heading(tmp_path):
    setlist = tmp_path / "disc_dash_no_second_heading.txt"
    setlist.write_text(
        "Tracks:\n"
        "1-1 First Song\n"
        "1-2 Second Song\n"
        "2-1 Third Song\n"
        "2-2 Fourth Song\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["original_number"] for track in tracks] == [101, 102, 201, 202]
    assert [track["normalized_number"] for track in tracks] == [1, 2, 3, 4]
    assert [track["title"] for track in tracks] == ["First Song", "Second Song", "Third Song", "Fourth Song"]

# --------------------------------------------------------------------------- #
# v289 - Safer broad setlist parsing and normalized tag file errors.
# --------------------------------------------------------------------------- #

def test_v289_numbered_disc_sections_may_restart_at_one(tmp_path):
    setlist = tmp_path / "disc_sections_restart.txt"
    setlist.write_text(
        "Disc One\n"
        "1 Cocaine\n"
        "2 My Back Pages\n\n"
        "Disc Two\n"
        "1 Can't Wait\n"
        "2 Highway 61 Revisited\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["normalized_number"] for track in tracks] == [1, 2, 3, 4]
    assert [track["title"] for track in tracks] == [
        "Cocaine",
        "My Back Pages",
        "Can't Wait",
        "Highway 61 Revisited",
    ]


def test_v289_side_letter_track_prefixes_parse_as_track_numbers(tmp_path):
    setlist = tmp_path / "side_letter_rows.txt"
    setlist.write_text(
        "A01 Perfect Way\n"
        "A02 Human Nature\n"
        "B03 Tutu\n"
        "B04 Portia\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["original_number"] for track in tracks] == [1, 2, 3, 4]
    assert [track["title"] for track in tracks] == ["Perfect Way", "Human Nature", "Tutu", "Portia"]


def test_v289_track_prefix_variants_are_accepted(tmp_path):
    setlist = tmp_path / "track_prefix_variants.txt"
    setlist.write_text(
        "t01: Jam>\n"
        "d1t02 - The Two Sisters\n"
        "cd1t03 - Third Tune\n"
        "04 - Chris intros> .32 Blues\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["title"] for track in tracks] == ["Jam>", "The Two Sisters", "Third Tune", "Chris intros> .32 Blues"]


def test_v289_set_section_comma_lists_are_parsed_without_splitting_medleys(tmp_path):
    setlist = tmp_path / "set_section_comma_lists.txt"
    setlist.write_text(
        "SET ONE\n"
        "Who Are You*,How Fine Is That,Freedom,Los Los,The Answer\n\n"
        "SET TWO\n"
        "Jam**>Flute Down**,Frankenstein,Apparently Nothing\n",
        encoding="utf-8",
    )

    tracks, source = T.parse_unnumbered_comma_tracks(str(setlist), 8)

    assert source == "comma-items"
    assert [track["title"] for track in tracks] == [
        "Who Are You",
        "How Fine Is That",
        "Freedom",
        "Los Los",
        "The Answer",
        "Jam>Flute Down",
        "Frankenstein",
        "Apparently Nothing",
    ]


def test_v289_strong_short_numbered_setlist_pads_unknown_tail(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio = []
    for idx in range(1, 4):
        path = tmp_path / f"{idx:02d}.flac"
        path.write_bytes(b"not real audio; write_audio_tags is patched")
        audio.append(str(path))
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Song A\n2 Song B\n", encoding="utf-8")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False)
    record = ShowMetadata(group_number=1, main_dir_name="Partial", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=3, artist="Artist",
                          date="2001-04-14", venue="Venue", location="City ST",
                          show_name="Artist 2001-04-14 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Partial",
             "setlist_file": str(setlist), "music_files": audio}
    calls = []
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((track_number, title)))
    messages = []

    stats = T.tag_group_with_record(config, group, record, emit=messages.append)

    assert stats["tagged"] == 3
    assert calls == [("01", "Song A"), ("02", "Song B"), ("03", "Unknown")]
    assert any("using listed titles" in str(message) for message in messages)


def test_v289_shn_tagging_error_uses_single_full_path_line(tmp_path):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio = tmp_path / "d1t01.shn"
    audio.write_bytes(b"not real shn")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Song A\n", encoding="utf-8")

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, convert_shn=False)
    record = ShowMetadata(group_number=1, main_dir_name="SHN", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=1, artist="Artist",
                          date="2001-04-14", venue="Venue", location="City ST",
                          show_name="Artist 2001-04-14 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "SHN",
             "setlist_file": str(setlist), "music_files": [str(audio)]}
    messages = []

    stats = T.tag_group_with_record(config, group, record, emit=messages.append)

    assert stats["errors"] == 1
    assert any(str(message).strip() == f"ERROR_AUDIO_FILE: '{audio}' - SHN is not directly taggable; enable Convert shn to convert before tagging" for message in messages)
    assert not any(" | d1t01.shn | " in str(message) for message in messages)


# --------------------------------------------------------------------------- #
# v290 - Split tag logs and inventory-style debug filenames
# --------------------------------------------------------------------------- #

def test_v290_log_manager_splits_tag_success_and_error_logs(tmp_path):
    from inventory_parser_lib import Config
    import logging_lib

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path))
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(tmp_path), 1, log_token="5")
    config.logs.tag("TAG_COPY: source -> dest")
    config.logs.tag("ERROR: '/tmp/bad.flac' - Not a valid FLAC file")

    success_text = (tmp_path / "logs" / "tags5.txt").read_text(encoding="utf-8")
    error_text = (tmp_path / "logs" / "tage5.txt").read_text(encoding="utf-8")
    assert "TAG_COPY: source -> dest" in success_text
    assert "Not a valid FLAC file" not in success_text
    assert "ERROR: '/tmp/bad.flac' - Not a valid FLAC file" in error_text
    assert "TAG_COPY: source -> dest" not in error_text


def test_v290_tag_debug_file_uses_inventory_setlist_filename(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01 file.flac"
    audio2 = tmp_path / "02 file.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "Info.txt"
    setlist.write_text("1 Only One Setlist Track\n", encoding="utf-8")

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=False)
    record = ShowMetadata(group_number=4, main_dir_name="Skipped Debug", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Skipped Debug",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}

    T.tag_group_with_record(config, group, record, emit=lambda _text: None,
                            allow_unknown_metadata=False,
                            fallback_to_filenames_on_track_problem=False,
                            metadata_problems=[],
                            meta_log_entry="SHOW_NAME: Artist 1977-05-08 Venue City ST\nSETLIST_FILE: " + str(setlist) + "\nEND_SHOW_METADATA\n")

    assert (tmp_path / "debug" / "Artist1977-05-08VenueCityST.txt").exists()
    assert not (tmp_path / "debug" / "Info.txt").exists()

# --------------------------------------------------------------------------- #
# v291 - Numbered Set I/Set II duration headings and embedded encore prefixes
# --------------------------------------------------------------------------- #

def test_v291_numbered_set_duration_headings_allow_track_restart_and_strip_encore_prefix(tmp_path):
    setlist = tmp_path / "deadco_set_duration_headings.txt"
    setlist.write_text(
        "Dead and Company\n"
        "2016-07-13\n"
        "First Niagara Pavilion\n"
        "Burgettstown, PA\n\n"
        "Source:\n"
        "Front of lawn > Zoom F8 @44.1kHz/16-bit > .wav\n\n"
        "Set I - 89 min.\n\n"
        "01. Hell in a Bucket\n"
        "02. Bertha\n"
        "03. Liberty >\n"
        "04. Maggie's Farm\n"
        "05. Cold Rain and Snow >\n"
        "06. Looks Like Rain\n"
        "07. Row Jimmy >\n"
        "08. Throwing Stones\n\n"
        "Set II - 99 min.\n\n"
        "01. Shakedown Street >\n"
        "02. Uncle John's Band >\n"
        "03. All Along the Watchtower >\n"
        "04. China Cat Sunflower >\n"
        "05. I Know You Rider >\n"
        "06. Drums > Space >\n"
        "07. Black Peter >\n"
        "08. Johnny B. Goode\n"
        "09. E: Midnight Hour\n\n"
        "dac2016-07-13.AKGmix.s01t01.flac:45f2ad314654f747f12bcf945e8e1d30\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["title"] for track in tracks] == [
        "Hell in a Bucket",
        "Bertha",
        "Liberty >",
        "Maggie's Farm",
        "Cold Rain and Snow >",
        "Looks Like Rain",
        "Row Jimmy >",
        "Throwing Stones",
        "Shakedown Street >",
        "Uncle John's Band >",
        "All Along the Watchtower >",
        "China Cat Sunflower >",
        "I Know You Rider >",
        "Drums > Space >",
        "Black Peter >",
        "Johnny B. Goode",
        "Midnight Hour",
    ]
    assert [track["normalized_number"] for track in tracks] == list(range(1, 18))


def test_v291_clean_track_title_strips_numbered_encore_variants():
    assert T._clean_track_title("E: Midnight Hour") == "Midnight Hour"
    assert T._clean_track_title("Encore: Midnight Hour") == "Midnight Hour"
    assert T._clean_track_title("Enc: Midnight Hour") == "Midnight Hour"

# --------------------------------------------------------------------------- #
# v292 - Implicit numbered list resets without set/disc headings
# --------------------------------------------------------------------------- #

def test_v292_numbered_lists_can_reset_without_set_or_disc_heading(tmp_path):
    setlist = tmp_path / "implicit_number_reset.txt"
    setlist.write_text(
        "1 First Set Opener\n"
        "2 First Set Second\n"
        "3 First Set Third\n"
        "4 First Set Closer\n"
        "1 Second Set Opener\n"
        "2 Second Set Second\n"
        "3 Second Set Closer\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["normalized_number"] for track in tracks] == list(range(1, 8))
    assert [track["title"] for track in tracks] == [
        "First Set Opener",
        "First Set Second",
        "First Set Third",
        "First Set Closer",
        "Second Set Opener",
        "Second Set Second",
        "Second Set Closer",
    ]


def test_v292_implicit_numbered_reset_may_have_blank_separator(tmp_path):
    setlist = tmp_path / "implicit_number_reset_blank.txt"
    setlist.write_text(
        "01. Disc One First\n"
        "02. Disc One Second\n\n"
        "01. Disc Two First\n"
        "02. Disc Two Second\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["title"] for track in tracks] == [
        "Disc One First",
        "Disc One Second",
        "Disc Two First",
        "Disc Two Second",
    ]


def test_v292_unconfirmed_reset_to_one_is_not_added_as_a_song(tmp_path):
    setlist = tmp_path / "unconfirmed_reset_to_one.txt"
    setlist.write_text(
        "1 Real Song One\n"
        "2 Real Song Two\n"
        "1 This note should not be tagged\n"
        "Source: cassette master > DAT\n",
        encoding="utf-8",
    )

    tracks = T.parse_setlist_tracks(str(setlist))

    assert [track["title"] for track in tracks] == ["Real Song One", "Real Song Two"]


# --------------------------------------------------------------------------- #
# v293 - Complete-path log compaction
# --------------------------------------------------------------------------- #

def test_v293_comp_log_compacts_legacy_multiple_media_rows_per_directory(tmp_path):
    from tlo_complete_path_log import compact_complete_path_log

    show_dir = tmp_path / "music" / "Artist 2001-04-14 Venue City ST"
    show_dir.mkdir(parents=True)
    first = show_dir / "01 opener.flac"
    second = show_dir / "02 middle.flac"
    third = show_dir / "03 closer.flac"
    for path in (first, second, third):
        path.write_bytes(b"audio")

    log_file = tmp_path / "compZ.log"
    log_file.write_text(
        "# completePathLog for search path: [VOL]Music\n"
        "SEARCH_PATH: [VOL]Music\n"
        f"{first}\n"
        f"{second}\n"
        f"{third}\n",
        encoding="utf-8",
    )

    removed = compact_complete_path_log(str(log_file))
    lines = log_file.read_text(encoding="utf-8").splitlines()
    payload = [line for line in lines if line and not line.startswith("#") and not line.startswith("SEARCH_PATH:")]

    assert removed == 2
    assert payload == [os.path.normpath(str(first))]


def test_v293_run_search_path_compacts_append_mode_legacy_comp_log(tmp_path, monkeypatch):
    from tlo_search_path_runner import run_search_path

    home = tmp_path / "home"
    search_root = tmp_path / "music"
    show_dir = search_root / "Artist 2001-04-14 Venue City ST"
    show_dir.mkdir(parents=True)
    files = [show_dir / name for name in ("01 opener.flac", "02 middle.flac", "03 closer.flac")]
    for path in files:
        path.write_bytes(b"audio")

    config = IPL.Config(debug=False, silent=True, TLOHome=str(home), compliant=False)
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(search_root), 1, log_token="L", log_mode="w")
    config.logs.complete_paths(str(files[1]))
    config.logs.complete_paths(str(files[2]))

    def fake_process_groups(config, artist_matcher):
        return []

    monkeypatch.setattr("tlo_search_path_runner.process_groups_for_search_path_v2", fake_process_groups)
    run_search_path(config, str(search_root), "", 1, log_token="L", log_mode="a", artist_matcher=object())

    lines = Path(config.logs.paths.complete_paths).read_text(encoding="utf-8").splitlines()
    payload = [line for line in lines if line and not line.startswith("#") and not line.startswith("SEARCH_PATH:")]
    assert payload == [os.path.normpath(str(files[1]))]

# v294 - Numbered list break lines and one-number duplicate repair

def test_v294_numbered_list_continues_after_break_line_before_encore(tmp_path):
    import tlo_tag_lib as T
    setlist = tmp_path / "encore_break.txt"
    setlist.write_text(
        "Artist\n"
        "Set II:\n"
        "1. Song One\n"
        "2. Song Two\n"
        "3. Encore Crowd\n"
        "___________________________\n"
        "4. Encore Song\n"
        "5.Next Encore\n"
        "\nNotes:\nnot a song\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [t["title"] for t in tracks] == [
        "Song One",
        "Song Two",
        "Encore Crowd",
        "Encore Song",
        "Next Encore",
    ]
    assert [t["normalized_number"] for t in tracks] == [1, 2, 3, 4, 5]


def test_v294_repairs_single_skipped_number_then_duplicate_row(tmp_path):
    import tlo_tag_lib as T
    setlist = tmp_path / "deadco_typo.txt"
    setlist.write_text(
        "Dead and Company\n"
        "Set I:\n"
        "1. Jam &gt;\n"
        "2. Jack Straw &gt;\n"
        "3. The Music Never Stopped*\n"
        "4. Next Time You See Me\n"
        "5. Loser*\n"
        "6. Peggy-O\n"
        "7. Help On the Way* &gt;\n"
        "9. Slipknot! &gt;\n"
        "9. Franklin's Tower*\n"
        "Set II:\n"
        "1. St. Stephen &gt;\n"
        "2. Dark Star&gt;\n"
        "3. Terrapin Station*&gt;\n"
        "4. Drums &gt; Space &gt;\n"
        "5. Terrapin Jam &gt;\n"
        "6. Morning Dew &gt;\n"
        "7. Casey Jones*\n"
        "8. Encore Crowd\n"
        "___________________________\n"
        "9. Black Muddy River\n"
        "10.U.S Blues *\n"
        "\nNotes:\n* guest\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert len(tracks) == 19
    assert [t["title"] for t in tracks][7:10] == [
        "Slipknot! >",
        "Franklin's Tower",
        "St. Stephen >",
    ]
    assert [t["normalized_number"] for t in tracks] == list(range(1, 20))

# v295 - Large non-song gaps between numbered rows

def test_v295_numbered_list_continues_across_large_note_gap(tmp_path):
    import tlo_tag_lib as T
    setlist = tmp_path / "large_gap_numbered_rows.txt"
    setlist.write_text(
        "Miles Davis\n"
        "Rare Miles 1946-60\n"
        "(Set 1)\n"
        "1. Woody `N You (Gillespie)                 4:58\n"
        "\n"
        "2. Bags' Groove (M. Jackson)                6:56\n"
        "3. What's New? (Burke-Haggart)              3:34\n"
        "4. But Not For Me (Gershwin-Gershwin)       6:44\n"
        "5. A Night in Tunisia (Gillespie-Paparelli) 7:04\n"
        "6. Four (M. Davis)                          4:12\n"
        "7. The Theme (M. Davis)                     0:17\n"
        "\n"
        "(Set 2)\n"
        "8. Walkin' (Carpenter)                      6:26\n"
        "9. Well, You Needn't (Monk)                 5:20\n"
        "10. Round Midnight (Hanighen-Williams-Monk) 5:30\n"
        "11. Lady Bird (Dameron-Heath)               5:04\n"
        "12. The Theme (M. Davis)                    0:18\n"
        "\n"
        "Originally from vinyl source\n"
        "http://www.plosin.com/milesAhead/Sessions.asp?s=571208\n"
        "Note: Originally, on Richard Russell's CDR source, Tracks 6-12 preceded\n"
        "Tracks 1-5. This explanatory paragraph is not a song.\n"
        "More prose and blank lines can appear here.\n"
        "\n"
        "Miles Davis Quintet\n"
        "Bandstand USA - Mutual Network radio broadcast\n"
        "Caf Bohemia, New York City, N.Y.\n"
        "May 17, 1958\n"
        "Miles Davis (tpt); John Coltrane (ts); Bill Evans (p)\n"
        "\n"
        "13. Four (Davis)                            4:53\n"
        "\n"
        "14. Bye Bye Blackbird (Henderson-Dixon)     6:54\n"
        "15. Walkin' (Carpenter)                     6:34\n"
        "16. Two Bass Hit (incomplete) (Lewis-Gillespie) 0:46\n"
        "\n"
        "Note: Track 16 is incomplete; this should not add another title.\n"
        "TOTAL TIME: 75:37\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert len(tracks) == 16
    assert [t["original_number"] for t in tracks] == list(range(1, 17))
    assert [t["title"] for t in tracks][12:] == [
        "Four (Davis)",
        "Bye Bye Blackbird (Henderson-Dixon)",
        "Walkin' (Carpenter)",
        "Two Bass Hit (incomplete) (Lewis-Gillespie)",
    ]


def test_v295_final_notes_do_not_extend_numbered_list_without_valid_continuation(tmp_path):
    import tlo_tag_lib as T
    setlist = tmp_path / "final_notes_no_continuation.txt"
    setlist.write_text(
        "Setlist:\n"
        "1. Song One\n"
        "2. Song Two\n"
        "3. Song Three\n"
        "Notes:\n"
        "Track 3 is incomplete on this source.\n"
        "1. This is a numbered note but it is not confirmed by a continuing 2.\n"
        "Thanks to the taper.\n",
        encoding="utf-8",
    )
    tracks = T.parse_setlist_tracks(str(setlist))
    assert [t["title"] for t in tracks] == ["Song One", "Song Two", "Song Three"]

# --------------------------------------------------------------------------- #
# v296 - Tag reason codes and audio-file errors stay out of debug files
# --------------------------------------------------------------------------- #

def test_v296_tag_reason_summary_counts_reason_codes(tmp_path):
    from inventory_parser_lib import Config
    import logging_lib

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path))
    logging_lib.setup_logging(config)
    config.logs.start_search_path(str(tmp_path), 1, log_token="6")
    config.logs.tag("SKIP_TITLE_COUNT: /music/show | track count mismatch: setlist=1 audio_files=2")
    config.logs.tag("ERROR_AUDIO_FILE: '/music/show/bad.flac' - Not a valid FLAC file")
    T.emit_tag_problem_summary(config, config.logs.tag)

    error_text = (tmp_path / "logs" / "tage6.txt").read_text(encoding="utf-8")
    assert "SKIP_TITLE_COUNT: /music/show | track count mismatch" in error_text
    assert "ERROR_AUDIO_FILE: '/music/show/bad.flac' - Not a valid FLAC file" in error_text
    assert "WARN_SUMMARY: tagging problem summary by reason code" in error_text
    assert "WARN_SUMMARY: ERROR_AUDIO_FILE: 1" in error_text
    assert "WARN_SUMMARY: SKIP_TITLE_COUNT: 1" in error_text

# --------------------------------------------------------------------------- #
# v297 - Tagger window elapsed time display
# --------------------------------------------------------------------------- #

def test_v297_tagger_elapsed_time_format():
    module_path = Path(__file__).with_name("tlo-ggi.py")
    spec = importlib.util.spec_from_file_location("tlo_ggi_for_v297_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module._format_elapsed_time(0) == "0:00"
    assert module._format_elapsed_time(59) == "0:59"
    assert module._format_elapsed_time(60) == "1:00"
    assert module._format_elapsed_time(61) == "1:01"
    assert module._format_elapsed_time(3661) == "1:01:01"

# --------------------------------------------------------------------------- #
# v298 - Tagger window width reduction
# --------------------------------------------------------------------------- #

def test_v298_tagger_window_uses_half_width_constants():
    module_path = Path(__file__).with_name("tlo-ggi.py")
    spec = importlib.util.spec_from_file_location("tlo_ggi_for_v298_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    assert module.TAGGER_PATH_ENTRY_WIDTH == 41
    assert module.TAGGER_OUTPUT_TEXT_WIDTH == 55
    assert module.TAGGER_PATH_ENTRY_WIDTH * 2 == 82
    assert module.TAGGER_OUTPUT_TEXT_WIDTH * 2 == 110

# --------------------------------------------------------------------------- #
# v299 - Standalone tagging title-tag fallback
# --------------------------------------------------------------------------- #

def test_v299_standalone_setlist_mismatch_can_use_existing_title_tags(tmp_path, monkeypatch):
    from inventory_parser_lib import Config

    audio1 = tmp_path / "01.flac"
    audio2 = tmp_path / "02.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 One Local Title\n", encoding="utf-8")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Standalone Titles", "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False)
    titles_by_path = {str(audio1): "d1t01", str(audio2): "02. Scarlet Begonias"}
    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path_name: titles_by_path.get(str(path_name), ""))
    messages = []

    tracks, source, problem = T._select_tracks_for_tagging(
        config,
        group,
        [str(audio1), str(audio2)],
        emit=messages.append,
        fallback_to_filenames_on_track_problem=False,
        fallback_to_title_tags_on_track_problem=True,
        record=None,
    )

    assert problem is None
    assert source == "title-tags"
    assert [track["title"] for track in tracks] == ["Unknown", "Scarlet Begonias"]
    assert any("using existing audio title tags" in str(message) for message in messages)
    assert any("empty, generic, or unusable" in str(message) for message in messages)


def test_v299_process_tagging_group_uses_title_tags_for_standalone_tagger(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01.flac"
    audio2 = tmp_path / "02.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Setlist Only Has One Title\n", encoding="utf-8")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Standalone Process", "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}
    record = ShowMetadata(group_number=1, main_dir_name="Standalone Process", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False)
    titles_by_path = {str(audio1): "01. First Existing Title", str(audio2): "Track 2"}
    calls = []

    monkeypatch.setattr(T, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], []))
    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path_name: titles_by_path.get(str(path_name), ""))
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((Path(path).name, track_number, title)))

    stats = T.process_tagging_group(config, group, artist_matcher=object(), emit=lambda _text: None)

    assert stats["tagged"] == 2
    assert stats["skipped"] == 0
    assert stats["title_tag_folders"] == [str(tmp_path)]
    assert calls == [("01.flac", "01", "First Existing Title"), ("02.flac", "02", "Unknown")]

# --------------------------------------------------------------------------- #
# v300 - Unknown song-title tags do not create debug files
# --------------------------------------------------------------------------- #

def test_v300_partial_unknown_title_tags_do_not_create_debug_file(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    audio1 = tmp_path / "01.flac"
    audio2 = tmp_path / "02.flac"
    audio1.write_bytes(b"not real audio")
    audio2.write_bytes(b"not real audio")
    setlist = tmp_path / "info.txt"
    setlist.write_text("1 Local Title Only\n", encoding="utf-8")

    titles_by_path = {str(audio1): "01. Real Existing Title", str(audio2): "Track 2"}
    calls = []
    monkeypatch.setattr(T, "read_existing_audio_title_tag", lambda path_name: titles_by_path.get(str(path_name), ""))
    monkeypatch.setattr(T, "write_audio_tags", lambda path, artist, album, track_number, title, total_tracks=0: calls.append((track_number, title)))

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    record = ShowMetadata(group_number=10, main_dir_name="Partial Unknown", main_dir_path=str(tmp_path),
                          setlist_file=str(setlist), music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "Partial Unknown",
             "setlist_file": str(setlist), "music_files": [str(audio1), str(audio2)]}

    stats = T.tag_group_with_record(config, group, record, emit=lambda _text: None,
                                    allow_unknown_metadata=True,
                                    fallback_to_filenames_on_track_problem=True,
                                    metadata_problems=[],
                                    meta_log_entry="SHOW_NAME: Artist 1977-05-08 Venue City ST\nEND_SHOW_METADATA\n")

    assert stats["tagged"] == 2
    assert calls == [("01", "Real Existing Title"), ("02", "Unknown")]
    assert not (tmp_path / "debug").exists()


def test_v300_no_readable_setlist_and_failed_fallbacks_do_not_create_debug_file(tmp_path, monkeypatch):
    from inventory_parser_lib import Config
    from tlo_models import ShowMetadata

    config = Config(debug=True, silent=True, TLOHome=str(tmp_path), compliant=False)
    record = ShowMetadata(group_number=11, main_dir_name="No Readable Setlist", main_dir_path=str(tmp_path),
                          setlist_file="", music_file_count=2, artist="Artist",
                          date="1977-05-08", venue="Venue", location="City ST",
                          show_name="Artist 1977-05-08 Venue City ST")
    group = {"main_dir_path": str(tmp_path), "main_dir_name": "No Readable Setlist",
             "setlist_file": "", "music_files": []}

    stats = T.tag_group_with_record(config, group, record, emit=lambda _text: None,
                                    allow_unknown_metadata=False,
                                    fallback_to_filenames_on_track_problem=False,
                                    fallback_to_title_tags_on_track_problem=True,
                                    metadata_problems=[])

    assert stats["skipped"] == 1
    assert not (tmp_path / "debug").exists()



# --------------------------------------------------------------------------- #
# v303 - Rename Compliantly is independent of tagging
# --------------------------------------------------------------------------- #

def test_v303_inventory_parser_allows_rename_without_tag_mode():
    values = {
        "rename_compliantly": True,
        "tag_during_inventory": False,
        "tag_copy_during_inventory": False,
        "tag_copy_and_delete_path": "",
    }
    IPL._validate_tag_copy_values(values)
    assert values["rename_compliantly"] is True


def test_v303_gui_has_no_rename_requires_tag_mode_block():
    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    assert "_show_rename_requires_tag_mode_alert" not in source
    assert "Because Rename Compliantly is checked" not in source


def test_v303_rename_only_inventory_renames_in_place_without_tagging(tmp_path, monkeypatch):
    from tlo_models import ShowMetadata
    import tlo_phase23_v2 as P
    import tlo_tag_lib as T

    source = tmp_path / "bad folder name"
    source.mkdir()
    audio = source / "01 Song.flac"
    audio.write_bytes(b"abc")
    show_name = "Artist 1970-01-01 Venue City ST"
    record = ShowMetadata(
        group_number=1,
        main_dir_name=source.name,
        main_dir_path=str(source),
        setlist_file="",
        music_file_count=1,
        artist="Artist",
        date="1970-01-01",
        venue="Venue",
        city="City",
        region="ST",
        location="City ST",
        show_name=show_name,
        music_dirs=[str(source)],
        setlist_files=[],
    )
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "music_sample_files": [str(audio)],
        "music_file_count": 1,
        "setlist_file": "",
        "setlist_files": [],
        "txt_files": [],
    }

    class Logs:
        def __init__(self):
            self.tag_messages = []
            self.group_messages = []
            self.meta_messages = []
            self.conflict_messages = []
            self.paths = SimpleNamespace(complete_paths=str(tmp_path / "comp.log"))
        def tag(self, fmt, *args): self.tag_messages.append(fmt % args if args else fmt)
        def groups(self, fmt, *args): self.group_messages.append(fmt % args if args else fmt)
        def show_metadata(self, fmt, *args): self.meta_messages.append(fmt % args if args else fmt)
        def conflicts(self, fmt, *args): self.conflict_messages.append(fmt % args if args else fmt)

    logs = Logs()
    logs_path = Path(logs.paths.complete_paths)
    logs_path.write_text(f"# completePathLog for search path: []\nSEARCH_PATH: []\n{audio}\n", encoding="utf-8")
    config = IPL.Config(
        debug=False,
        silent=True,
        TLOHome=str(tmp_path),
        current_search_path=str(tmp_path),
        rename_compliantly=True,
        tag_during_inventory=False,
        tag_copy_during_inventory=False,
    )
    config.logs = logs

    monkeypatch.setattr(P, "_build_groups_from_search_path", lambda *_args, **_kwargs: [group])
    monkeypatch.setattr(P, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], []))
    monkeypatch.setattr(T, "tag_group_with_record", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("tagging must not run")))

    records = P.process_groups_for_search_path_v2(config, artist_matcher=None)

    renamed = tmp_path / show_name
    assert not source.exists()
    assert renamed.is_dir()
    assert records[0].main_dir_path == str(renamed)
    assert config.tag_during_inventory is False
    assert any("tagging=disabled" in message for message in logs.tag_messages)
    complete_text = logs_path.read_text(encoding="utf-8")
    assert str(renamed / "01 Song.flac") in complete_text
    assert str(audio) not in complete_text


def test_v303_standalone_tagger_accepts_rename_without_explicit_tag_mode(tmp_path):
    import tlo_tag_lib as T

    home = tmp_path / "TLOHome"
    home.mkdir()
    config = T.build_tagger_config(
        tlo_home=str(home),
        tag_in_place=False,
        tag_copy=False,
        rename_compliantly=True,
    )
    assert config.rename_compliantly is True
    assert config.tag_copy_during_inventory is False


# --------------------------------------------------------------------------- #
# v304 - empty-volume roots are serial; named volumes run in parallel
# --------------------------------------------------------------------------- #

def test_v304_path_split_serializes_only_empty_volume_roots():
    import walk_trees_lib as W

    items = [
        ("/mnt/c/blank-a", "", "", "c", "1", "w"),
        ("/mnt/d/named-a", "", "Archive A", "d", "2", "w"),
        ("/mnt/e/blank-b", "", "", "e", "1", "a"),
        ("/mnt/f/named-b", "", "Archive B", "f", "3", "w"),
    ]
    serial_items, named_items = W._split_serial_and_parallel_items(SimpleNamespace(), items)

    assert [item[0] for item in serial_items] == ["/mnt/c/blank-a", "/mnt/e/blank-b"]
    assert [item[0] for item in named_items] == ["/mnt/d/named-a", "/mnt/f/named-b"]


def test_v304_named_volume_paths_group_by_volume_for_parallel_workers():
    import walk_trees_lib as W

    items = [
        ("/mnt/d/one", "", "Archive A", "d", "2", "w"),
        ("/mnt/e/two", "", "Archive B", "e", "3", "w"),
        ("/mnt/d/three", "", "archive a", "d", "2", "a"),
    ]
    groups = W._group_named_volume_items(items)

    assert [[item[0] for item in group] for group in groups] == [
        ["/mnt/d/one", "/mnt/d/three"],
        ["/mnt/e/two"],
    ]


def test_v330_blank_group_runs_after_named_volume_groups(monkeypatch):
    import walk_trees_lib as W

    monkeypatch.setattr(W, "resolve_physical_drive_id", lambda path: "")
    blank = [
        ("/mnt/c/blank-a", "", "", "c", "1", "w"),
        ("/mnt/e/blank-b", "", "", "e", "1", "a"),
    ]
    named = [
        ("/mnt/d/named-a", "", "Archive A", "d", "2", "w"),
        ("/mnt/f/named-b", "", "Archive B", "f", "3", "w"),
    ]
    groups = W._build_volume_work_groups(blank, named)

    assert [[item[0] for item in group] for group in groups] == [
        ["/mnt/d/named-a"],
        ["/mnt/f/named-b"],
        ["/mnt/c/blank-a", "/mnt/e/blank-b"],
    ]


def test_v304_inventory_updater_button_uses_requested_two_line_label():
    gui = _load_tlo_ggi_module()
    build_source = inspect.getsource(gui.AddToInventoryWindow._build)
    assert 'text="Process Potential\\nDuplicate/Upgrades"' in build_source


# --------------------------------------------------------------------------- #
# v305 - public v1.0/Build display and concise startup output
# --------------------------------------------------------------------------- #

def test_v305_public_version_matches_bundle_number():
    import tlo_version as V

    assert V.VERSION == "v335"
    assert V.BUNDLE_BUILD == 335
    assert V.DISPLAY_VERSION == "v1.2 Build 335"
    assert V.versioned_title("TLO Inventory GUI") == "TLO Inventory GUI v1.2 Build 335"


def test_v305_startup_banner_never_appends_release_change_summary():
    import tlo_main_lib as M
    import tlo_version as V

    for debug in (False, True):
        banner = M._startup_banner(SimpleNamespace(debug=debug))
        assert banner == "Starting tlo-gi v1.2 Build 335"
        assert V.VERSION_SUMMARY not in banner
        assert " - " not in banner


def test_v305_all_toplevel_gui_titles_include_public_version():
    gui = _load_tlo_ggi_module()
    from tlo_inventory_update import UPDATER_DISPLAY_VERSION

    assert gui.WINDOW_TITLE == "TLO Inventory GUI v1.2 Build 335"
    assert gui.TAGGER_DISPLAY_VERSION == "TLO Tagger GUI v1.2 Build 335"
    assert UPDATER_DISPLAY_VERSION == "TLO Inventory Updater v1.2 Build 335"

    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    expected_calls = (
        'alert.title(versioned_title("TLO Backup Alert"))',
        'dialog.title(versioned_title("Tag Copy"))',
        'dialog.title(versioned_title("Existing TLO Inventory"))',
        'self.window.title(versioned_title("TLO Handle Duplicates"))',
        'review.title(versioned_title(f"TLO Txt Review - {os.path.basename(path_name)}"))',
    )
    for call in expected_calls:
        assert call in source


# --------------------------------------------------------------------------- #
# v308 - toBeInventoried.txt blank/comment handling
# --------------------------------------------------------------------------- #

def test_v308_inventory_file_ignores_hash_comments_and_blank_lines(tmp_path):
    import inventory_list_lib as IL

    inv = tmp_path / "toBeInventoried.txt"
    inv.write_text(
        "# TLO toBeInventoried.txt\n"
        "#\n"
        "   # indented comment\n"
        "\n"
        "G:\\x\n"
        "\t\n"
        "I:\\x\n",
        encoding="utf-8",
    )

    parsed = IL._parse_inventory_file(str(inv))

    assert parsed == [
        (r"G:\x", "/mnt/g/x", "", ""),
        (r"I:\x", "/mnt/i/x", "", ""),
    ]


def test_v308_inventory_file_ignores_utf8_bom_hash_comment(tmp_path):
    import inventory_list_lib as IL

    inv = tmp_path / "toBeInventoried.txt"
    inv.write_text("\ufeff# heading\n/mnt/e/music\n", encoding="utf-8")

    assert IL._parse_inventory_file(str(inv)) == [
        ("/mnt/e/music", "/mnt/e/music", "", ""),
    ]

# --------------------------------------------------------------------------- #
# v313 - Add Shows first-run guard when no bootlist exists
# --------------------------------------------------------------------------- #

def test_v313_add_shows_first_run_blank_volume_warns_and_does_not_continue(tmp_path, monkeypatch):
    gui = _load_tlo_ggi_module()
    updater = object.__new__(gui.AddToInventoryWindow)
    updater.config = SimpleNamespace(TLOHome=str(tmp_path))
    updater.window = None
    calls = []

    def fake_showwarning(title, message, parent=None):
        calls.append((title, message, parent))

    monkeypatch.setattr(gui.messagebox, "showwarning", fake_showwarning)
    monkeypatch.setattr(gui.messagebox, "askokcancel", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("askokcancel should not be called")))

    assert updater._confirm_first_add_shows_run("") is False
    assert calls
    assert "No existing bootlist.csv was found" in calls[0][1]
    assert "Enter the Current Backup/Storage Drive and Volume before continuing" in calls[0][1]


def test_v313_add_shows_first_run_with_volume_requires_continue_confirmation(tmp_path, monkeypatch):
    gui = _load_tlo_ggi_module()
    updater = object.__new__(gui.AddToInventoryWindow)
    updater.config = SimpleNamespace(TLOHome=str(tmp_path))
    updater.window = None
    prompts = []

    def fake_askokcancel(title, message, parent=None):
        prompts.append((title, message, parent))
        return False

    monkeypatch.setattr(gui.messagebox, "showwarning", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("showwarning should not be called")))
    monkeypatch.setattr(gui.messagebox, "askokcancel", fake_askokcancel)

    assert updater._confirm_first_add_shows_run("Archive 1") is False
    assert prompts
    assert "No existing bootlist.csv was found" in prompts[0][1]
    assert "Continue with Add Shows as the first inventory output?" in prompts[0][1]


def test_v313_add_shows_existing_bootlist_does_not_prompt(tmp_path, monkeypatch):
    gui = _load_tlo_ggi_module()
    (tmp_path / "bootlist.csv").write_text("sep=^\nShow^VolumePath\n", encoding="utf-8")
    updater = object.__new__(gui.AddToInventoryWindow)
    updater.config = SimpleNamespace(TLOHome=str(tmp_path))
    updater.window = None

    monkeypatch.setattr(gui.messagebox, "showwarning", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("showwarning should not be called")))
    monkeypatch.setattr(gui.messagebox, "askokcancel", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("askokcancel should not be called")))

    assert updater._confirm_first_add_shows_run("") is True


# --------------------------------------------------------------------------- #
# v317 - Main inventory hamburger Help cascade, About dialog, and FAQ file
# --------------------------------------------------------------------------- #

def test_v317_main_inventory_hamburger_help_cascade_sources_about_and_faq():
    gui = _load_tlo_ggi_module()
    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")

    assert 'ttk.Menubutton(' in source
    assert 'text="☰"' in source
    assert 'self.hamburger_menu.add_cascade(label="Help", menu=self.help_menu)' in source
    assert 'self.help_menu = tk.Menu(self.hamburger_menu, tearoff=False)' in source
    assert 'self.help_menu.add_command(label="About", command=self._show_about_from_menu)' in source
    assert 'self.help_menu.add_command(label="FAQ", command=self._show_faq_from_menu)' in source
    assert 'def _run_after_menu_closes(self, callback):' in source
    assert 'def _show_about_from_menu(self):' in source
    assert 'def _show_faq_from_menu(self):' in source
    assert 'text="Help\\n "' not in source
    assert 'def _show_help_menu' not in source
    assert 'Traders Little Organizer™ - TLO' in source
    assert 'f"V1.2Build{BUNDLE_BUILD}\\n"' in source
    assert 'TLO-FAQ.txt' in source
    assert gui.BUNDLE_BUILD == 335






def test_v330_about_dialog_uses_superscript_trademark_symbol():
    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")

    assert "Traders Little Organizer™ - TLO" in source
    assert "Traders Little Organizer(TM) - TLO" not in source


def test_v317_help_menu_wrappers_schedule_dialog_callbacks():
    gui = _load_tlo_ggi_module()
    calls = []

    class DummyRoot:
        def after_idle(self, callback):
            calls.append(("after_idle", callback.__name__))
            callback()

    class DummyGui:
        root = DummyRoot()

        def _show_about(self):
            calls.append(("dialog", "about"))

        def _show_faq(self):
            calls.append(("dialog", "faq"))

    dummy = DummyGui()
    dummy._run_after_menu_closes = lambda callback: gui.App._run_after_menu_closes(dummy, callback)

    gui.App._show_about_from_menu(dummy)
    gui.App._show_faq_from_menu(dummy)

    assert ("after_idle", "_show_about") in calls
    assert ("dialog", "about") in calls
    assert ("after_idle", "_show_faq") in calls
    assert ("dialog", "faq") in calls


def test_v317_faq_file_is_in_source_bundle():
    faq = Path(__file__).with_name("TLO-FAQ.txt")
    assert faq.is_file()
    text = faq.read_text(encoding="utf-8")
    assert "Q:Is TLO a commercial application:" in text
    assert "A: No, TLO is freeware." in text
    assert "LiveShowTagger" in text
    assert "Do I need to define TLOHome before I do anything?" in text
    assert "Can TLO ever do anything destructive?" in text
    assert "What if I forget and accidentally re-inventory a drive?" in text
    assert "copy and delete" in text
    assert "duplicate entries" in text


# --------------------------------------------------------------------------- #
# v319 - CorruptFlacs.txt and tlo-gsi --myTLO compatibility
# --------------------------------------------------------------------------- #

def _load_tlo_gsi_module():
    module_path = Path(__file__).with_name("tlo-gsi.py")
    spec = importlib.util.spec_from_file_location("tlo_gsi_for_tests", module_path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
        return module
    finally:
        sys.modules.pop(spec.name, None)


def test_v319_tlo_gsi_accepts_hidden_mytlo_with_same_precedence(tmp_path, monkeypatch):
    gsi = _load_tlo_gsi_module()
    env_home = tmp_path / "envHome"
    cli_home = tmp_path / "cliHome"
    my_home = tmp_path / "myHome"
    for path in (env_home, cli_home, my_home):
        path.mkdir()
    monkeypatch.setenv("TLOHome", str(env_home))

    resolved, find_value = gsi.parse_cli_args([
        "--TLOHome", str(cli_home),
        "--myTLO", str(my_home),
        "--find", "Dylan",
    ])

    assert resolved == my_home
    assert find_value == "Dylan"
    assert "--myTLO" not in gsi.HELP_TEXT


def test_v319_corrupt_flacs_log_is_created_and_records_only_flac_paths(tmp_path):
    from inventory_parser_lib import Config
    import tlo_tag_lib as taglib

    config = Config(debug=False, silent=True, TLOHome=str(tmp_path), compliant=False, tag_during_inventory=True)
    log_path = tmp_path / "CorruptFlacs.txt"

    taglib.ensure_corrupt_flacs_log(config)
    assert log_path.is_file()
    assert log_path.read_text(encoding="utf-8") == ""

    flac_path = tmp_path / "Bad Show" / "bad01.flac"
    mp3_path = tmp_path / "Bad Show" / "bad01.mp3"
    taglib.record_corrupt_flac(config, str(flac_path))
    taglib.record_corrupt_flac(config, str(mp3_path))

    assert log_path.read_text(encoding="utf-8").splitlines() == [str(flac_path)]


def test_v319_flac_tag_write_failures_are_recorded_to_corrupt_flacs(tmp_path, monkeypatch):
    import tlo_tag_lib as taglib

    audio_path = tmp_path / "bad.flac"
    audio_path.write_bytes(b"not really a flac")
    config = SimpleNamespace(TLOHome=str(tmp_path))
    taglib.ensure_corrupt_flacs_log(config)

    def fake_write_audio_tags(*_args, **_kwargs):
        raise taglib.TaggerError("not a valid flac file")

    monkeypatch.setattr(taglib, "write_audio_tags", fake_write_audio_tags)
    group = {"main_dir_path": str(tmp_path), "music_files": [str(audio_path)]}
    record = SimpleNamespace(artist="Artist", album_name="Album", venue="", date="2024-01-01", location="", show_name="Artist 2024-01-01")
    tracks = [{"normalized_number": 1, "title": "Song"}]
    monkeypatch.setattr(taglib, "_rescan_group_audio_files", lambda _group: [str(audio_path)])
    monkeypatch.setattr(taglib, "_prepare_audio_files_for_tagging", lambda _config, _group, raw, emit=None: (list(raw), 0))
    monkeypatch.setattr(taglib, "_select_tracks_for_tagging", lambda *_args, **_kwargs: (tracks, "test", ""))

    stats = taglib.tag_group_with_record(config, group, record, emit=lambda _text: None)

    assert stats["errors"] == 1
    assert (tmp_path / "CorruptFlacs.txt").read_text(encoding="utf-8").splitlines() == [str(audio_path)]


# --------------------------------------------------------------------------- #
# v319 - Cleanup hardening for forced exits, CLI Ctrl-C, SHN timeout, and file reads
# --------------------------------------------------------------------------- #

def test_v319_runtime_control_exposes_child_cleanup_backstop():
    import inspect
    import tlo_runtime_control as R

    source = inspect.getsource(R.terminate_all_children)
    assert "multiprocessing.active_children" in source
    assert ".terminate()" in source
    assert ".join(timeout=join_timeout)" in source
    assert ".kill()" in source


def test_v319_gui_forced_exits_sweep_children_before_os_exit():
    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    assert "def _force_exit_after_child_cleanup" in source
    assert "terminate_all_children()" in source
    assert "flush_standard_streams()" in source
    assert "os._exit(code)" in source
    assert source.count("self._force_exit_after_child_cleanup(130)") >= 3


def test_v319_cli_keyboard_interrupt_cleans_newly_allocated_tokens():
    source = Path(__file__).with_name("tlo-gi.py").read_text(encoding="utf-8")
    assert "except KeyboardInterrupt" in source
    assert "request_cancel_and_terminate_active_executor()" in source
    assert "terminate_all_children()" in source
    assert "newly_allocated_log_tokens" in source
    assert "delete_logs_for_tokens" in source


def test_v319_run_inventory_keyboard_interrupt_uses_newly_allocated_tokens():
    source = Path(__file__).with_name("tlo_main_lib.py").read_text(encoding="utf-8")
    assert "except KeyboardInterrupt" in source
    assert "terminate_all_children()" in source
    assert "newly_allocated_log_tokens" in source
    assert "delete_logs_for_tokens(config.TLOHome, tokens)" in source


def test_v319_shn_conversion_uses_timeout_and_reports_timeout(monkeypatch, tmp_path):
    import subprocess
    import tlo_tag_lib as taglib

    shn = tmp_path / "01 Song One.shn"
    shn.write_bytes(b"fake shn")
    monkeypatch.setattr(taglib, "_bundled_ffmpeg_executable", lambda: "/app/bundled/ffmpeg")

    calls = []
    def fake_run(command, stdout=None, stderr=None, text=None, timeout=None):
        calls.append((command, timeout))
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(taglib.subprocess, "run", fake_run)

    with pytest.raises(taglib.TaggerError) as exc:
        taglib.convert_shn_to_flac(str(shn), emit=lambda _text: None)

    assert calls and calls[0][1] == taglib.SHN_CONVERSION_TIMEOUT_SECONDS
    assert "timed out" in str(exc.value)
    assert not (tmp_path / "01 Song One.flac.tlo-convert.tmp.flac").exists()


def test_v319_setlist_date_fallback_uses_context_manager_for_drive_file_reads():
    source = Path(__file__).with_name("tlo_phase23_v2.py").read_text(encoding="utf-8")
    assert 'data = open(path_name, "rb").read()' not in source
    assert 'with open(path_name, "rb") as infile:' in source
    assert "data = infile.read()" in source


# v323 - Packaged platform icon assets

def test_v323_packaged_platform_icon_assets_are_present():
    from pathlib import Path
    icon_dir = Path(__file__).resolve().parent / "icons"
    for stem in ("tlo-inventory-icon", "tlo-search-icon", "tlo-tag-icon"):
        assert (icon_dir / f"{stem}.png").is_file()
        assert (icon_dir / f"{stem}.ico").is_file()
        assert (icon_dir / f"{stem}.icns").is_file()


def test_v323_windows_dist_uses_packaged_ico_files_directly():
    from pathlib import Path
    text = (Path(__file__).resolve().parent / "createWindowsDist.ps1").read_text(encoding="utf-8")
    assert "$IconRoot = Join-Path $SourceRoot 'icons'" in text
    assert "tlo-inventory-icon.ico" in text
    assert "tlo-search-icon.ico" in text
    assert "tlo-tag-icon.ico" in text
    assert "Required Windows icon file not found" in text
    assert "Convert-PngIconToWindowsIco" not in text



def test_v323_windows_ico_assets_are_dib_based_not_png_compressed():
    import struct
    from pathlib import Path

    png_signature = bytes([137, 80, 78, 71, 13, 10, 26, 10])
    icon_dir = Path(__file__).resolve().parent / "icons"
    for stem in ("tlo-inventory-icon", "tlo-search-icon", "tlo-tag-icon"):
        data = (icon_dir / f"{stem}.ico").read_bytes()
        reserved, icon_type, count = struct.unpack_from("<HHH", data, 0)
        assert reserved == 0
        assert icon_type == 1
        assert count >= 5
        for index in range(count):
            entry_offset = 6 + index * 16
            width, height, colors, res, planes, bit_count, size, image_offset = struct.unpack_from("<BBBBHHII", data, entry_offset)
            blob = data[image_offset:image_offset + size]
            assert blob
            assert not blob.startswith(png_signature), f"{stem}.ico entry {index} is PNG-compressed, not DIB/BMP-based"


def test_v323_windows_dist_verifies_exact_packaged_icon_resources():
    from pathlib import Path
    text = (Path(__file__).resolve().parent / "createWindowsDist.ps1").read_text(encoding="utf-8")
    assert "Assert-WindowsIcoIsDibBased" in text
    assert "Assert-WindowsExeMatchesSourceIcon" in text
    assert "hashlib.sha256(blob).hexdigest()" in text
    assert "source_digests - exe_digests" in text
    assert "missing_source_images" in text
    assert "RT_ICON" in text
    assert "pefile" in text

# --------------------------------------------------------------------------- #
# v323 - Compliant rename paths preserve trailing parentheticals
# --------------------------------------------------------------------------- #

def test_v323_compliant_string2_show_name_preserves_parentheticals():
    from tlo_models import ShowMetadata

    record = ShowMetadata(
        group_number=1,
        main_dir_name="Artist 2001-02-03 Venue City ST (SBD)",
        main_dir_path="/tmp/Artist 2001-02-03 Venue City ST (SBD)",
        setlist_file="",
        music_file_count=1,
        artist="Artist",
        date="2001-02-03",
        venue="Venue City ST",
        parentheticals="(SBD)",
    )

    assert P._build_compliant_string2_show_name(record) == "Artist 2001-02-03 Venue City ST (SBD)"


def test_v323_compliant_dash_show_name_preserves_parentheticals():
    from tlo_models import ShowMetadata

    record = ShowMetadata(
        group_number=1,
        main_dir_name="Artist - Album Title (FM)",
        main_dir_path="/tmp/Artist - Album Title (FM)",
        setlist_file="",
        music_file_count=1,
        artist="Artist",
        venue="Album Title",
        parentheticals="(FM)",
    )

    assert P._build_compliant_dash_show_name(record) == "Artist - Album Title (FM)"


def test_v323_add_shows_compliant_rename_preserves_record_parentheticals(tmp_path):
    import json
    from types import SimpleNamespace

    folder = tmp_path / "Artist 2001-02-03 Venue City ST (SBD)"
    folder.mkdir()
    info = folder / "info.txt"
    info.write_text("01 Song\n", encoding="utf-8")
    record = {
        "show_name": "Artist 2001-02-03 Venue City ST",
        "parentheticals": "(SBD)",
        "main_dir_path": str(folder),
        "setlist_file": str(info),
        "setlist_files_json": json.dumps([str(info)]),
        "music_dirs_json": json.dumps([str(folder)]),
    }

    new_folder = U._rename_add_shows_folder_compliantly(SimpleNamespace(rename_compliantly=True), str(folder), record)
    expected = tmp_path / "Artist 2001-02-03 Venue City ST (SBD)"

    assert new_folder == os.path.normpath(str(expected))
    assert expected.is_dir()
    assert record["main_dir_path"] == os.path.normpath(str(expected))
    assert record["setlist_file"] == os.path.normpath(str(expected / "info.txt"))
    assert json.loads(record["music_dirs_json"]) == [os.path.normpath(str(expected))]


def test_v323_inventory_tag_rename_preserves_record_parentheticals(tmp_path):
    from tlo_models import ShowMetadata

    source = tmp_path / "raw source folder"
    source.mkdir()
    audio = source / "01 Song.flac"
    audio.write_bytes(b"fake")
    setlist = source / "info.txt"
    setlist.write_text("01 Song\n", encoding="utf-8")
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(audio)],
        "music_sample_files": [str(audio)],
        "setlist_file": str(setlist),
        "setlist_files": [str(setlist)],
        "txt_files": [str(setlist)],
    }
    record = ShowMetadata(
        group_number=1,
        main_dir_name=source.name,
        main_dir_path=str(source),
        setlist_file=str(setlist),
        music_file_count=1,
        artist="Artist",
        date="2001-02-03",
        venue="Venue City ST",
        show_name="Artist 2001-02-03 Venue City ST",
        parentheticals="(SBD)",
        music_dirs=[str(source)],
        setlist_files=[str(setlist)],
    )
    config = IPL.Config(debug=False, silent=True, TLOHome=str(tmp_path), tag_during_inventory=True, rename_compliantly=True)

    renamed_group, renamed_record = T.prepare_inventory_tagging_target(config, group, record, emit=lambda _text: None)
    expected = tmp_path / "Artist 2001-02-03 Venue City ST (SBD)"

    assert not source.exists()
    assert expected.is_dir()
    assert renamed_group is group
    assert renamed_record is record
    assert group["main_dir_path"] == os.path.normpath(str(expected))
    assert record.main_dir_path == os.path.normpath(str(expected))
    assert group["setlist_file"] == os.path.normpath(str(expected / "info.txt"))



def test_v323_update_checker_prefers_platform_update_asset(monkeypatch, tmp_path):
    import tlo_github_updates as G

    release = {
        "tag_name": "v1.1-build324",
        "name": "TLO v1.1 Build 324",
        "assets": [
            {"name": "TLO_V1.1Build324_complete.zip", "browser_download_url": "https://example.invalid/complete", "size": 1},
            {"name": "TLO_V1.1Build324_update_Linux.zip", "browser_download_url": "https://example.invalid/linux", "size": 1},
        ],
    }
    monkeypatch.setattr(G.sys, "platform", "linux")
    asset, kind, platform = G._choose_asset(release, 324)

    assert asset["name"] == "TLO_V1.1Build324_update_Linux.zip"
    assert kind == "update"
    assert platform == "linux"


def test_v323_update_settings_are_tlohome_local(tmp_path):
    import json
    import tlo_github_updates as G

    assert G.is_auto_update_enabled(tmp_path) is False
    G.set_auto_update_enabled(tmp_path, True)

    settings_path = tmp_path / "update-settings.json"
    assert settings_path.is_file()
    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    assert settings["auto_update"] is True
    assert G.is_auto_update_enabled(tmp_path) is True
    assert G.should_auto_check(tmp_path) is True


def test_v323_inventory_and_search_sources_include_update_menu_items():
    inventory_source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    search_source = Path(__file__).with_name("tlo-gsi.py").read_text(encoding="utf-8")

    for source in (inventory_source, search_source):
        assert 'label="Check for updates"' in source
        assert 'label="Auto update"' in source
        assert 'update-settings.json' in Path(__file__).with_name("tlo_github_updates.py").read_text(encoding="utf-8")
        assert 'check_for_updates' in source

# --------------------------------------------------------------------------- #
# v324 - Add Shows honors Tag in Place for regular and duplicate workflows.
# --------------------------------------------------------------------------- #

def test_v324_build_config_add_shows_honors_tag_in_place_but_ignores_tag_copy():
    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    build_config = source[source.index("    def _build_config(self, *, for_add_shows=False):"):source.index("    def _pause_inventory(self):")]

    assert 'tag_in_place = bool(self.bool_vars["tag_during_inventory"].get())' in build_config
    assert "Add Shows honors Tag in Place" in build_config
    assert "tag_copy = False" in build_config
    assert "tag_in_place = False" not in build_config


def test_v324_add_shows_regular_and_duplicate_paths_tag_before_staging():
    source = Path(__file__).with_name("tlo_inventory_update.py").read_text(encoding="utf-8")
    regular = source[source.index("def process_new_shows") : source.index("def duplicate_work_items")]
    duplicate = source[source.index("def process_duplicate_folder") : source.index("def delete_new_keep_old")]

    regular_tag = regular.index("_tag_add_shows_folder_in_place(config, folder, record_dict, generated_setlist)")
    regular_move = regular.index('move_folder_to(folder, dirs["staged"])')
    duplicate_tag = duplicate.index("_tag_add_shows_folder_in_place(config, folder, record, generated_setlist)")
    duplicate_move = duplicate.index('move_folder_to(folder, dirs["staged"])')

    assert regular_tag < regular_move
    assert duplicate_tag < duplicate_move


def test_v324_add_shows_tag_in_place_helper_invokes_tag_writer(monkeypatch, tmp_path):
    folder = tmp_path / "readyForXfer" / "Artist 2001-02-03 Venue Boston MA"
    folder.mkdir(parents=True)
    audio = folder / "01 Song.flac"
    audio.write_bytes(b"fake")
    info = folder / "info.txt"
    info.write_text("Artist\n2001-02-03\nVenue\nBoston, MA\n\n01 Song\n", encoding="utf-8")
    generated = tmp_path / "setlists" / "Artist 2001-02-03 Venue Boston MA.txt"
    generated.parent.mkdir()
    generated.write_text("01 Song\n", encoding="utf-8")
    config = IPL.Config(
        debug=False,
        silent=True,
        TLOHome=str(tmp_path),
        compliant=True,
        tag_during_inventory=True,
        tag_copy_during_inventory=False,
        rename_compliantly=False,
    )
    record = {
        "show_name": "Artist 2001-02-03 Venue Boston MA",
        "artist": "Artist",
        "date": "2001-02-03",
        "venue": "Venue",
        "location": "Boston MA",
        "main_dir_path": str(folder),
        "setlist_file": str(info),
        "setlist_files_json": json.dumps([str(info)]),
        "music_dirs_json": json.dumps([str(folder)]),
    }
    calls = []

    def fake_tag_group_with_record(config_arg, group, record_arg, **kwargs):
        calls.append((config_arg, group, record_arg, kwargs))
        return T.empty_tag_stats() | {"groups": 1, "tagged": 1}

    monkeypatch.setattr(T, "tag_group_with_record", fake_tag_group_with_record)

    stats = U._tag_add_shows_folder_in_place(config, str(folder), record, str(generated))

    assert stats["groups"] == 1
    assert stats["tagged"] == 1
    assert len(calls) == 1
    assert calls[0][1]["main_dir_path"] == os.path.normpath(str(folder))
    assert calls[0][2].show_name == "Artist 2001-02-03 Venue Boston MA"
    tag_logs = list((tmp_path / "logs").glob("tags*.txt"))
    assert tag_logs
    assert "ADD_SHOWS_TAG_IN_PLACE" in tag_logs[0].read_text(encoding="utf-8")



def test_v324_update_checker_prefers_platform_complete_fallback(monkeypatch):
    import tlo_github_updates as G

    release = {
        "tag_name": "v1.1-build329",
        "name": "TLO v1.2 Build 335",
        "assets": [
            {"name": "TLO_V1.1Build329_complete_Windows.zip", "browser_download_url": "https://example.invalid/win", "size": 1},
            {"name": "TLO_V1.1Build329_complete_Linux.zip", "browser_download_url": "https://example.invalid/linux", "size": 1},
            {"name": "TLO_V1.1Build329_complete_macOS.zip", "browser_download_url": "https://example.invalid/mac", "size": 1},
        ],
    }
    monkeypatch.setattr(G.sys, "platform", "linux")
    asset, kind, platform = G._choose_asset(release, 329)

    assert asset["name"] == "TLO_V1.1Build329_complete_Linux.zip"
    assert kind == "complete"
    assert platform == "linux"


# --------------------------------------------------------------------------- #
# v325/v330 - GUI TLOHome text boxes removed, read-only labels shown, myTLO precedence preserved.
# --------------------------------------------------------------------------- #

def test_v330_inventory_and_search_guis_do_not_build_tlohome_input_boxes():
    inventory_source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    search_source = Path(__file__).with_name("tlo-gsi.py").read_text(encoding="utf-8")

    inventory_build = inventory_source[inventory_source.index("    def _build(self):"):inventory_source.index("    def _run_after_menu_closes(self, callback):")]
    search_build = search_source[search_source.index("    def _build_main_window(self) -> None:"):search_source.index("    def _run_after_menu_closes")]

    assert 'text="TLOHome"' not in inventory_build
    assert 'self.vars["TLOHome"]' not in inventory_source
    assert 'text=f"TLOHome: {tlohome_display}"' in inventory_build
    assert 'text=f"TLOHome: {self.paths.tlohome}"' in search_build
    assert "tlohome_entry" not in search_source
    assert "tlohome_var" not in search_source


def test_v330_inventory_gui_uses_non_gui_tlohome_resolver_with_mytlo_precedence():
    source = Path(__file__).with_name("tlo-ggi.py").read_text(encoding="utf-8")
    resolver = source[source.index("    def _resolve_gui_tlo_home"):source.index("    def _show_about_from_menu")]
    build_config = source[source.index("    def _build_config(self, *, for_add_shows=False):"):source.index("    def _pause_inventory(self):")]

    assert "resolve_inventory_tlo_home" in resolver
    assert "my_tlo=self._cli_my_tlo_value()" in resolver
    assert "tlo_home=self._cli_tlo_home_value()" in resolver
    assert "self._resolve_gui_tlo_home(error_type=ValueError)" in build_config


def test_v330_search_cli_keeps_mytlo_before_tlohome_before_env(tmp_path, monkeypatch):
    import importlib.util

    module_path = Path(__file__).with_name("tlo-gsi.py")
    spec = importlib.util.spec_from_file_location("tlo_gsi_v330", module_path)
    search_gui = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = search_gui
    spec.loader.exec_module(search_gui)

    env_home = tmp_path / "env"
    tlo_home = tmp_path / "tlo"
    my_home = tmp_path / "my"
    for home in (env_home, tlo_home, my_home):
        home.mkdir()
    monkeypatch.setenv("TLOHome", str(env_home))

    resolved, _find = search_gui.parse_cli_args(["--TLOHome", str(tlo_home), "--myTLO", str(my_home)])

    assert resolved == my_home


# --------------------------------------------------------------------------- #
# v330 - physical-drive scheduling, delete backup commands, and TLOHome labels.
# --------------------------------------------------------------------------- #

def test_v330_named_volumes_on_same_physical_drive_are_one_serial_work_group(monkeypatch):
    import walk_trees_lib as W

    physical = {
        "/mnt/d/named-a": "disk-1",
        "/mnt/e/named-b": "disk-1",
        "/mnt/f/named-c": "disk-2",
    }
    monkeypatch.setattr(W, "resolve_physical_drive_id", lambda path: physical.get(path, ""))
    named = [
        ("/mnt/d/named-a", "", "Archive A", "d", "1", "w"),
        ("/mnt/e/named-b", "", "Archive B", "e", "2", "w"),
        ("/mnt/f/named-c", "", "Archive C", "f", "3", "w"),
    ]

    groups = W._group_named_volume_items_by_physical_drive(named)

    assert [[item[0] for item in group] for group in groups] == [
        ["/mnt/d/named-a", "/mnt/e/named-b"],
        ["/mnt/f/named-c"],
    ]


def test_v330_add_shows_volume_path_preserves_drive_from_storage_field():
    assert U._format_add_shows_volume_path("[Backup-1]E:", "Artist 2001-02-03 Venue") == "[Backup-1] E:\\Artist 2001-02-03 Venue"
    assert U._format_add_shows_volume_path("[Backup-1]/mnt/e", "Artist 2001-02-03 Venue") == "[Backup-1] /mnt/e/Artist 2001-02-03 Venue"
    assert U._format_add_shows_volume_path("Backup-1", "Artist 2001-02-03 Venue") == "[Backup-1] Artist 2001-02-03 Venue"


def test_v330_delete_backup_bat_has_no_echo_off_and_uses_bootlist_rooted_path(tmp_path):
    script = tmp_path / "deleteBackupFolders.bat"

    U._append_delete_command(str(script), "E:\\Artist 2001-02-03 Venue")

    text = script.read_text(encoding="utf-8")
    assert not text.startswith("@echo off")
    assert 'rmdir /s /q "E:\\Artist 2001-02-03 Venue"' in text


def test_v330_delete_backup_path_requires_drive_or_root_from_bootlist_row():
    assert U._delete_path_from_bootlist_volume_path("[Backup-1] E:\\Artist 2001-02-03 Venue") == os.path.normpath("E:\\Artist 2001-02-03 Venue")
    assert U._delete_path_from_bootlist_volume_path("[Backup-1] /mnt/e/Artist 2001-02-03 Venue") == os.path.normpath("/mnt/e/Artist 2001-02-03 Venue")
    assert U._delete_path_from_bootlist_volume_path("[Backup-1] /Volumes/Backup-1/Artist 2001-02-03 Venue") == os.path.normpath("/Volumes/Backup-1/Artist 2001-02-03 Venue")
    assert U._delete_path_from_bootlist_volume_path("[Backup-1] /Artist 2001-02-03 Venue") == ""
    assert U._delete_path_from_bootlist_volume_path("[Backup-1] Artist 2001-02-03 Venue") == ""

# --------------------------------------------------------------------------- #
# v330 - Review-report hardening and hygiene fixes.
# --------------------------------------------------------------------------- #

def test_v330_update_download_host_is_github_pinned():
    import tlo_github_updates as G

    assert G._download_host_allowed("https://github.com/owner/repo/releases/download/x.zip") is True
    assert G._download_host_allowed("https://objects.githubusercontent.com/github-production-release-asset") is True
    assert G._download_host_allowed("https://example.invalid/release.zip") is False
    assert G._download_host_allowed("http://github.com/owner/repo/releases/download/x.zip") is False


def test_v330_update_destination_uses_sanitized_basename_and_warns_without_digest(monkeypatch, tmp_path):
    import tlo_github_updates as G

    release = {
        "tag_name": "v1.2-build336",
        "name": "TLO v1.2 Build 336",
        "assets": [
            {
                "name": "../TLO_V1.2Build336_update_Linux.zip",
                "browser_download_url": "https://github.com/onaracstlo-lab/TradersLittleOrganizer/releases/download/v336/TLO.zip",
                "size": 1,
            }
        ],
    }
    monkeypatch.setattr(G.sys, "platform", "linux")
    monkeypatch.setattr(G, "_fetch_latest_release", lambda owner, repo: release)
    monkeypatch.setattr(G, "_downloads_dir", lambda: tmp_path)
    seen = []

    def fake_download(asset, destination):
        seen.append(destination)
        destination.write_bytes(b"x")
        return True

    monkeypatch.setattr(G, "_download_asset", fake_download)
    result = G.check_for_updates(tmp_path / "TLOHome", manual=True)

    assert result.status == "downloaded"
    assert seen == [tmp_path / "TLO_V1.2Build336_update_Linux.zip"]
    assert result.path == str(tmp_path / "TLO_V1.2Build336_update_Linux.zip")
    assert "verified the downloaded file size only" in result.message


def test_v330_artist_query_cache_is_bounded():
    import tlo_artist_db as A

    matcher = A.ArtistMatcher(db_path=":memory:", query_cache_max_entries=3)
    for idx in range(10):
        A.lookup_artist_master_with_status(f"No Match Artist {idx}", matcher)

    assert len(matcher.query_cache) == 3
    assert "no match artist 0" not in "|".join(matcher.query_cache.keys())


def test_v330_setlistfm_rate_limit_releases_lock_before_waiting():
    source = Path(__file__).with_name("tlo_setlistfm_lookup.py").read_text(encoding="utf-8")
    wait_block = source[source.index("def wait_for_rate_limit") : source.index("def api_get")]

    assert "Release it, wait, and" in wait_block
    assert "time.sleep(wait_time)" in wait_block
    assert "continue" in wait_block

# --------------------------------------------------------------------------- #
# v331 - Convert shn also works without tagging in Full Inventory/Add Shows. v332 adds per-entry active switch settings to meta*.log records.
# --------------------------------------------------------------------------- #

def test_v331_full_inventory_converts_shn_without_tagging(monkeypatch, tmp_path):
    from tlo_models import ShowMetadata

    source = tmp_path / "Artist 2001-02-03 Venue Boston MA"
    source.mkdir()
    shn = source / "01 Song.shn"
    shn.write_bytes(b"fake shn")
    group = {
        "main_dir_path": str(source),
        "main_dir_name": source.name,
        "music_dirs": [str(source)],
        "music_files": [str(shn)],
        "setlist_files": [],
        "txt_files": [],
    }
    record = ShowMetadata(
        group_number=1,
        main_dir_name=source.name,
        main_dir_path=str(source),
        setlist_file="",
        music_file_count=1,
        artist="Artist",
        date="2001-02-03",
        venue="Venue",
        city="Boston",
        region="MA",
        location="Boston MA",
        show_name="Artist 2001-02-03 Venue Boston MA",
        music_dirs=[str(source)],
        setlist_files=[],
    )

    class CaptureLogs:
        def __init__(self):
            self.tag_messages = []
            self.conflict_messages = []

        def tag(self, fmt, *args):
            self.tag_messages.append(fmt % args if args else fmt)

        def conflicts(self, fmt, *args):
            self.conflict_messages.append(fmt % args if args else fmt)

    logs = CaptureLogs()
    config = IPL.Config(
        debug=False,
        silent=True,
        TLOHome=str(tmp_path),
        current_search_path=str(source),
        tag_during_inventory=False,
        tag_copy_during_inventory=False,
        convert_shn=True,
    )
    config.logs = logs

    def fake_convert(path_name, emit=None):
        target = Path(path_name).with_suffix(".flac")
        target.write_bytes(b"fake flac")
        Path(path_name).unlink()
        if emit:
            emit(f"  CONVERTED SHN: {Path(path_name).name} -> {target.name} | converter=test")
        return str(target)

    monkeypatch.setattr(P, "_build_groups_from_search_path", lambda _config, _path: [group])
    monkeypatch.setattr(P, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], []))
    monkeypatch.setattr(P, "_log_group", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(P, "_log_show_metadata", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(T, "convert_shn_to_flac", fake_convert)
    monkeypatch.setattr(T, "tag_group_with_record", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("tag writer should not run")))

    records = P.process_groups_for_search_path_v2(config, artist_matcher=None)

    assert records == [record]
    assert not shn.exists()
    assert (source / "01 Song.flac").is_file()
    assert any("CONVERT_SHN_DURING_INVENTORY: enabled | tagging=disabled" in message for message in logs.tag_messages)
    assert any("CONVERT_SHN_SUMMARY: folders=1 converted_files=1 file_errors=0" in message for message in logs.tag_messages)
    assert not any("TAG_SUMMARY" in message for message in logs.tag_messages)


def test_v331_add_shows_converts_shn_without_tagging(monkeypatch, tmp_path):
    folder = tmp_path / "readyForXfer" / "Artist 2001-02-03 Venue Boston MA"
    folder.mkdir(parents=True)
    shn = folder / "01 Song.shn"
    shn.write_bytes(b"fake shn")
    record = {
        "show_name": "Artist 2001-02-03 Venue Boston MA",
        "artist": "Artist",
        "date": "2001-02-03",
        "venue": "Venue",
        "location": "Boston MA",
        "main_dir_path": str(folder),
        "music_dirs_json": json.dumps([str(folder)]),
    }
    config = IPL.Config(
        debug=False,
        silent=True,
        TLOHome=str(tmp_path),
        compliant=True,
        tag_during_inventory=False,
        tag_copy_during_inventory=False,
        convert_shn=True,
    )

    def fake_convert(path_name, emit=None):
        target = Path(path_name).with_suffix(".flac")
        target.write_bytes(b"fake flac")
        Path(path_name).unlink()
        if emit:
            emit(f"  CONVERTED SHN: {Path(path_name).name} -> {target.name} | converter=test")
        return str(target)

    monkeypatch.setattr(T, "convert_shn_to_flac", fake_convert)
    monkeypatch.setattr(T, "tag_group_with_record", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("tag writer should not run")))

    stats = U._tag_add_shows_folder_in_place(config, str(folder), record, "")

    assert stats["groups"] == 1
    assert stats["tagged"] == 0
    assert stats["errors"] == 0
    assert not shn.exists()
    assert (folder / "01 Song.flac").is_file()
    tag_logs = list((tmp_path / "logs").glob("tags*.txt"))
    assert tag_logs
    all_tag_text = "\n".join(path.read_text(encoding="utf-8") for path in (tmp_path / "logs").glob("tag*.txt"))
    assert "ADD_SHOWS_CONVERT_SHN_ONLY" in all_tag_text
    assert "ADD_SHOWS_CONVERT_SHN_SUMMARY: folders=1 converted_files=1 file_errors=0" in all_tag_text
    assert "ADD_SHOWS_TAG_IN_PLACE" not in all_tag_text

# v332 - meta logs include per-entry active switch settings

def test_v332_switch_line_reports_active_inventory_settings():
    cfg = SimpleNamespace(
        compliant=True,
        compliant_artist_mode="as-is",
        tag_during_inventory=True,
        tag_copy_during_inventory=False,
        tag_copy_and_delete_path="",
        current_path_copy_destination="",
        current_path_copy_delete_destination="",
        rename_compliantly=True,
        convert_shn=True,
        etree_lookup=True,
        setlistfm_lookup=False,
    )
    line = P._format_switches_log_line(cfg, action="Full Inventory")
    assert line.startswith("Switches -- ")
    assert "Action: Full Inventory" in line
    assert "Compliant: yes" in line
    assert "Tag: yes" in line
    assert "Tag in Place: yes" in line
    assert "Rename Compliantly: yes" in line
    assert "Convert shn: yes" in line
    assert "etreeDB: yes" in line
    assert "setlist.fm: no" in line
    assert "Compliant Artist Mode: as-is" in line


def test_v332_meta_log_lines_include_switch_line(tmp_path):
    record = P.ShowMetadata(
        group_number=1,
        main_dir_name="Switch Show",
        main_dir_path=str(tmp_path),
        setlist_file="",
        music_file_count=0,
        show_name="Switch Show",
    )
    switch_line = "Switches -- Compliant: yes; Tag: yes;"
    lines = P._format_show_metadata_log_lines(record, [], switches_line=switch_line)
    assert lines[0] == "SHOW_NAME: Switch Show"
    assert lines[1] == "SHOW_IN_CONFLICT: no"
    assert lines[2] == switch_line


def test_v332_add_shows_metadata_log_includes_switches(tmp_path):
    cfg = SimpleNamespace(
        TLOHome=str(tmp_path),
        logs=None,
        compliant=True,
        compliant_artist_mode="master",
        tag_during_inventory=True,
        tag_copy_during_inventory=True,  # ignored by Add Shows but captured as inactive by this log path
        tag_copy_and_delete_path="",
        current_path_copy_destination="",
        current_path_copy_delete_destination="",
        rename_compliantly=True,
        convert_shn=True,
        etree_lookup=False,
        setlistfm_lookup=False,
        silent=True,
        debug=False,
    )
    record = {
        "show_name": "Artist 1977-05-08 Venue City ST",
        "main_dir_path": str(tmp_path / "readyForXfer" / "Artist 1977-05-08 Venue City ST"),
        "setlist_file": "",
        "artist": "Artist",
        "date": "1977-05-08",
    }
    U._log_add_shows_metadata(cfg, record, record["main_dir_path"], "[Backup]E:", "Add Shows staged new show")
    meta_logs = sorted((tmp_path / "logs").glob("meta*.log"))
    assert meta_logs, "Add Shows metadata log was not created"
    text = meta_logs[0].read_text(encoding="utf-8")
    assert "SHOW_NAME: Artist 1977-05-08 Venue City ST" in text
    assert "Switches -- Action: Add Shows; Compliant: yes; Tag: yes;" in text
    assert "Tag in Place: yes" in text
    assert "Tag Copy: no" in text
    assert "Tag Copy/Delete Original: no" in text
    assert "Convert shn: yes" in text
    assert "OBSERVATION: Add Shows staged new show" in text

# v333 - Artist in Album tagging option

def test_v333_album_tag_defaults_to_artist_prefix():
    import tlo_tag_lib as T
    cfg = SimpleNamespace(compliant=False, artist_in_album=True)
    record = SimpleNamespace(artist="Miles Davis", date="1970-04-09", venue="Fillmore West", location="San Francisco CA")
    assert T._album_for_record(cfg, record) == "Miles Davis 1970-04-09 Fillmore West San Francisco CA"


def test_v333_album_tag_without_artist_prefix_when_unchecked():
    import tlo_tag_lib as T
    cfg = SimpleNamespace(compliant=False, artist_in_album=False)
    record = SimpleNamespace(artist="Miles Davis", date="1970-04-09", venue="Fillmore West", location="San Francisco CA")
    assert T._album_for_record(cfg, record) == "1970-04-09 Fillmore West San Francisco CA"


def test_v333_artist_in_album_option_defaults_checked_and_cli_can_disable():
    from tlo_options import OPTIONS_BY_FIELD, GUI_CHECKBOX_OPTIONS, add_options_to_parser
    import argparse
    option = OPTIONS_BY_FIELD["artist_in_album"]
    assert option.default is True
    assert option.gui_label == "Artist in Album Tag"
    assert option in GUI_CHECKBOX_OPTIONS
    parser = argparse.ArgumentParser()
    add_options_to_parser(parser, fields=("artist_in_album",))
    assert parser.parse_args([]).artist_in_album is True
    assert parser.parse_args(["--no-artist-in-album"]).artist_in_album is False


# v334 - Main GUI checkbox order and Artist in Album Tag label

def test_v334_main_gui_checkbox_layout_is_two_rows_by_four_columns():
    from tlo_options import OPTIONS_BY_FIELD, GUI_CHECKBOX_OPTIONS
    expected = {
        "etree_lookup": (0, 0, "etreeDB"),
        "compliant": (0, 1, "Compliant"),
        "tag_during_inventory": (0, 2, "Tag in Place"),
        "artist_in_album": (0, 3, "Artist in Album Tag"),
        "setlistfm_lookup": (1, 0, "setlist.fm"),
        "rename_compliantly": (1, 1, "Rename Compliantly"),
        "tag_copy_during_inventory": (1, 2, "Tag Copy"),
        "convert_shn": (1, 3, "Convert shn"),
    }
    assert len(GUI_CHECKBOX_OPTIONS) == 8
    for field, (row, col, label) in expected.items():
        option = OPTIONS_BY_FIELD[field]
        assert (option.gui_row, option.gui_col, option.gui_label) == (row, col, label)


def test_v334_main_gui_configures_four_checkbox_columns():
    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    for column in range(4):
        assert f"checkbox_frame.columnconfigure({column}, weight=0)" in source


# --------------------------------------------------------------------------- #
# v335 - Native Windows helper subprocesses remain hidden in GUI one-file builds
# --------------------------------------------------------------------------- #

def test_v335_hidden_windows_subprocess_kwargs_include_no_window_flags(monkeypatch):
    import tlo_tag_lib as taglib

    class FakeStartupInfo:
        def __init__(self):
            self.dwFlags = 0
            self.wShowWindow = None

    monkeypatch.setattr(taglib.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(taglib.subprocess, "STARTUPINFO", FakeStartupInfo, raising=False)
    monkeypatch.setattr(taglib.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(taglib.subprocess, "SW_HIDE", 0, raising=False)

    kwargs = taglib._hidden_windows_subprocess_kwargs("nt")

    assert kwargs["creationflags"] == 0x08000000
    assert kwargs["startupinfo"].dwFlags & 1
    assert kwargs["startupinfo"].wShowWindow == 0
    assert taglib._hidden_windows_subprocess_kwargs("posix") == {}


def test_v335_shn_converter_passes_hidden_windows_subprocess_options(monkeypatch, tmp_path):
    import tlo_tag_lib as taglib

    shn = tmp_path / "01 Song One.shn"
    shn.write_bytes(b"fake shn")
    monkeypatch.setattr(taglib, "_bundled_ffmpeg_executable", lambda: "C:/app/ffmpeg.exe")
    monkeypatch.setattr(taglib, "_hidden_windows_subprocess_kwargs", lambda: {"creationflags": 12345})
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        Path(command[-1]).write_bytes(b"fake flac")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(taglib.subprocess, "run", fake_run)
    taglib.convert_shn_to_flac(str(shn), emit=lambda _text: None)

    assert captured["creationflags"] == 12345


def test_v335_physical_drive_powershell_passes_hidden_windows_subprocess_options(monkeypatch):
    import tlo_volume_label as volume

    monkeypatch.setattr(volume, "_hidden_windows_subprocess_kwargs", lambda: {"creationflags": 67890})
    captured = {}

    def fake_run(command, **kwargs):
        captured.update(kwargs)
        return SimpleNamespace(stdout="7\n", stderr="")

    monkeypatch.setattr(volume.subprocess, "run", fake_run)
    assert volume._run_command(["powershell.exe", "-NoProfile", "-Command", "echo 7"]) == "7"
    assert captured["creationflags"] == 67890
