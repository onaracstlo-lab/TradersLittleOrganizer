"""Build 490 regressions for guarded non-compliant Artist + Place + Date tails."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as P

pytestmark = pytest.mark.behavior

__version__ = "v493"


def _matcher():
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"todd snider": {"Todd Snider"}}
    matcher.master_aliases = {"Todd Snider": ["Todd Snider"]}
    matcher.master_norms = {"Todd Snider": {"toddsnider"}}
    return matcher


def _config(tmp_path: Path, *, compliant=False):
    return SimpleNamespace(
        compliant=compliant,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=compliant,
        compliant_artist_mode="as_is" if compliant else "master",
        etree_lookup=False,
        setlistfm_lookup=False,
        thorough_setlist_matching=False,
        tlo_dbs_dir=str(tmp_path),
        venue_reference_db_file=str(tmp_path / "venues.txt"),
        debug=False,
    )


def _group(show_dir: Path):
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
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


def _extract(tmp_path: Path, folder: str, *, compliant=False):
    show_dir = tmp_path / folder
    show_dir.mkdir()
    return P._extract_metadata_for_group(
        _config(tmp_path, compliant=compliant), _group(show_dir), _matcher()
    )


def test_build490_todd_snider_literal_sdb_recovers_predate_venue_and_location(tmp_path: Path):
    record, dates, unresolved = _extract(
        tmp_path,
        "Todd Snider Skipper's Smokehouse, Tampa, FL 2005-04-16 sdb",
    )

    assert record.artist == "Todd Snider"
    assert record.date == "2005-04-16"
    assert record.venue == "Skipper's Smokehouse"
    assert record.location == "Tampa, FL"
    assert record.qualifier == ""
    assert record.show_name == "Todd Snider 2005-04-16 Skipper's Smokehouse Tampa, FL"
    assert not unresolved
    assert any(item["source"] == "artist_place_date_technical_suffix" for item in dates)


def test_build490_existing_terminal_performance_qualifier_can_activate_same_guarded_fallback(tmp_path: Path):
    record, _dates, unresolved = _extract(
        tmp_path,
        "Todd Snider Skipper's Smokehouse, Tampa, FL 2005-04-16 set 1",
    )

    assert record.artist == "Todd Snider"
    assert record.venue == "Skipper's Smokehouse"
    assert record.location == "Tampa, FL"
    assert record.qualifier == "Set 1"
    assert record.show_name == "Todd Snider 2005-04-16 Skipper's Smokehouse Tampa, FL (Set 1)"
    assert not unresolved


def test_build490_unrecognized_postdate_title_text_still_does_not_activate_fallback(tmp_path: Path):
    record, _dates, _unresolved = _extract(
        tmp_path,
        "Todd Snider Skipper's Smokehouse, Tampa, FL 2005-04-16 Deluxe",
    )

    assert record.artist == "Todd Snider"
    assert record.date == "2005-04-16"
    assert record.venue == ""
    assert record.location == ""
    assert "Skipper's Smokehouse" not in record.show_name


def test_build490_normal_artist_date_order_keeps_existing_interpretation(tmp_path: Path):
    record, _dates, unresolved = _extract(
        tmp_path,
        "Todd Snider 2005-04-16 Skipper's Smokehouse, Tampa, FL",
    )

    assert record.artist == "Todd Snider"
    assert record.date == "2005-04-16"
    assert record.venue == "Skipper's Smokehouse"
    assert record.location == "Tampa, FL"
    assert record.show_name == "Todd Snider 2005-04-16 Skipper's Smokehouse Tampa, FL"
    assert not unresolved


def test_build490_compliant_mode_is_deliberately_unchanged_for_noncompliant_name(tmp_path: Path):
    record, _dates, unresolved = _extract(
        tmp_path,
        "Todd Snider Skipper's Smokehouse, Tampa, FL 2005-04-16 sdb",
        compliant=True,
    )

    assert record.artist == "Todd Snider Skipper's Smokehouse, Tampa, FL"
    assert record.date == "2005-04-16"
    assert record.venue == "sdb"
    assert record.location == ""
    assert record.album_name == "sdb"
    assert record.show_name == "Todd Snider Skipper's Smokehouse, Tampa, FL 2005-04-16 sdb"
    assert not unresolved


def test_build490_requirements_and_manual_document_guarded_extension():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    req = "\n".join(
        paragraph.text
        for paragraph in Document(root / "TLO_Inventory_Requirements_Working_v493.docx").paragraphs
    )
    manual = (root / "TLO_Inventory_User_Manual_v493.rtf").read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "Current document version: v493 (v1.7 Build 493)." in req
    assert "Todd Snider Skipper's Smokehouse, Tampa, FL 2005-04-16 sdb" in req
    assert "The literal SDB spelling is accepted only inside this guarded fallback" in req
    assert "Compliant mode is unchanged" in req
    assert "Version v1.7 Build 493" in manual
    assert "Todd Snider Skipper's Smokehouse, Tampa, FL 2005-04-16 sdb" in manual
    assert "Existing Artist Date ... parsing retains precedence, and Compliant mode is unchanged." in manual
