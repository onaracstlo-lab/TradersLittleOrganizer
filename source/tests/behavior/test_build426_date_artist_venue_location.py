"""Build 427 regressions for guarded Date Artist Venue Location paths."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as P

pytestmark = pytest.mark.behavior

__version__ = "v440"


def _matcher(*, genesis_collision=False):
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {
        "genesis": {"Genesis", "Genesis Alternate"} if genesis_collision else {"Genesis"},
        "palace": {"Palace"},
        "stage": {"Stage"},
    }
    matcher.master_aliases = {
        "Genesis": ["Genesis"],
        "Palace": ["Palace"],
        "Stage": ["Stage"],
    }
    matcher.master_norms = {
        "Genesis": {"genesis"},
        "Palace": {"palace"},
        "Stage": {"stage"},
    }
    if genesis_collision:
        matcher.master_aliases["Genesis Alternate"] = ["Genesis"]
        matcher.master_norms["Genesis Alternate"] = {"genesis"}
    return matcher


def _config(tmp_path: Path):
    return SimpleNamespace(
        compliant=False,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        thorough_setlist_matching=False,
        tlo_dbs_dir=str(tmp_path),
        debug=False,
    )


def _group(show_dir: Path, tag_artist=""):
    samples = [{"artist": tag_artist, "albumartist": ""}] if tag_artist else []
    return {
        "group_number": 1,
        "main_dir_name": show_dir.name,
        "main_dir_path": str(show_dir),
        "setlist_file": "",
        "setlist_files": [],
        "music_dirs": [str(show_dir)],
        "music_file_count": 1,
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": samples,
        "flac_tag_artist_values": [tag_artist] if tag_artist else [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


def test_build426_matches_date_artist_venue_location_with_required_venue():
    match, collisions = P._match_date_artist_venue_location(
        "1997-04-05 Genesis Old Pub London England", _matcher()
    )

    assert collisions == []
    assert match is not None
    assert match["artist_master"] == "Genesis"
    assert match["date_norm"] == "1997-04-05"
    assert match["venue"] == "Old Pub"
    assert match["city"] == "London"
    assert match["country"] == "England"


@pytest.mark.parametrize(
    "folder",
    [
        "1990-07-10 Palace Melbourne Australia",
        "1990-07-10 The Palace Melbourne Australia",
        "1997-04-05 Genesis London England",
    ],
)
def test_build426_rejects_date_artist_location_when_no_venue_remains(folder):
    match, collisions = P._match_date_artist_venue_location(folder, _matcher())
    assert match is None
    assert collisions == []


def test_build426_requires_artist_to_begin_immediately_after_date():
    match, collisions = P._match_date_artist_venue_location(
        "1997-04-05 Old Pub Genesis London England", _matcher()
    )
    assert match is None
    assert collisions == []


def test_build426_refuses_ambiguous_artist_prefix():
    match, collisions = P._match_date_artist_venue_location(
        "1997-04-05 Genesis Old Pub London England",
        _matcher(genesis_collision=True),
    )
    assert match is None
    assert collisions == ["Genesis", "Genesis Alternate"]


def test_build426_full_path_only_case_resolves_expected_show(tmp_path: Path):
    show_dir = tmp_path / "1997-04-05 Genesis Old Pub London England"
    show_dir.mkdir()

    record, dates, unresolved = P._extract_metadata_for_group(
        _config(tmp_path), _group(show_dir), _matcher()
    )

    assert record.artist == "Genesis"
    assert record.date == "1997-04-05"
    assert record.venue == "Old Pub"
    assert record.location == "London, England"
    assert record.show_name == "Genesis 1997-04-05 Old Pub London, England"
    assert any(item["source"] == "date_artist_venue_location" for item in dates)
    assert not unresolved
    assert any("Date Artist Venue Location path pattern matched" in item for item in record.observations)


def test_build426_matching_tag_can_supply_artist_without_blocking_path_fields(tmp_path: Path):
    show_dir = tmp_path / "1997-04-05 Genesis Old Pub London England"
    show_dir.mkdir()

    record, _dates, unresolved = P._extract_metadata_for_group(
        _config(tmp_path), _group(show_dir, tag_artist="Genesis"), _matcher()
    )

    assert record.artist == "Genesis"
    assert record.date == "1997-04-05"
    assert record.venue == "Old Pub"
    assert record.location == "London, England"
    assert not unresolved


def test_build426_no_venue_guard_prevents_palace_artist_false_positive(tmp_path: Path):
    show_dir = tmp_path / "1990-07-10 Palace Melbourne Australia"
    show_dir.mkdir()

    record, _dates, unresolved = P._extract_metadata_for_group(
        _config(tmp_path), _group(show_dir), _matcher()
    )

    assert record.artist != "Palace"
    assert record.artist == ""
    assert unresolved


def test_build426_requirements_and_manual_document_rule():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v440.docx")
    requirements_text = "\n".join(paragraph.text for paragraph in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v440.rtf").read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "Current document version: v440 (v1.5 Build 440)." in requirements_text
    assert "Date Artist Venue Location" in requirements_text
    assert "1997-04-05 Genesis Old Pub London England" in requirements_text
    assert "a venue must remain after removing the artist" in requirements_text.lower()
    assert "Version v1.5 Build 440" in manual_text
    assert "Date Artist Venue Location" in manual_text
    assert "1997-04-05 Genesis Old Pub London England" in manual_text
    assert "a venue must remain after removing the artist" in manual_text.lower()
