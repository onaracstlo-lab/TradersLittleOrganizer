"""Build 543 corrupt-input isolation regressions for standalone Tag and Add Shows."""

from __future__ import annotations

import io
import shutil
import sqlite3
import zipfile
from pathlib import Path

import pytest
from mutagen.flac import FLAC

import logging_lib
import tlo_inventory_update as updater
import tlo_tag_lib as taglib
import tlo_text_utils as text_utils

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]
FLAC_FIXTURE = ROOT / "tests" / "fixtures" / "build543_silence.flac"


def _write_artist_db(home: Path, artists: list[str]) -> None:
    db_dir = home / "TLO_DBs"
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_dir / "artists.sqlite")
    conn.executescript(
        """
        CREATE TABLE artists (
            artist_id INTEGER PRIMARY KEY,
            source_row_number INTEGER NOT NULL UNIQUE,
            master_name TEXT NOT NULL
        );
        CREATE TABLE aliases (
            alias_id INTEGER PRIMARY KEY,
            artist_id INTEGER NOT NULL,
            alias_text TEXT NOT NULL,
            alias_order INTEGER NOT NULL
        );
        CREATE TABLE terms (
            term_id INTEGER PRIMARY KEY,
            artist_id INTEGER NOT NULL,
            term_text TEXT NOT NULL,
            term_type TEXT NOT NULL,
            term_order INTEGER NOT NULL
        );
        """
    )
    for number, artist in enumerate(artists, start=1):
        conn.execute("INSERT INTO artists VALUES (?, ?, ?)", (number, number, artist))
        conn.execute("INSERT INTO aliases VALUES (?, ?, ?, ?)", (number, number, artist, 1))
        conn.execute("INSERT INTO terms VALUES (?, ?, ?, ?, ?)", (number, number, artist, "master", 0))
    conn.commit()
    conn.close()
    (db_dir / "venues.txt").write_text("Fillmore East\nBarton Hall\n", encoding="utf-8")


def _write_corrupt_deflate_docx(path: Path) -> None:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "word/document.xml",
            "<w:document><w:p>" + "x " * 4000 + "</w:p></w:document>",
        )
    data = bytearray(buf.getvalue())
    start = 30 + int.from_bytes(data[26:28], "little")
    for index in range(start + 5, min(start + 40, len(data))):
        data[index] ^= 0xFF
    path.write_bytes(data)


def _copy_tracks(folder: Path, names: tuple[str, ...]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    assert FLAC_FIXTURE.is_file()
    for name in names:
        shutil.copy2(FLAC_FIXTURE, folder / name)


def test_build543_corrupt_docx_deflate_is_treated_as_unusable_text(tmp_path):
    path = tmp_path / "setlist.docx"
    _write_corrupt_deflate_docx(path)

    assert text_utils.read_text_file_full(str(path)) == ""
    assert text_utils.read_text_file_sample(str(path)) == ""


def test_build543_run_tagger_continues_after_one_folder_raises(monkeypatch, tmp_path):
    groups = [
        {"main_dir_path": str(tmp_path / "bad")},
        {"main_dir_path": str(tmp_path / "good")},
    ]
    messages: list[str] = []
    calls: list[str] = []

    monkeypatch.setattr(taglib, "validate_required_databases", lambda _config: None)
    monkeypatch.setattr(taglib, "load_artist_matcher", lambda _config: object())
    monkeypatch.setattr(taglib, "_groups_from_inventory_discovery", lambda _config, _path: groups)

    def fake_process(_config, group, _matcher, emit=None):
        calls.append(group["main_dir_path"])
        if group["main_dir_path"].endswith("bad"):
            raise RuntimeError("broken third-party setlist")
        result = taglib.empty_tag_stats()
        result["groups"] = 1
        result["tagged"] = 1
        return result

    monkeypatch.setattr(taglib, "process_tagging_group", fake_process)
    totals = taglib.run_tagger(
        tlo_home=str(tmp_path),
        tag_path=str(tmp_path),
        emit=messages.append,
    )

    assert calls == [str(tmp_path / "bad"), str(tmp_path / "good")]
    assert totals["groups"] == 2
    assert totals["tagged"] == 1
    assert totals["errors"] == 1
    assert any("ERROR_TAGGING:" in message and "broken third-party setlist" in message for message in messages)


def test_build543_run_tagger_jobs_continues_after_one_folder_raises(monkeypatch, tmp_path):
    groups = [
        {"main_dir_path": str(tmp_path / "bad")},
        {"main_dir_path": str(tmp_path / "good")},
    ]
    messages: list[str] = []
    calls: list[str] = []
    config = taglib.build_tagger_config(tlo_home=str(tmp_path))

    monkeypatch.setattr(taglib, "validate_required_databases", lambda _config: None)
    monkeypatch.setattr(taglib, "load_artist_matcher", lambda _config: object())
    monkeypatch.setattr(taglib, "_groups_from_inventory_discovery", lambda _config, _path: groups)

    def fake_process(_config, group, _matcher, emit=None):
        calls.append(group["main_dir_path"])
        if group["main_dir_path"].endswith("bad"):
            raise EOFError("truncated setlist")
        result = taglib.empty_tag_stats()
        result["groups"] = 1
        result["tagged"] = 1
        return result

    monkeypatch.setattr(taglib, "process_tagging_group", fake_process)
    totals = taglib.run_tagger_jobs(
        config,
        [{"path": str(tmp_path), "volume_label": "", "volume_key": ""}],
        emit=messages.append,
    )

    assert calls == [str(tmp_path / "bad"), str(tmp_path / "good")]
    assert totals["groups"] == 2
    assert totals["tagged"] == 1
    assert totals["errors"] == 1
    assert any("ERROR_TAGGING:" in message and "truncated setlist" in message for message in messages)


def test_build543_two_folder_real_tagger_run_survives_corrupt_docx(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _write_artist_db(home, ["Allman Brothers Band", "Grateful Dead"])

    music = tmp_path / "music"
    bad = music / "Allman Brothers Band 1971-03-13 Fillmore East, New York, NY"
    good = music / "Grateful Dead 1977-05-08 Barton Hall, Ithaca, NY"
    _copy_tracks(bad, ("01 Song One.flac", "02 Song Two.flac"))
    _copy_tracks(good, ("01 Song One.flac", "02 Song Two.flac"))
    _write_corrupt_deflate_docx(bad / "setlist.docx")
    (good / "setlist.txt").write_text(
        "01 Scarlet Begonias\n02 Fire on the Mountain\n",
        encoding="utf-8",
    )

    totals = taglib.run_tagger(
        tlo_home=str(home),
        tag_path=str(music),
        corrupt_files="keep",
        emit=lambda _text: None,
    )

    assert totals["groups"] == 2
    assert totals["tagged"] == 2
    assert totals["skipped"] == 1
    assert FLAC(good / "01 Song One.flac")["title"] == ["Scarlet Begonias"]
    assert FLAC(good / "02 Song Two.flac")["title"] == ["Fire on the Mountain"]
    assert FLAC(good / "01 Song One.flac")["artist"] == ["Grateful Dead"]
    assert FLAC(bad / "01 Song One.flac").get("artist") is None


def test_build543_add_shows_duplicate_with_corrupt_docx_completes_consistently(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _write_artist_db(home, ["Grateful Dead"])
    dirs = updater.ensure_updater_directories(str(home))
    duplicate = Path(dirs["dups"]) / "Grateful Dead 1977-05-08 Barton Hall, Ithaca, NY"
    _copy_tracks(duplicate, ("01 Scarlet Begonias.flac", "02 Fire on the Mountain.flac"))
    _write_corrupt_deflate_docx(duplicate / "setlist.docx")

    config = taglib.build_tagger_config(tlo_home=str(home), corrupt_files="keep")
    logging_lib.setup_logging(config)
    record = {
        "show_name": "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY",
        "artist": "Grateful Dead",
        "date": "1977-05-08",
        "venue": "Barton Hall",
        "location": "Ithaca, NY",
        "main_dir_path": str(duplicate),
        "music_file_count": "2",
    }

    result = updater.process_duplicate_folder(
        config,
        {"folder": str(duplicate), "record": record},
        [],
        "Juke1",
    )

    assert result == {"delete_commands": 0, "delete_commands_skipped": 0, "staged": 1}
    assert not duplicate.exists()
    staged = Path(dirs["staged"]) / duplicate.name
    assert staged.is_dir()
    rows = updater.read_bootlist(str(home))
    assert len(rows) == 1
    assert rows[0]["Show"] == "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    assert rows[0]["VolumePath"] == f"[Juke1] {duplicate.name}"
    assert FLAC(staged / "01 Scarlet Begonias.flac")["title"] == ["Scarlet Begonias"]
    assert FLAC(staged / "02 Fire on the Mountain.flac")["title"] == ["Fire on the Mountain"]
