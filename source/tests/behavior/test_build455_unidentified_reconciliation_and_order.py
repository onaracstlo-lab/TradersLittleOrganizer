"""Build 455: persistent unidentified lists reconcile in encounter order."""

from pathlib import Path

import pytest
import tlo_postprocess as PP

pytestmark = pytest.mark.behavior

__version__ = "v455"


def test_unidentified_shows_preserve_existing_then_current_encounter_order(tmp_path: Path):
    target = tmp_path / "unidentifiedShows.txt"
    target.write_text("/z/first\n/a/second\n", encoding="utf-8")

    PP._write_unidentified_shows(
        str(tmp_path),
        ["/m/new", "/a/second", "/b/last", "/m/new"],
    )

    assert target.read_text(encoding="utf-8").splitlines() == [
        "/z/first", "/a/second", "/m/new", "/b/last"
    ]


def test_unidentified_shows_remove_prior_entry_when_current_run_resolves_it(tmp_path: Path):
    target = tmp_path / "unidentifiedShows.txt"
    target.write_text("/keep/old\n/music/now-resolved\n/keep/later\n", encoding="utf-8")

    PP._write_unidentified_shows(
        str(tmp_path),
        ["/new/unresolved"],
        addressed_paths=["/music/now-resolved"],
    )

    assert target.read_text(encoding="utf-8").splitlines() == [
        "/keep/old", "/keep/later", "/new/unresolved"
    ]


def test_current_unresolved_path_wins_over_addressed_alias(tmp_path: Path):
    target = tmp_path / "unidentifiedShows.txt"
    target.write_text("/music/still-unresolved\n", encoding="utf-8")

    PP._write_unidentified_shows(
        str(tmp_path),
        ["/music/still-unresolved"],
        addressed_paths=["/music/still-unresolved"],
    )

    assert target.read_text(encoding="utf-8").splitlines() == ["/music/still-unresolved"]


def test_addressed_paths_include_original_path_after_rename():
    records = [
        {
            "show_name": "Artist 2020-01-01 Venue City, ST",
            "main_dir_path": "/music/Artist 2020-01-01 Venue City, ST",
            "original_main_dir_path": "/music/bad old folder",
        },
        {
            "show_name": "",
            "main_dir_path": "/music/still unresolved",
            "original_main_dir_path": "",
        },
    ]

    assert PP._collect_addressed_paths_from_metadata(records) == [
        "/music/Artist 2020-01-01 Venue City, ST",
        "/music/bad old folder",
    ]


def test_artists_not_in_database_preserve_encounter_order_and_casefold_dedupe(tmp_path: Path):
    target = tmp_path / "artistsNotInDatabase.txt"
    target.write_text("Zulu Group\nexample master group\n", encoding="utf-8")

    PP._write_artists_not_in_database(
        str(tmp_path),
        ["Example Master Group", "Alpha All-Star Band", "alpha all-star band", "Beta Group"],
    )

    assert target.read_text(encoding="utf-8").splitlines() == [
        "Zulu Group",
        "example master group",
        "Alpha All-Star Band",
        "Beta Group",
    ]


def test_corrupt_files_dropdown_is_only_slightly_wider_than_build453():
    source = (Path(__file__).resolve().parents[2] / "tlo-ggi.py").read_text(encoding="utf-8")
    block = source[source.index("self.corrupt_files_combo = ttk.Combobox"):]
    block = block[:block.index("self.corrupt_files_combo.grid")]
    assert "width=18" in block
    assert "width=20" not in block
