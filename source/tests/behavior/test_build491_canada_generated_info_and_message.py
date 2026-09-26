"""Build 491 regressions for Canadian regions, marker info-gen files, and GUI wording."""

import importlib.util
import json
from pathlib import Path

import pytest

import tlo_phase23_v2 as P
import tlo_postprocess as PP
import tlo_setlist_file_selection as FS
import tlo_setlist_metadata_lookup as S
from tlo_constants import CANADIAN_REGION_CODES

pytestmark = pytest.mark.behavior

__version__ = "v493"


def _load_gui_module():
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("tlo_ggi_build491", root / "tlo-ggi.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build491_canadian_postal_abbreviations_are_built_in_region_codes():
    assert set(("AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT")) <= set(CANADIAN_REGION_CODES)


def test_build491_path_string2_uses_canadian_province_abbreviation_as_location_anchor():
    assert P._parse_string2("Massey Hall Toronto ON") == ("Massey Hall", "Toronto", "ON", "Canada", "")
    assert P._parse_string2("Commodore Ballroom Vancouver BC") == ("Commodore Ballroom", "Vancouver", "BC", "Canada", "")


def test_build491_canadian_abbreviation_requires_uppercase_when_newly_inferred():
    assert P._parse_string2("Massey Hall Toronto on") == ("", "", "", "", "")


def test_build491_setlist_location_parser_recognizes_canadian_abbreviation_without_db_file(tmp_path: Path):
    support = S._SupportData(str(tmp_path))
    assert S._parse_location_from_text("Toronto, ON", support)[:3] == ("Toronto", "ON", "Canada")
    # NT is shared with Australia's Northern Territory: recognize the region but
    # do not infer a country unless surrounding evidence supplies one.
    assert S._parse_location_from_text("Yellowknife, NT", support)[:3] == ("Yellowknife", "NT", "")
    assert P._parse_string2("Yellowknife NT Canada") == ("", "Yellowknife", "NT", "Canada", "")


def test_build491_marker_only_info_creates_info_gen_and_exports_it_instead_of_original(tmp_path: Path):
    show = tmp_path / "show"
    show.mkdir()
    (show / "01 Intro.flac").write_bytes(b"")
    (show / "02 Song.mp3").write_bytes(b"")
    original = show / "info.txt"
    original.write_text("Folder never contained an info file.\n", encoding="utf-8")
    record = {
        "artist": "Artist",
        "date": "2005-04-16",
        "venue": "Venue",
        "location": "Toronto, ON",
        "main_dir_path": str(show),
        "music_dirs_json": json.dumps([str(show)]),
    }

    exported = PP._export_setlist_text(str(original), record)
    generated = show / "info-gen.txt"

    assert generated.is_file()
    assert generated.read_text(encoding="utf-8").strip() == exported
    assert exported.splitlines() == [
        "Artist: Artist",
        "Date: 2005-04-16",
        "Venue: Venue",
        "Location: Toronto, ON",
        "",
        "File: 01 Intro.flac",
        "File: 02 Song.mp3",
    ]
    assert "Folder never contained an info file" not in exported
    assert original.read_text(encoding="utf-8").strip() == "Folder never contained an info file."


def test_build491_marker_info_gen_omits_unknown_metadata(tmp_path: Path):
    show = tmp_path / "show"
    show.mkdir()
    (show / "track.flac").write_bytes(b"")
    original = show / "notes.txt"
    original.write_text("Folder never contained an info file.", encoding="utf-8")
    record = {
        "artist": "Artist",
        "date": "",
        "venue": "",
        "location": "",
        "main_dir_path": str(show),
        "music_dirs_json": json.dumps([str(show)]),
    }

    exported = PP._export_setlist_text(str(original), record)
    assert exported.splitlines() == ["Artist: Artist", "", "File: track.flac"]
    assert "Date:" not in exported
    assert "Venue:" not in exported
    assert "Location:" not in exported


def test_build491_generated_info_wins_over_old_marker_on_next_selection(tmp_path: Path):
    marker = tmp_path / "info.txt"
    marker.write_text("Folder never contained an info file.\n", encoding="utf-8")
    generated = tmp_path / "info-gen.txt"
    generated.write_text("Artist: Artist\nDate: 2005-04-16\nFile: 01 Intro.flac\n", encoding="utf-8")

    ordered = FS._ordered_txt_files([str(marker), str(generated)])
    assert Path(ordered[0]).name == "info-gen.txt"


def test_build491_marker_with_other_content_remains_original_and_does_not_create_info_gen(tmp_path: Path):
    show = tmp_path / "show"
    show.mkdir()
    original = show / "info.txt"
    original_text = "Folder never contained an info file.\n01 Real Song\n"
    original.write_text(original_text, encoding="utf-8")
    record = {"main_dir_path": str(show), "music_dirs_json": json.dumps([str(show)])}

    exported = PP._export_setlist_text(str(original), record)
    assert exported == original_text.strip()
    assert not (show / "info-gen.txt").exists()


def test_build491_backup_alert_names_delete_backup_folders_txt():
    root = Path(__file__).resolve().parents[2]
    source = (root / "tlo-ggi.py").read_text(encoding="utf-8")
    assert "TLOHome/deleteBackupFolders.txt already exists. Continue or abort?" in source


def test_build491_requirements_and_manual_document_changes():
    root = Path(__file__).resolve().parents[2]
    from docx import Document

    req = root / "TLO_Inventory_Requirements_Working_v493.docx"
    manual = root / "TLO_Inventory_User_Manual_v493.rtf"
    assert req.is_file()
    assert manual.is_file()

    req_text = "\n".join(p.text for p in Document(req).paragraphs)
    manual_text = manual.read_text(encoding="utf-8", errors="replace")

    assert "Build 491" in req_text
    assert "info-gen.txt" in req_text
    assert "deleteBackupFolders.txt" in req_text
    assert "BC" in req_text and "ON" in req_text
    assert "Version v1.7 Build 493" in manual_text
    assert "info-gen.txt" in manual_text
    assert "deleteBackupFolders.txt" in manual_text
