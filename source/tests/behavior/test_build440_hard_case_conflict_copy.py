"""Build 440 regressions for hard-case identity conflicts and copy/delete gating."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as P
import tlo_postprocess as PP
import tlo_tag_lib as T

pytestmark = pytest.mark.behavior

__version__ = "v440"


def _matcher(*masters):
    matcher = ArtistMatcher(db_path="")
    for master in masters:
        matcher.exact_map.setdefault(master.casefold(), set()).add(master)
        matcher.master_aliases[master] = [master]
        matcher.master_norms[master] = {"".join(ch for ch in master.casefold() if ch.isalpha())}
    return matcher


def _config(tmp_path: Path):
    return SimpleNamespace(
        compliant=False,
        current_volume_label="B&J M",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        thorough_setlist_matching=False,
        tlo_dbs_dir=str(tmp_path),
        debug=False,
        rename_compliantly=True,
        tag_copy_and_delete_path="",
    )


def _taj_hard_case(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "venues.txt").write_text("Capitol Theatre\n", encoding="utf-8")
    show_dir = (
        tmp_path
        / "Mahal, Taj"
        / "1990"
        / "Taj Mahal 1990-01-28 Charleston, W.V. (Mt. Stage) (FM)"
    )
    show_dir.mkdir(parents=True)
    setlist = show_dir / "Taj Mahal 1990-01-28 info.txt"
    setlist.write_text(
        "\n".join(
            [
                "Taj Mahal",
                "Jan. 28, 1990",
                "Capitol Theatre",
                "Charleston, W.V.",
                "(Mountain Stage)",
                "",
                "Source: FM Broadcast > Cassette Master (TDK SA90)",
                "",
                "(Setlist) (36:24)",
                "01. The Bourgeois Blues",
                "02. Blue Light Boogie",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    # Stand-in files are sufficient for path transfer tests; metadata is passed
    # in through the sampled tag structure used by the extractor.
    (show_dir / "Taj Mahal 1990-01-28 t01.flac").write_bytes(b"one")
    (show_dir / "Taj Mahal 1990-01-28 t02.flac").write_bytes(b"two")
    group = {
        "group_number": 1,
        "main_dir_name": show_dir.name,
        "main_dir_path": str(show_dir),
        "setlist_file": str(setlist),
        "setlist_files": [str(setlist)],
        "music_dirs": [str(show_dir)],
        "music_file_count": 2,
        "music_files": [
            str(show_dir / "Taj Mahal 1990-01-28 t01.flac"),
            str(show_dir / "Taj Mahal 1990-01-28 t02.flac"),
        ],
        "music_sample_files": [],
        "flac_tag_samples": [
            {
                "file": str(show_dir / "Taj Mahal 1990-01-28 t01.flac"),
                "artist": "",
                "albumartist": "",
                "album": "",
                "date": "",
            },
            {
                "file": str(show_dir / "Taj Mahal 1990-01-28 t02.flac"),
                "artist": "Van Morrison",
                "albumartist": "",
                "album": "Piazza del Duomo, Pistoia, Italy",
                "date": "1989-06-29",
            },
        ],
        "flac_tag_artist_values": ["Van Morrison"],
        "flac_tag_album_values": ["Piazza del Duomo, Pistoia, Italy"],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": ["1989-06-29"],
    }
    return show_dir, setlist, group


def test_build440_dotted_month_date_is_recognized():
    matches = P._find_date_matches("Jan. 28, 1990", allow_slash=True)
    assert [item["normalized"] for item in matches] == ["1990-01-28"]


def test_build440_taj_hard_case_rejects_foreign_flac_identity(tmp_path: Path):
    _show_dir, _setlist, group = _taj_hard_case(tmp_path)
    record, date_matches, unresolved = P._extract_metadata_for_group(
        _config(tmp_path), group, _matcher("Taj Mahal", "Van Morrison")
    )

    assert record.artist == "Taj Mahal"
    assert record.date == "1990-01-28"
    assert record.venue == "Capitol Theatre"
    assert record.location == "Charleston, WV"
    assert record.show_name == "Taj Mahal 1990-01-28 Capitol Theatre Charleston, WV (Mt. Stage) (FM)"
    assert record.show_in_conflict is False
    assert record.conflicts == []
    assert unresolved == []
    assert any(item["normalized"] == "1989-06-29" for item in date_matches)
    assert any("conflicting DATE tag ignored" in item for item in record.observations)
    assert not any(candidate.value == "Van Morrison" for candidate in record.evidence.get("artist", []))


def test_build440_dotted_state_location_is_extracted_from_selected_setlist(tmp_path: Path):
    _show_dir, setlist, _group = _taj_hard_case(tmp_path)
    from tlo_setlist_metadata_lookup import extract_setlist_venue_location

    result = extract_setlist_venue_location(str(setlist), str(tmp_path))
    assert result.artist == "Taj Mahal"
    assert result.venue == "Capitol Theatre"
    assert result.city == "Charleston"
    assert result.region == "WV"


def test_build440_conflicted_blank_show_is_not_synthesized_for_bootlist():
    record = {
        "show_name": "",
        "show_in_conflict": "yes",
        "artist": "Van Morrison",
        "date": "",
        "venue": "Capitol Theatre",
        "location": "",
        "parentheticals": "(Mt. Stage) (FM)",
        "main_dir_path": r"G:\\M\\Mahal, Taj\\1990\\Taj Mahal 1990-01-28 Charleston, W.V. (Mt. Stage) (FM)",
    }
    prepared = PP._prepare_record_for_bootlist_export(record)
    assert prepared["show_name"] == ""
    assert prepared.get("_postprocess_skip_row") == "yes"
    assert "xxxx-xx-xx" not in prepared["show_name"]


def test_build440_recovered_hard_case_executes_cross_filesystem_copy_delete(tmp_path: Path, monkeypatch):
    show_dir, _setlist, group = _taj_hard_case(tmp_path / "source")
    config = _config(tmp_path / "source")
    record, _date_matches, unresolved = P._extract_metadata_for_group(
        config, group, _matcher("Taj Mahal", "Van Morrison")
    )
    assert unresolved == []
    assert not P._record_is_unidentified_for_mutation(record, unresolved)

    destination = tmp_path / "destination"
    destination.mkdir()
    config.tag_copy_and_delete_path = str(destination)
    monkeypatch.setattr(T, "_paths_on_same_filesystem", lambda *_args, **_kwargs: False)

    moved_group, moved_record = T.prepare_inventory_copy_delete_target(config, group, record)

    expected = destination / "Taj Mahal 1990-01-28 Capitol Theatre Charleston, WV (Mt. Stage) (FM)"
    assert not show_dir.exists()
    assert expected.is_dir()
    assert (expected / "Taj Mahal 1990-01-28 info.txt").is_file()
    assert Path(moved_group["main_dir_path"]) == expected
    assert Path(moved_record.main_dir_path) == expected
