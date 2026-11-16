"""Build 668: multilingual textual dates and conservative Compliant disc siblings."""

from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase

pytestmark = pytest.mark.behavior

MONTHS = {
    "de": ("Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September", "Oktober", "November", "Dezember"),
    "fr": ("janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août", "septembre", "octobre", "novembre", "décembre"),
    "it": ("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"),
}


@pytest.mark.parametrize("language,words", MONTHS.items())
def test_all_twelve_months_in_three_languages(language, words):
    assert len(words) == 12, language
    for month, word in enumerate(words, 1):
        for text in (f"01. {word} 2022", f"01 {word} 2022", f"{word} 01, 2022"):
            matches = phase._find_date_matches(text)
            assert any(match["normalized"] == f"2022-{month:02d}-01" for match in matches), (language, text, matches)


@pytest.mark.parametrize("value,expected", [
    ("01. Juni 2022", "2022-06-01"),
    ("1. März 2022", "2022-03-01"),
    ("1 Maerz 2022", "2022-03-01"),
    ("1 Marz 2022", "2022-03-01"),
    ("1er juin 2022", "2022-06-01"),
    ("1ère juin 2022", "2022-06-01"),
    ("01 fevrier 2022", "2022-02-01"),
    ("01 août 2022", "2022-08-01"),
    ("01 aout 2022", "2022-08-01"),
    ("1º maggio 2022", "2022-05-01"),
    ("1° giugno 2022", "2022-06-01"),
    ("14APR01", "2001-04-14"),
    ("01. June 2022", "2022-06-01"),
])
def test_normalization_and_existing_english_forms(value, expected):
    assert expected in {m["normalized"] for m in phase._find_date_matches(value)}, value


@pytest.mark.parametrize("value", ["31 febbraio 2022", "30 février 2022", "31 Juni 2022", "29 Februar 2021"])
def test_invalid_calendar_dates_remain_rejected(value):
    assert not any(m["normalized"].endswith("-31") or m["normalized"].endswith("-30")
                   or m["normalized"] == "2021-02-29" for m in phase._find_date_matches(value))


def _groups(tmp_path: Path, show: str, names: tuple[str, ...], *, compliant=True, extra_parent_audio=False):
    root = tmp_path / "library"
    parent = root / show
    files = []
    for name in names:
        directory = parent / name
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "01 audio.flac"
        path.write_bytes(b"audio")
        files.append(path)
    if extra_parent_audio:
        direct = parent / "00 intro.flac"
        direct.write_bytes(b"intro")
        files.append(direct)
    log = tmp_path / "complete_paths.txt"
    log.write_text("SEARCH_PATH: " + str(root) + "\n" + "\n".join(map(str, files)) + "\n", encoding="utf-8")
    config = SimpleNamespace(
        compliant=compliant, performance_mode="balanced",
        logs=SimpleNamespace(paths=SimpleNamespace(complete_paths=str(log))),
    )
    return parent, phase._build_groups_from_search_path(config, str(root))


@pytest.mark.parametrize("parts", [
    ("Disc 01", "Disc 02"),
    ("CD1", "CD2"),
    ("Set 1", "Set 2"),
    ("Disk 01", "Disc 02"),
    ("Disc one", "Disc two"),
    ("Part 1", "Part 2"),
])
def test_dated_show_disc_siblings_become_one_parent_group_without_setlist(tmp_path, parts):
    parent, groups = _groups(tmp_path, "Kinks 1987-05-28 Dortmund Westfalenhalle", parts)
    assert len(groups) == 1
    group = groups[0]
    assert group["main_dir_path"] == str(parent)
    assert group["main_dir_name"] == parent.name
    assert group["aggregation_reason"] == "compliant_disc_set_siblings"
    assert group["music_file_count"] == 2
    assert {Path(d).name for d in group["music_dirs"]} == set(parts)
    assert not group["setlist_file"]
    assert not group["flac_tag_samples"]


@pytest.mark.parametrize("parts", [
    ("Disc 01",),
    ("Disc 01", "Disc 03"),
    ("Disc 01", "CD 02"),
    ("Disc 01", "Other Band 1999-01-02 Somewhere"),
    ("Disc 01", "Disc 02", "Other Band 1999-01-02 Somewhere"),
])
def test_dangerous_or_incomplete_groups_are_never_aggregated(tmp_path, parts):
    parent, groups = _groups(tmp_path, "Kinks 1987-05-28 Dortmund Westfalenhalle", parts)
    assert len(groups) == len(parts)
    assert all(group["main_dir_path"] != str(parent) for group in groups)


def test_collection_root_not_promoted(tmp_path):
    parent, groups = _groups(tmp_path, "Unidentified Disc Collection", ("Disc 01", "Disc 02"))
    assert len(groups) == 2
    assert all(group["main_dir_path"] != str(parent) for group in groups)


def test_direct_parent_music_not_double_counted(tmp_path):
    parent, groups = _groups(tmp_path, "Kinks 1987-05-28 Dortmund Westfalenhalle", ("Disc 01", "Disc 02"), extra_parent_audio=True)
    assert len(groups) == 3
    assert all(group["aggregation_reason"] != "compliant_disc_set_siblings" for group in groups)


def test_noncompliant_existing_disc_grouping_not_regressed(tmp_path):
    parent, groups = _groups(tmp_path, "Kinks 1987-05-28 Dortmund Westfalenhalle", ("Disc 01", "Disc 02"), compliant=False)
    assert len(groups) == 1
    assert groups[0]["main_dir_path"] == str(parent)


def test_kinks_disc_pair_is_actually_identified_by_compliant_metadata_without_setlist(tmp_path):
    from tlo_artist_db import ArtistMatcher

    show, groups = _groups(tmp_path, "Kinks 1987-05-28 Dortmund Westfalenhalle", ("Disc 01", "Disc 02"))
    assert len(groups) == 1
    group = dict(groups[0], group_number=1)
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"kinks": {"The Kinks"}, "the kinks": {"The Kinks"}}
    matcher.master_aliases = {"The Kinks": ["The Kinks", "Kinks"]}
    matcher.master_norms = {"The Kinks": {"thekinks", "kinks"}}
    config = SimpleNamespace(
        compliant=True, compliant_artist_mode="master", proper_grammar=False,
        as_is_artist_name=False, current_volume_label="",
    )
    record, dates, unresolved = phase._extract_metadata_for_group_compliant(config, group, matcher)
    assert record.artist == "The Kinks"
    assert record.date == "1987-05-28"
    assert record.main_dir_path == str(show)
    assert record.show_name.startswith("The Kinks 1987-05-28")
    assert not record.setlist_file
    assert not unresolved
    assert len(group["music_dirs"]) == 2
