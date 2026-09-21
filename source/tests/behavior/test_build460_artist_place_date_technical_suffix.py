"""Build 460 regressions for Artist + place + Date + technical-suffix folders."""

from pathlib import Path
from types import SimpleNamespace

import pytest

from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as P

pytestmark = pytest.mark.behavior

__version__ = "v468"


def _matcher(*, include_rtf=True):
    matcher = ArtistMatcher(db_path="")
    matcher.exact_map = {"return to forever": {"Return to Forever"}}
    matcher.master_aliases = {"Return to Forever": ["Return to Forever"]}
    matcher.master_norms = {"Return to Forever": {"returntoforever"}}
    if include_rtf:
        matcher.exact_map["rtf"] = {"Return to Forever"}
        matcher.master_aliases["Return to Forever"].append("RTF")
        matcher.master_norms["Return to Forever"].add("rtf")
    return matcher


def _config(tmp_path: Path, *, etree=False):
    return SimpleNamespace(
        compliant=False,
        current_volume_label="",
        current_slam="",
        as_is_artist_name=False,
        compliant_artist_mode="master",
        etree_lookup=etree,
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


def test_build460_guarded_match_uses_db_alias_and_existing_date_parser():
    match, collisions = P._match_artist_place_date_technical_suffix(
        "RTF Paris 7 March 76 flac16", _matcher()
    )

    assert collisions == []
    assert match is not None
    assert match["artist_raw"] == "RTF"
    assert match["artist_master"] == "Return to Forever"
    assert match["place_hint"] == "Paris"
    assert match["date_norm"] == "1976-03-07"
    assert match["technical_suffix"].lower() == "flac16"


def test_build460_does_not_construct_initialism_when_alias_is_absent():
    match, collisions = P._match_artist_place_date_technical_suffix(
        "RTF Paris 7 March 76 flac16", _matcher(include_rtf=False)
    )

    assert match is None
    assert collisions == []


def test_build460_full_case_retains_single_word_place_only_as_last_resort(tmp_path: Path):
    show_dir = tmp_path / "RTF Paris 7 March 76 flac16"
    show_dir.mkdir()

    record, dates, unresolved = P._extract_metadata_for_group(
        _config(tmp_path), _group(show_dir), _matcher()
    )

    assert record.artist == "Return to Forever"
    assert record.date == "1976-03-07"
    assert record.venue == ""
    assert record.location == "Paris"
    assert record.show_name == "Return to Forever 1976-03-07 Paris"
    assert not unresolved
    assert any(item["source"] == "artist_place_date_technical_suffix" for item in dates)
    assert any("guarded Artist Place Date TechnicalSuffix" in item for item in record.observations)
    assert any("retained single-word pre-date place hint" in item for item in record.observations)


def test_build460_exact_venues_file_match_is_used_as_venue(tmp_path: Path):
    (tmp_path / "venues.txt").write_text("Lone Star Cafe\n", encoding="utf-8")
    show_dir = tmp_path / "RTF Lone Star Cafe 7 March 76 flac16"
    show_dir.mkdir()

    record, _dates, unresolved = P._extract_metadata_for_group(
        _config(tmp_path), _group(show_dir), _matcher()
    )

    assert record.artist == "Return to Forever"
    assert record.date == "1976-03-07"
    assert record.venue == "Lone Star Cafe"
    assert record.location == ""
    assert record.show_name == "Return to Forever 1976-03-07 Lone Star Cafe"
    assert not unresolved


def test_build460_structured_pre_date_location_uses_existing_string2_rules(tmp_path: Path):
    show_dir = tmp_path / "RTF Old Pub London England 7 March 76 flac16"
    show_dir.mkdir()

    record, _dates, unresolved = P._extract_metadata_for_group(
        _config(tmp_path), _group(show_dir), _matcher()
    )

    assert record.artist == "Return to Forever"
    assert record.date == "1976-03-07"
    assert record.venue == "Old Pub"
    assert record.location == "London, England"
    assert record.show_name == "Return to Forever 1976-03-07 Old Pub London, England"
    assert not unresolved


def test_build460_unknown_multiword_pre_date_text_is_not_promoted_to_location(tmp_path: Path):
    show_dir = tmp_path / "RTF Dark Side 7 March 76 flac16"
    show_dir.mkdir()

    record, _dates, _unresolved = P._extract_metadata_for_group(
        _config(tmp_path), _group(show_dir), _matcher()
    )

    assert record.artist == "Return to Forever"
    assert record.date == "1976-03-07"
    assert record.venue == ""
    assert record.location == ""
    assert "Dark Side" not in record.show_name


@pytest.mark.parametrize(
    "folder",
    [
        "RTF Paris 7 March 76",          # no technical tail
        "RTF Paris 7 March 76 Deluxe",  # ordinary title-like tail
    ],
)
def test_build460_pattern_requires_recognized_technical_tail(folder):
    match, collisions = P._match_artist_place_date_technical_suffix(folder, _matcher())
    assert match is None
    assert collisions == []


def test_build460_raw_place_hint_does_not_block_stronger_online_metadata(tmp_path: Path, monkeypatch):
    show_dir = tmp_path / "RTF Paris 7 March 76 flac16"
    show_dir.mkdir()

    def fake_etree(config, record, evidence, observations):
        record.venue = "Le Bataclan"
        record.city = "Paris"
        record.country = "France"
        record.location = "Paris, France"
        return True

    monkeypatch.setattr(P, "_apply_etree_lookup_to_record", fake_etree)

    record, _dates, unresolved = P._extract_metadata_for_group(
        _config(tmp_path, etree=True), _group(show_dir), _matcher()
    )

    assert record.venue == "Le Bataclan"
    assert record.location == "Paris, France"
    assert record.show_name == "Return to Forever 1976-03-07 Le Bataclan Paris, France"
    assert not unresolved
    assert not any("retained single-word pre-date place hint" in item for item in record.observations)


def test_build460_requirements_and_manual_document_guarded_fallback():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    req = "\n".join(
        paragraph.text for paragraph in Document(root / "TLO_Inventory_Requirements_Working_v482.docx").paragraphs
    )
    manual = (root / "TLO_Inventory_User_Manual_v482.rtf").read_text(
        encoding="utf-8", errors="ignore"
    )

    assert "Current document version: v482 (v1.7 Build 482)." in req
    assert "Artist + Place + Date + TechnicalSuffix" in req
    assert "TLO must not construct, infer, or guess an initialism" in req
    assert "RTF Paris 7 March 76 flac16" in req
    assert "Version v1.7 Build 482" in manual
    assert "RTF Paris 7 March 76 flac16" in manual
    assert "TLO does not invent RTF from Return to Forever" in manual
