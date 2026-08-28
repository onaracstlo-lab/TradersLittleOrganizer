"""Build 414 regressions for location-safe artist headers and bare-number tracks."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior

from inventory_parser_lib import Config
from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as P
import tlo_setlist_metadata_lookup as M
import tlo_tag_lib as T

__version__ = "v415"


INFO = """Chick Corea and Herbie Hancock
Concert Hall
Kennedy Center
Washington, DC
April 10, 2015
Church CA-14 cardioid microphones  >  Church Ugly II pre-amp > Sony PCM-10

total time 93:09

Chick Corea and Herbie Hancock - pianos

1
2
3
4
5
6
7
8
9
10
11
"""


def _matcher(include_herbie=True, ambiguous_herbie=False):
    matcher = ArtistMatcher(db_path="")
    exact = {
        "chick corea": {"Chick Corea"},
        "washington": {"Washington"},
    }
    aliases = {
        "Chick Corea": ["Chick Corea"],
        "Washington": ["Washington"],
    }
    norms = {
        "Chick Corea": {"chickcorea"},
        "Washington": {"washington"},
    }
    if include_herbie:
        exact["herbie hancock"] = {"Herbie Hancock", "Herbie Hancock Alt"} if ambiguous_herbie else {"Herbie Hancock"}
        aliases["Herbie Hancock"] = ["Herbie Hancock"]
        norms["Herbie Hancock"] = {"herbiehancock"}
        if ambiguous_herbie:
            aliases["Herbie Hancock Alt"] = ["Herbie Hancock"]
            norms["Herbie Hancock Alt"] = {"herbiehancock"}
    matcher.exact_map = exact
    matcher.master_aliases = aliases
    matcher.master_norms = norms
    return matcher


def _write_info(tmp_path: Path) -> Path:
    (tmp_path / "venues.txt").write_text("Kennedy Center\nConcert Hall\n", encoding="utf-8")
    info = tmp_path / "corea-hancock2015-04-10.txt"
    info.write_text(INFO, encoding="utf-8")
    return info


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


def test_build414_five_line_header_keeps_artist_and_deeper_named_venue(tmp_path: Path):
    info = _write_info(tmp_path)
    result = M.extract_setlist_venue_location(str(info), str(tmp_path))

    assert result.artist == "Chick Corea and Herbie Hancock"
    assert result.artist_source == "setlist_metadata:STRUCTURED_UNLABELED_ARTIST_HEADER"
    assert result.venue == "Kennedy Center"
    assert result.city == "Washington"
    assert result.region == "DC"


def test_build414_collaboration_resolves_only_when_every_component_is_unique():
    candidate, masters = P._resolve_collaborative_artist_header(
        "Chick Corea and Herbie Hancock", _matcher(), SimpleNamespace(as_is_artist_name=False)
    )
    assert candidate == "Chick Corea and Herbie Hancock"
    assert masters == ["Chick Corea", "Herbie Hancock"]

    candidate, masters = P._resolve_collaborative_artist_header(
        "Chick Corea and Herbie Hancock", _matcher(include_herbie=False), SimpleNamespace(as_is_artist_name=False)
    )
    assert candidate == ""
    assert masters == []


def test_build414_ambiguous_collaboration_component_does_not_guess():
    candidate, masters = P._resolve_collaborative_artist_header(
        "Chick Corea and Herbie Hancock", _matcher(ambiguous_herbie=True), SimpleNamespace(as_is_artist_name=False)
    )
    assert candidate == ""
    assert masters == []


def test_build414_location_tail_artist_hit_is_rejected():
    long_part = "My Recording 2015-04-10 Kennedy Center Washington, DC"
    assert P._path_artist_hit_is_location_tail(long_part, "Washington") is True
    hits, _collisions = P._db_backed_artist_hits_for_path_part(long_part, _matcher())
    assert ("Washington", "Washington") not in hits


def test_build414_exact_artist_directory_named_washington_remains_eligible():
    exact_hits, _collisions = P._db_backed_artist_hits_for_path_part("Washington", _matcher())
    assert ("Washington", "Washington") in exact_hits


def test_build414_full_metadata_extraction_uses_collaboration_not_location_artist(tmp_path: Path):
    info = _write_info(tmp_path)
    show_dir = tmp_path / "My Recording 2015-04-10 Kennedy Center Washington, DC"
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
        "music_file_count": 11,
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": ["My Recording"],
        "flac_tag_album_values": ["My Recording 2015-04-10 Kennedy Center Washington, DC"],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }

    record, _dates, _unresolved = P._extract_metadata_for_group(_config(tmp_path), group, _matcher())

    assert record.artist == "Chick Corea and Herbie Hancock"
    assert record.date == "2015-04-10"
    assert record.venue == "Kennedy Center"
    assert record.location == "Washington, DC"
    assert record.show_name == "Chick Corea and Herbie Hancock 2015-04-10 Kennedy Center Washington, DC"
    assert any("collaboration resolved from unique Artist DB components" in item for item in record.observations)


def test_build414_exact_count_bare_number_block_becomes_unknown_tracks(tmp_path: Path):
    info = _write_info(tmp_path)
    rows = T._exact_count_bare_number_track_candidate(str(info), 11)
    assert len(rows) == 11
    assert [row["original_number"] for row in rows] == list(range(1, 12))
    assert [row["normalized_number"] for row in rows] == list(range(1, 12))
    assert {row["title"] for row in rows} == {"Unknown"}


def test_build414_final_selection_writes_unknown_not_numeric_titles(tmp_path: Path):
    info = _write_info(tmp_path)
    audio = []
    for idx in range(1, 12):
        path = tmp_path / f"corea-hancock2015-04-10_{idx:02d}.flac"
        path.write_bytes(b"")
        audio.append(str(path))
    config = Config(debug=False, silent=True, TLOHome=str(tmp_path))

    rows, source, error = T._select_tracks_for_tagging(
        config, {"setlist_file": str(info), "path": str(tmp_path)}, audio, record=None
    )

    assert error is None
    assert source == "setlist"
    assert len(rows) == 11
    assert [row["title"] for row in rows] == ["Unknown"] * 11
    assert not any(row["title"] == str(idx) for idx, row in enumerate(rows, start=1))


def test_build414_bare_number_count_mismatch_is_neutral(tmp_path: Path):
    info = _write_info(tmp_path)
    assert T._exact_count_bare_number_track_candidate(str(info), 10) == []
    assert T._exact_count_bare_number_track_candidate(str(info), 12) == []


def test_build414_requirements_and_manual_document_rule():
    # Updated to v414 during the release/document sweep.
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v415.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual_text = (root / "TLO_Inventory_User_Manual_v415.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v415 (v1.4 Build 415)." in req_text
    assert "Washington, DC" in req_text
    assert "Chick Corea and Herbie Hancock" in req_text
    assert "bare-number" in req_text.casefold()
    assert "Unknown" in req_text
    assert "Version v1.4 Build 415" in manual_text
    assert "Build 414 - Location-safe artist headers and bare-number tracks" in manual_text
    assert "Washington" in manual_text
    assert "Unknown" in manual_text
