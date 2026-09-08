"""Build 418 regressions for restored terminal artist suffixes and DB review list."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior


def _matcher(mapping):
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    for term, masters in mapping.items():
        values = set(masters if isinstance(masters, (list, tuple, set)) else [masters])
        matcher.exact_map[term.casefold()] = values
        for master in values:
            matcher.master_aliases.setdefault(master, [master, term])
            matcher.master_norms.setdefault(master, {"".join(ch for ch in master.casefold() if ch.isalpha())})
    return matcher


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        ("Example Band", "Example Master Band"),
        ("Example Group", "Example Master Group"),
        ("Example All Star", "Example Master All Star"),
        ("Example All Stars", "Example Master All Stars"),
        ("Example All-Star", "Example Master All-Star"),
        ("Example All-Stars", "Example Master All-Stars"),
        ("Example AllStar", "Example Master AllStar"),
        ("Example AllStars", "Example Master AllStars"),
        ("Example All Star Band", "Example Master All Star Band"),
        ("Example All-Star Band", "Example Master All-Star Band"),
        ("Example All Stars Band", "Example Master All Stars Band"),
        ("Example All-Stars Band", "Example Master All-Stars Band"),
        ("Example-AllStar", "Example Master-AllStar"),
    ],
)
def test_build418_reapplies_exact_stripped_suffix_to_db_master(candidate, expected):
    from tlo_artist_db import lookup_artist_master_with_status, terminal_suffix_fallback_info_for_artist

    matcher = _matcher({"Example": "Example Master"})
    assert lookup_artist_master_with_status(candidate, matcher) == ("matched", [expected])
    info = terminal_suffix_fallback_info_for_artist(expected, matcher)
    assert info
    assert info["db_master"] == "Example Master"
    assert info["performance_artist"] == expected


def test_build418_full_name_match_still_wins_and_is_not_marked_as_fallback():
    from tlo_artist_db import lookup_artist_master_with_status, terminal_suffix_fallback_info_for_artist

    matcher = _matcher({"Example Group": "Example Group", "Example": "Example Master"})
    assert lookup_artist_master_with_status("Example Group", matcher) == ("matched", ["Example Group"])
    assert terminal_suffix_fallback_info_for_artist("Example Group", matcher) is None


def test_build418_does_not_duplicate_suffix_already_present_in_resolved_master():
    from tlo_artist_db import lookup_artist_master_with_status, terminal_suffix_fallback_info_for_artist

    matcher = _matcher({"Marshall Tucker": "The Marshall Tucker Band"})
    assert lookup_artist_master_with_status("Marshall Tucker Band", matcher) == (
        "matched", ["The Marshall Tucker Band"]
    )
    info = terminal_suffix_fallback_info_for_artist("The Marshall Tucker Band", matcher)
    assert info and info["db_master"] == "The Marshall Tucker Band"
    assert info["performance_artist"] == "The Marshall Tucker Band"


def test_build418_ambiguous_base_still_does_not_promote():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Example": ["Example One", "Example Two"]})
    assert lookup_artist_master_with_status("Example Group", matcher) == ("no_match", [])


def test_build418_record_marks_restored_performance_artist_not_in_database():
    import tlo_phase23_v2 as P
    from tlo_models import ShowMetadata

    matcher = _matcher({"Example": "Example Master"})
    # Populate the fallback map exactly as normal resolution does.
    from tlo_artist_db import lookup_artist_master_with_status
    assert lookup_artist_master_with_status("Example All-Star Band", matcher) == (
        "matched", ["Example Master All-Star Band"]
    )
    record = ShowMetadata(1, "x", "/x", "", 1, artist="Example Master All-Star Band")
    observations = []
    P._mark_terminal_suffix_fallback_artist_not_in_database(record, matcher, observations)
    assert record.artist_not_in_database == "Example Master All-Star Band"
    assert any("not present as a full DB match" in item for item in observations)


def test_build418_db_master_that_already_contains_suffix_is_not_added_to_missing_list():
    import tlo_phase23_v2 as P
    from tlo_models import ShowMetadata
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Marshall Tucker": "The Marshall Tucker Band"})
    assert lookup_artist_master_with_status("Marshall Tucker Band", matcher)[0] == "matched"
    record = ShowMetadata(1, "x", "/x", "", 1, artist="The Marshall Tucker Band")
    P._mark_terminal_suffix_fallback_artist_not_in_database(record, matcher, [])
    assert record.artist_not_in_database == ""


def test_build418_postprocess_missing_artist_list_preserves_sorts_and_casefold_dedupes(tmp_path: Path):
    import tlo_postprocess as PP

    target = tmp_path / "artistsNotInDatabase.txt"
    target.write_text("Zulu Group\nexample master group\n", encoding="utf-8")
    out = PP._write_artists_not_in_database(
        str(tmp_path), ["Example Master Group", "Alpha All-Star Band", "alpha all-star band"]
    )
    assert Path(out) == target
    assert target.read_text(encoding="utf-8").splitlines() == [
        "Alpha All-Star Band", "example master group", "Zulu Group"
    ]


def test_build418_metadata_log_roundtrip_carries_missing_artist_marker(tmp_path: Path):
    import tlo_postprocess as PP

    logs = tmp_path / "logs"
    logs.mkdir()
    (logs / "meta1.log").write_text(
        "SHOW_NAME: Example Master Group 2020-01-01\n"
        "MAIN_DIR_PATH: /music/show\n"
        "ARTIST: Example Master Group\n"
        "ARTIST_NOT_IN_DATABASE: Example Master Group\n"
        "END_SHOW_METADATA\n",
        encoding="utf-8",
    )
    records = PP._parse_show_metadata_logs(str(tmp_path), tokens=["1"])
    assert records[0]["artist_not_in_database"] == "Example Master Group"


def test_build418_full_metadata_record_keeps_restored_artist_and_marks_review_list(tmp_path: Path):
    import tlo_phase23_v2 as P

    show_dir = tmp_path / "Example Group 2020-01-02 Sample Venue Boston, MA"
    show_dir.mkdir()
    group = {
        "group_number": 1,
        "main_dir_name": show_dir.name,
        "main_dir_path": str(show_dir),
        "setlist_file": "",
        "music_file_count": 1,
        "setlist_files": [],
        "music_dirs": [str(show_dir)],
        "music_files": [],
        "music_sample_files": [],
        "flac_tag_samples": [],
        "flac_tag_artist_values": [],
        "flac_tag_album_values": [],
        "flac_tag_albumartist_values": [],
        "flac_tag_date_values": [],
    }
    config = SimpleNamespace(
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
    record, _dates, _unresolved = P._extract_metadata_for_group(config, group, _matcher({"Example": "Example Master"}))
    assert record.artist == "Example Master Group"
    assert record.artist_not_in_database == "Example Master Group"
    assert record.show_name.startswith("Example Master Group 2020-01-02")


def test_build418_requirements_and_manual_document_restored_suffix_and_review_list():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    req = Document(root / "TLO_Inventory_Requirements_Working_v448.docx")
    req_text = "\n".join(p.text for p in req.paragraphs)
    manual = (root / "TLO_Inventory_User_Manual_v448.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v448 (v1.6 Build 448)." in req_text
    assert "restore the exact terminal suffix text" in req_text
    assert "TLOHome/artistsNotInDatabase.txt" in req_text
    assert "Build 407, 417, 418: Terminal Band/Group/All-Star-family Artist DB fallback" in req_text
    assert "Version v1.6 Build 448" in manual
    assert "restores the exact removed suffix" in manual
    assert "artistsNotInDatabase.txt" in manual
