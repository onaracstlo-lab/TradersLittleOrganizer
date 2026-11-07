"""Build 621: comma-delimited city and evidence-based ambiguous date resolution."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_phase23_v2 as phase
from tlo_artist_db import ArtistMatcher

pytestmark = pytest.mark.behavior


def _matcher():
    matcher = ArtistMatcher(db_path="")
    names = ("Jethro", "Jethro Tull", "Derby", "Twiddle", "The Catalyst")
    matcher.exact_map = {name.casefold(): {name} for name in names}
    matcher.master_aliases = {name: [name] for name in names}
    matcher.master_norms = {name: {"".join(ch for ch in name.casefold() if ch.isalnum())} for name in names}
    return matcher


def _extract(tmp_path: Path, name="Jethro Tull, Derby 02-04-07", setlist="", *,
             etree=False, setlistfm=False, compliant=False):
    folder = tmp_path / name
    folder.mkdir(exist_ok=True)
    setlist_path = folder / "info.txt"
    if setlist:
        setlist_path.write_text(setlist, encoding="utf-8")
    config = SimpleNamespace(
        compliant=compliant, current_volume_label="", current_slam="",
        as_is_artist_name=False, compliant_artist_mode="master",
        etree_lookup=etree, setlistfm_lookup=setlistfm,
        tlo_dbs_dir=str(tmp_path), TLOHome=str(tmp_path), debug=False,
    )
    group = {
        "group_number": 1, "main_dir_name": name,
        "main_dir_path": str(folder),
        "setlist_file": str(setlist_path) if setlist else "",
        "setlist_files": [str(setlist_path)] if setlist else [],
        "music_dirs": [str(folder)], "music_file_count": 1,
        "flac_tag_samples": [], "flac_tag_artist_values": [],
        "flac_tag_album_values": [], "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }
    return phase._extract_metadata_for_group(config, group, _matcher())


def _etree_hit(date, city="Derby", artist="Jethro Tull", venue="Assembly Rooms"):
    return SimpleNamespace(
        artist=artist, normalized_date=date, venue=venue, city=city,
        state="", performance_id=22,
    )


def _fm_hit(date, city="Derby", artist="Jethro Tull", venue="Assembly Rooms"):
    y, m, d = date.split("-")
    return SimpleNamespace(
        artist=artist, event_date=f"{d}-{m}-{y}", venue=venue,
        city=city, state="", state_code="", country="England",
        country_code="GB", setlists=(), setlist_url="https://example.invalid/show",
    )


def test_explicit_iso_date_and_single_word_city_without_venue(tmp_path):
    record, _dates, issues = _extract(tmp_path, "Jethro Tull, Derby 2007-02-04")
    assert (record.artist, record.date, record.venue, record.city, record.show_name) == (
        "Jethro Tull", "2007-02-04", "", "Derby", "Jethro Tull 2007-02-04 Derby"
    )
    assert not issues


def test_selected_setlist_resolves_us_ambiguous_numeric_date(tmp_path):
    record, dates, issues = _extract(tmp_path, setlist="Jethro Tull\nDate: 2007-02-04\nCity: Derby\n1 Aqualung\n")
    assert (record.artist, record.date, record.city, record.venue) == ("Jethro Tull", "2007-02-04", "Derby", "")
    assert record.show_name == "Jethro Tull 2007-02-04 Derby"
    assert not issues
    assert any(item["normalized"] == "2007-02-04" for item in dates)


def test_selected_setlist_resolves_dmy_date_not_in_original_parser(tmp_path):
    record, _dates, issues = _extract(tmp_path, setlist="Jethro Tull\nDate: 2007-04-02\nCity: Derby\n1 Aqualung\n")
    assert (record.artist, record.date, record.city) == ("Jethro Tull", "2007-04-02", "Derby")
    assert not issues


def test_without_corroboration_keeps_date_ambiguous_but_artist_and_city(tmp_path):
    record, dates, issues = _extract(tmp_path)
    assert (record.artist, record.date, record.venue, record.city) == ("Jethro Tull", "", "", "Derby")
    assert not record.show_name
    assert any("date conflict" in reason for reason in issues)
    assert {x["normalized"] for x in dates if x["normalized"].count("-") == 2} >= {
        "2002-04-07", "2007-02-04", "2007-04-02"
    }


@pytest.mark.parametrize("source", ["etree", "setlistfm"])
def test_one_online_candidate_with_matching_city_resolves(tmp_path, monkeypatch, source):
    calls = []
    def etree(artist, date, **kwargs):
        calls.append(("etree", date))
        return [_etree_hit(date)] if date == "2007-02-04" else []
    def fm(artist, date, **kwargs):
        calls.append(("fm", date))
        return [_fm_hit(date)] if date == "2007-02-04" else []
    monkeypatch.setattr(phase, "lookup_venue_and_location", etree)
    monkeypatch.setattr(phase, "lookup_setlistfm_venue_and_location", fm)
    record, _dates, issues = _extract(tmp_path, etree=source == "etree", setlistfm=source == "setlistfm")
    assert (record.artist, record.date, record.city) == ("Jethro Tull", "2007-02-04", "Derby")
    assert record.show_name == ("Jethro Tull 2007-02-04 Assembly Rooms Derby, England"
                                if source == "setlistfm" else
                                "Jethro Tull 2007-02-04 Assembly Rooms Derby")
    assert not issues
    assert len(calls) >= 3
    assert len({date for _source, date in calls}) == 3


def test_both_online_sources_must_not_disagree(tmp_path, monkeypatch):
    def etree(artist, date, **kwargs):
        return [_etree_hit(date)] if date == "2002-04-07" else []
    def fm(artist, date, **kwargs):
        return [_fm_hit(date)] if date == "2007-02-04" else []
    monkeypatch.setattr(phase, "lookup_venue_and_location", etree)
    monkeypatch.setattr(phase, "lookup_setlistfm_venue_and_location", fm)
    record, _dates, issues = _extract(tmp_path, etree=True, setlistfm=True)
    assert record.date == ""
    assert any("date conflict" in reason for reason in issues)
    assert any("remained unresolved" in obs for obs in record.observations)


def test_two_online_date_hits_stay_unresolved(tmp_path, monkeypatch):
    def etree(artist, date, **kwargs):
        return [_etree_hit(date)] if date in {"2002-04-07", "2007-02-04"} else []
    monkeypatch.setattr(phase, "lookup_venue_and_location", etree)
    record, _dates, issues = _extract(tmp_path, etree=True)
    assert not record.date
    assert any("date conflict" in reason for reason in issues)


def test_online_hit_in_other_city_does_not_validate(tmp_path, monkeypatch):
    def etree(artist, date, **kwargs):
        return [_etree_hit(date, city="London")] if date == "2007-02-04" else []
    monkeypatch.setattr(phase, "lookup_venue_and_location", etree)
    record, _dates, issues = _extract(tmp_path, etree=True)
    assert not record.date
    assert any("date conflict" in reason for reason in issues)


def test_wrong_artist_hit_is_not_validation(tmp_path, monkeypatch):
    def etree(artist, date, **kwargs):
        return [_etree_hit(date, artist="Derby")] if date == "2007-02-04" else []
    monkeypatch.setattr(phase, "lookup_venue_and_location", etree)
    record, _dates, issues = _extract(tmp_path, etree=True)
    assert not record.date
    assert any("date conflict" in reason for reason in issues)


def test_online_exception_keeps_conflict(tmp_path, monkeypatch):
    def etree(artist, date, **kwargs):
        raise RuntimeError("temporarily unavailable")
    monkeypatch.setattr(phase, "lookup_venue_and_location", etree)
    record, _dates, issues = _extract(tmp_path, etree=True)
    assert not record.date
    assert any("date conflict" in reason for reason in issues)


@pytest.mark.parametrize("name", [
    "Jethro Tull, Live 2007-02-04",
    "Jethro Tull, Greatest Hits 2007-02-04",
    "Unknown Band, Derby 2007-02-04",
    "Jethro Tull, Derby 2007-02-04 Deluxe",
    "Jethro Tull, New Venue, Derby 2007-02-04",
])
def test_unstructured_or_unmatched_folders_do_not_use_comma_city_rule(tmp_path, name):
    record, _dates, _issues = _extract(tmp_path, name)
    assert not any("guarded Artist, City Date fallback" in obs for obs in record.observations)


def test_compliant_mode_does_not_invoke_new_rule(tmp_path):
    record, _dates, _issues = _extract(tmp_path, compliant=True)
    assert not any("guarded Artist, City Date fallback" in obs for obs in record.observations)


def test_no_online_calls_when_setlist_resolves_date(tmp_path, monkeypatch):
    def failure(*args, **kwargs):
        raise AssertionError("online date probing should not run")
    monkeypatch.setattr(phase, "_resolve_ambiguous_dates_from_online", failure)
    record, _dates, issues = _extract(tmp_path,
        setlist="Jethro Tull\nDate: 2007-02-04\nCity: Derby\n1 Aqualung\n", etree=False, setlistfm=False)
    assert record.date == "2007-02-04" and not issues


def test_original_lucinda_not_affected(tmp_path):
    record, _dates, issues = _extract(tmp_path, "Jethro Tull, Derby 2007-02-04")
    assert record.show_name == "Jethro Tull 2007-02-04 Derby"
    assert not issues
