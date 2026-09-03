"""Build 424 regressions for partial dates at dash-album boundaries."""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

from docx import Document
import pytest

import tlo_phase23_v2 as phase
from tlo_artist_db import ArtistMatcher

pytestmark = pytest.mark.behavior
__version__ = "v426"

ROOT = Path(__file__).resolve().parents[2]


def _ray_price_matcher() -> ArtistMatcher:
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"ray price": {"Ray Price"}}
    matcher.master_aliases = {"Ray Price": ["Ray Price"]}
    matcher.master_norms = {"Ray Price": {"rayprice"}}
    return matcher


def _config() -> SimpleNamespace:
    return SimpleNamespace(
        compliant=False,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=False,
        setlistfm_lookup=False,
        setlistfm_upgrade=False,
    )


def _group(folder_name: str) -> dict:
    path = os.path.join(os.sep, "music", folder_name)
    return {
        "group_number": 1,
        "main_dir_name": folder_name,
        "main_dir_path": path,
        "setlist_file": "",
        "music_file_count": 1,
        "setlist_files": [],
        "music_dirs": [path],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }


def test_partial_end_first_date_at_string2_edge_is_normalized_and_removed():
    parsed = phase._analyze_dash_string2_before_album(
        "Gilley's - Pasadena, Texas - xx-xx-81"
    )

    assert parsed["date"] == "1981-xx-xx"
    assert parsed["venue"] == "Gilley's"
    assert parsed["city"] == "Pasadena"
    assert parsed["region"] == "TX"
    assert parsed["country"] == ""


def test_partial_date_inside_album_title_does_not_force_performance_mode():
    assert phase._analyze_dash_string2_before_album(
        "Archive xx-xx-81 Deluxe Edition"
    ) == {}


def test_ray_price_folder_resolves_structured_partial_date_show():
    folder = "Ray Price - Gilley's - Pasadena, Texas - xx-xx-81"

    record, date_matches, unresolved = phase._extract_metadata_for_group(
        _config(), _group(folder), _ray_price_matcher()
    )

    assert unresolved == []
    assert record.artist == "Ray Price"
    assert record.date == "1981-xx-xx"
    assert record.venue == "Gilley's"
    assert record.location == "Pasadena, TX"
    assert record.album_name == ""
    assert record.show_name == "Ray Price 1981-xx-xx Gilley's Pasadena, TX"
    assert any(match.get("normalized") == "1981-xx-xx" for match in date_matches)
    assert any(
        "contained performance date/location evidence" in observation
        for observation in record.observations
    )


def test_build424_documentation_integrates_partial_boundary_date_rule():
    requirements = Document(ROOT / "TLO_Inventory_Requirements_Working_v426.docx")
    requirements_text = "\n".join(paragraph.text for paragraph in requirements.paragraphs)
    manual_text = (ROOT / "TLO_Inventory_User_Manual_v426.rtf").read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "Current document version: v426 (v1.5 Build 426)." in requirements_text
    assert "supported normalized partial date when it occurs at the beginning or end of String2" in requirements_text
    assert "Ray Price 1981-xx-xx Gilley's Pasadena, TX" in requirements_text
    assert "Version v1.5 Build 426" in manual_text
    assert "a supported partial date when that date is at the beginning or end of String2" in manual_text
    assert "Ray Price 1981-xx-xx Gilley's Pasadena, TX" in manual_text
