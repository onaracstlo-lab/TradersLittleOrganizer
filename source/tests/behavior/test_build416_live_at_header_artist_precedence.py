"""Build 416 regressions for Live-at header interpretation and artist precedence."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as P
import tlo_setlist_metadata_lookup as M

__version__ = "v423"


INFO = """Great vintage stuff!!

AL DiMeola Group GROUP

Live at Gürzenich, Cologne, Germany, 1978-10-13

Source: FM Broadcast> BASF Metal Tape C90 > trade (many years ago!!)

Sound: excellent (listen to mp3 samples)

TRACKS:

Egyptian Danza
Chasin' the Voodoo
Dark Eye Tango
Lady of Rome, Sister of Brazil
Fantasia Suite for Two Guitars
Midnight Tango
Race With Devil on Spanish Highway

LINEUP:

Al DiMeola - guitar
Philippe Saisse - keyboards
Wlodek Gulgowski -keyboards
Tim Landers - bass
Robbie Gonzalez - drums
Eddie Colon - timbales and percussion
"""


def _matcher():
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {
        "al dimeola group": {"Al DiMeola Group"},
        "wrong artist": {"Wrong Artist"},
    }
    matcher.master_aliases = {
        "Al DiMeola Group": ["Al DiMeola Group"],
        "Wrong Artist": ["Wrong Artist"],
    }
    matcher.master_norms = {
        "Al DiMeola Group": {"aldimeolagroup"},
        "Wrong Artist": {"wrongartist"},
    }
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
        tlo_dbs_dir=str(tmp_path),
        debug=False,
    )


def _write_info(tmp_path: Path) -> Path:
    (tmp_path / "venues.txt").write_text("Gürzenich\n", encoding="utf-8")
    info = tmp_path / "dimeola1978-10-13.txt"
    info.write_text(INFO, encoding="utf-8")
    return info


def test_build416_live_at_header_beats_introductory_prose(tmp_path: Path):
    info = _write_info(tmp_path)
    result = M.extract_setlist_venue_location(str(info), str(tmp_path))

    assert result.artist == "AL DiMeola Group"
    assert result.artist_source == "setlist_metadata:STRUCTURED_UNLABELED_ARTIST_HEADER"
    assert result.artist_confidence >= 94
    assert result.venue == "Gürzenich"
    assert result.city == "Cologne"
    assert result.country == "Germany"
    assert result.source == "setlist_metadata:LOCATION_LIVE_AT_VENUE_LOCATION"
    assert "Great Vintage Stuff" not in result.artist


def test_build416_duplicate_terminal_group_is_collapsed_conservatively():
    assert M._normalize_artist_header_text("AL DiMeola Group GROUP") == "AL DiMeola Group"
    assert M._normalize_artist_header_text("Example Band BAND") == "Example Band"
    assert M._normalize_artist_header_text("Al DiMeola Group") == "Al DiMeola Group"
    assert M._normalize_artist_header_text("The Group") == "The Group"


def test_build416_db_confirmed_live_at_artist_overrides_weaker_path_artist(tmp_path: Path):
    info = _write_info(tmp_path)
    show_dir = tmp_path / "Wrong Artist 1978-10-13"
    show_dir.mkdir()
    local_info = show_dir / info.name
    local_info.write_text(INFO, encoding="utf-8")

    group = {
        "group_number": 1,
        "main_dir_name": show_dir.name,
        "main_dir_path": str(show_dir),
        "setlist_file": str(local_info),
        "setlist_files": [str(local_info)],
        "music_dirs": [str(show_dir)],
        "music_file_count": 7,
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }

    record, _dates, _unresolved = P._extract_metadata_for_group(_config(tmp_path), group, _matcher())

    assert record.artist == "Al DiMeola Group"
    assert record.date == "1978-10-13"
    assert record.venue == "Gurzenich"
    assert record.city == "Cologne"
    assert record.country == "Germany"
    assert record.show_name.startswith("Al DiMeola Group 1978-10-13 Gurzenich Cologne")
    assert any(
        "DB-confirmed structured setlist artist overrode weaker path artist: Wrong Artist -> Al DiMeola Group" in item
        for item in record.observations
    )


def test_build416_live_at_header_does_not_strip_a_single_group_suffix(tmp_path: Path):
    info = _write_info(tmp_path)
    text = INFO.replace("AL DiMeola Group GROUP", "Al DiMeola Group")
    info.write_text(text, encoding="utf-8")
    result = M.extract_setlist_venue_location(str(info), str(tmp_path))
    assert result.artist == "AL DiMeola Group"


def test_build416_requirements_and_manual_document_rule():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v423.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v423.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v423 (v1.5 Build 423)." in req_text
    assert "Artist / Live at Venue" in req_text
    assert "AL DiMeola Group GROUP" in req_text
    assert "Gürzenich" in req_text
    assert "Build 416 revision" in req_text
    assert "Version v1.5 Build 423" in manual_text
    assert "Artist followed by Live at Venue" in manual_text
