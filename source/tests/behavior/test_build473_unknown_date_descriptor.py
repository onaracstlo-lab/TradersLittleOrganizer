"""Build 474: conservative descriptor fallback for unknown-date collections/shows."""

from pathlib import Path

import pytest

import tlo_phase23_v2 as phase
import tlo_postprocess as post
from tlo_models import ShowMetadata
from tlo_show_descriptor import extract_fallback_descriptor

__version__ = "v476"
pytestmark = pytest.mark.behavior


def _record(tmp_path: Path, text: str, filename: str = "info.txt", folder: str = "Artist") -> ShowMetadata:
    music_dir = tmp_path / folder
    music_dir.mkdir(parents=True, exist_ok=True)
    setlist = music_dir / filename
    setlist.write_text(text, encoding="utf-8")
    return ShowMetadata(
        group_number=1,
        main_dir_name=music_dir.name,
        main_dir_path=str(music_dir),
        setlist_file=str(setlist),
        setlist_files=[str(setlist)],
        music_file_count=2,
        artist="Artist",
        date="xxxx-xx-xx",
    )


def test_explicit_collection_header_becomes_descriptor_not_venue(tmp_path):
    record = _record(
        tmp_path,
        "Artist\nCollection: Early Flights\n\n1. First Song\n2. Second Song\n",
    )
    observations = []

    assert phase._apply_unknown_date_descriptor_fallback(record, observations)
    assert record.descriptor == "Early Flights"
    assert record.descriptor_source == "setlist-explicit-collection"
    assert record.venue == ""
    assert record.location == ""
    assert phase._build_show_name(record) == "Artist xxxx-xx-xx Early Flights"
    assert any("unknown-date descriptor fallback" in item for item in observations)


def test_broadcast_session_header_becomes_descriptor(tmp_path):
    record = _record(tmp_path, "Artist\nBBC Radio Sessions\n\n01 Song A\n02 Song B\n")
    candidate = extract_fallback_descriptor(
        setlist_file=record.setlist_file,
        setlist_files=record.setlist_files,
        artist=record.artist,
        main_dir_name=record.main_dir_name,
    )
    assert candidate is not None
    assert candidate.value == "BBC Radio Sessions"
    assert candidate.source == "setlist-descriptor-header"
    assert candidate.score >= 90


def test_quoted_release_title_becomes_descriptor(tmp_path):
    record = _record(tmp_path, 'Artist\n"Archive One"\n\n1 Song A\n')
    candidate = extract_fallback_descriptor(
        setlist_file=record.setlist_file,
        artist=record.artist,
        main_dir_name=record.main_dir_name,
    )
    assert candidate is not None
    assert candidate.value == "Archive One"
    assert candidate.source == "setlist-quoted-title"


def test_plain_header_title_requires_blank_separator_so_unnumbered_song_block_is_not_used(tmp_path):
    record = _record(tmp_path, "Artist\nSong One\nSong Two\nSong Three\n")
    candidate = extract_fallback_descriptor(
        setlist_file=record.setlist_file,
        artist=record.artist,
        main_dir_name="Artist",
    )
    assert candidate is None


def test_technical_lineage_is_not_descriptor_and_filename_can_fallback(tmp_path):
    record = _record(
        tmp_path,
        "Artist\nSBD > DAT > FLAC\n\n1 Song A\n",
        filename="BBC_Sessions.txt",
    )
    candidate = extract_fallback_descriptor(
        setlist_file=record.setlist_file,
        artist=record.artist,
        main_dir_name="Artist",
    )
    assert candidate is not None
    assert candidate.value == "BBC Sessions"
    assert candidate.source == "setlist-filename"


def test_directory_residue_is_last_resort_descriptor(tmp_path):
    record = _record(
        tmp_path,
        "Artist\n\n1 Song A\n",
        filename="info.txt",
        folder="Artist Early Recordings flac16",
    )
    candidate = extract_fallback_descriptor(
        setlist_file=record.setlist_file,
        artist=record.artist,
        main_dir_name=record.main_dir_name,
    )
    assert candidate is not None
    assert candidate.value == "Early Recordings"
    assert candidate.source == "directory-residue"
    assert candidate.score == 60


def test_fallback_does_not_run_for_known_date_or_geographic_metadata(tmp_path):
    known = _record(tmp_path / "known", "Collection: Early Flights\n1 Song A\n")
    known.date = "1970-01-01"
    assert not phase._apply_unknown_date_descriptor_fallback(known, [])
    assert known.descriptor == ""

    located = _record(tmp_path / "located", "Collection: Early Flights\n1 Song A\n")
    located.venue = "Somewhere Hall"
    located.location = "Boston, MA"
    assert not phase._apply_unknown_date_descriptor_fallback(located, [])
    assert located.descriptor == ""


def test_descriptor_is_in_meta_log_postprocess_and_generated_setlist_base(tmp_path):
    record = _record(tmp_path, "Collection: Early Flights\n1 Song A\n")
    assert phase._apply_unknown_date_descriptor_fallback(record, [])
    record.show_name = phase._build_show_name(record)
    lines = phase._format_show_metadata_log_lines(record, [])
    assert "DESCRIPTOR: Early Flights" in lines
    assert "DESCRIPTOR_SOURCE: setlist-explicit-collection" in lines

    converted = post._metadata_record_to_postprocess_dict(record)
    assert converted["descriptor"] == "Early Flights"
    assert converted["show_name"] == "Artist xxxx-xx-xx Early Flights"
    assert post._setlist_base_from_record(converted) == "Artistxxxx-xx-xxEarlyFlights"


def test_build473_documents_describe_descriptor_as_non_geographic_fallback():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    requirements = Document(root / "TLO_Inventory_Requirements_Working_v486.docx")
    req_text = "\n".join(p.text for p in requirements.paragraphs)
    manual = (root / "TLO_Inventory_User_Manual_v486.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = (root / "TLO-FAQ.txt").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v486 (v1.7 Build 486)." in req_text
    assert "separate non-geographic Descriptor" in req_text
    assert "The Descriptor must never populate Venue, City, Region, Country, or Location." in req_text
    assert "Build 473 - unknown-date descriptor fallback" in manual
    assert "Venue and Location remain blank" in manual
    assert "Build 473 can add a separate non-geographic descriptor" in faq
