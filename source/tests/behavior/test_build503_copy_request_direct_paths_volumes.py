"""Build 503 direct path/volume Copy Requests with show de-confliction."""

__version__ = "v503"

import os
import sqlite3
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

import tlo_copy_requests as CR
from tlo_bootlist_volume_policy import format_volume_path, write_bootlist_rows


def _artist_db(home: Path):
    dbdir = home / "TLO_DBs"
    dbdir.mkdir(parents=True, exist_ok=True)
    db = dbdir / "artists.sqlite"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE artists (artist_id INTEGER PRIMARY KEY, source_row_number INTEGER NOT NULL UNIQUE, master_name TEXT NOT NULL);
        CREATE TABLE aliases (alias_id INTEGER PRIMARY KEY, artist_id INTEGER NOT NULL, alias_text TEXT NOT NULL, alias_order INTEGER NOT NULL);
        CREATE TABLE terms (term_id INTEGER PRIMARY KEY, artist_id INTEGER NOT NULL, term_text TEXT NOT NULL, term_type TEXT NOT NULL, term_order INTEGER NOT NULL);
        INSERT INTO artists VALUES (1, 1, 'Grateful Dead');
        INSERT INTO aliases VALUES (1, 1, 'GD', 1);
        INSERT INTO terms VALUES (1, 1, 'Grateful Dead', 'master', 0);
        INSERT INTO terms VALUES (2, 1, 'GD', 'alias', 1);
        INSERT INTO artists VALUES (2, 2, 'Miles Davis');
        INSERT INTO aliases VALUES (2, 2, 'Miles', 1);
        INSERT INTO terms VALUES (3, 2, 'Miles Davis', 'master', 0);
        INSERT INTO terms VALUES (4, 2, 'Miles', 'alias', 1);
        """
    )
    conn.commit()
    conn.close()


def _music_folder(root: Path, rel: str, payload=b"music"):
    path = root / Path(rel)
    path.mkdir(parents=True, exist_ok=True)
    (path / "track01.flac").write_bytes(payload)
    return path


def _row(show: str, volume: str, rel: str):
    return {"Show": show, "VolumePath": format_volume_path(volume, "/" + rel.replace(os.sep, "/"))}


def _request(tmp_path: Path, text: str):
    path = tmp_path / "wanted.txt"
    path.write_text(text, encoding="utf-8")
    return path


def test_build503_absolute_path_is_direct_and_deconflicts_artist_item_same_pass(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    volume = tmp_path / "VOLROOT"
    show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    show_dir = _music_folder(volume, "Dead/show-one", b"one")
    write_bootlist_rows(str(home), [_row(show, "VOL", "Dead/show-one")])
    dest = tmp_path / "dest"
    dest.mkdir()
    request = _request(tmp_path, f"{volume}\nGrateful Dead\n")
    rid = CR.create_or_open_request(str(home), str(request), str(dest))["request_id"]

    evaluation = CR.evaluate_request(str(home), rid, roots={"vol": [str(volume)]})
    assert str(volume) in evaluation.direct_available
    assert show in evaluation.available

    result = CR.copy_available(str(home), rid, roots={"vol": [str(volume)]})
    assert [entry[0] for entry in result.copied] == [str(volume)]
    target_root = dest / volume.name
    assert (target_root / "Dead" / "show-one" / "track01.flac").read_bytes() == b"one"
    assert not (dest / show_dir.name).exists()

    state = CR.load_request(str(home), rid)
    assert CR._normalize_show(show) in state["completed"]
    assert state["completed_direct"]
    assert state["completed"][CR._normalize_show(show)]["destination_path"] == str(target_root / "Dead" / "show-one")
    final = CR.evaluate_request(str(home), rid, roots={})
    assert show in final.completed_shows
    assert str(volume) in final.completed_direct_items
    assert final.status == CR.STATUS_COMPLETE


def test_build503_volume_label_is_direct_and_tracks_contained_shows(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    volume = tmp_path / "archive-root"
    show = "Miles Davis 1970-04-10 Fillmore West San Francisco, CA"
    _music_folder(volume, "Jazz/miles", b"miles")
    write_bootlist_rows(str(home), [_row(show, "ARCHIVE", "Jazz/miles")])
    dest = tmp_path / "dest"
    dest.mkdir()
    request = _request(tmp_path, "ARCHIVE\nMiles\n")
    rid = CR.create_or_open_request(str(home), str(request), str(dest))["request_id"]

    evaluation = CR.evaluate_request(str(home), rid, roots={"archive": [str(volume)]})
    assert evaluation.items[0].kind == "volume"
    assert "ARCHIVE" in evaluation.direct_available
    result = CR.copy_available(str(home), rid, roots={"archive": [str(volume)]})
    assert [entry[0] for entry in result.copied] == ["ARCHIVE"]
    assert (dest / "ARCHIVE" / "Jazz" / "miles" / "track01.flac").read_bytes() == b"miles"
    assert CR.evaluate_request(str(home), rid, roots={}).status == CR.STATUS_COMPLETE


def test_build503_bracketed_volume_path_direct_copy_and_resume_tracking(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    volume = tmp_path / "vol"
    show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    _music_folder(volume, "Dead/show", b"same")
    write_bootlist_rows(str(home), [_row(show, "VOL", "Dead/show")])
    dest = tmp_path / "dest"
    dest.mkdir()
    request = _request(tmp_path, "[VOL] /Dead\n")
    rid = CR.create_or_open_request(str(home), str(request), str(dest))["request_id"]

    first = CR.copy_available(str(home), rid, roots={"vol": [str(volume)]})
    assert len(first.copied) == 1
    assert (dest / "Dead" / "show" / "track01.flac").exists()
    second = CR.copy_available(str(home), rid, roots={"vol": [str(volume)]})
    assert second.copied == []
    assert CR.evaluate_request(str(home), rid, roots={}).status == CR.STATUS_COMPLETE


def test_build503_missing_direct_path_waits_instead_of_becoming_artist(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    dest = tmp_path / "dest"
    dest.mkdir()
    missing = tmp_path / "not-connected" / "collection"
    request = _request(tmp_path, str(missing) + "\n")
    rid = CR.create_or_open_request(str(home), str(request), str(dest))["request_id"]
    evaluation = CR.evaluate_request(str(home), rid, roots={})
    assert evaluation.items[0].kind == "path"
    assert str(missing) in evaluation.direct_waiting
    assert evaluation.unmatched_items == []
    assert evaluation.status == CR.STATUS_WAITING


def test_build503_direct_copy_preview_counts_direct_bytes_and_gui_enables_copy(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    source = tmp_path / "source"
    _music_folder(source, "nested", b"12345")
    dest = tmp_path / "dest"
    dest.mkdir()
    request = _request(tmp_path, str(source) + "\n")
    rid = CR.create_or_open_request(str(home), str(request), str(dest))["request_id"]
    evaluation, required, _free, errors = CR.preview_request(str(home), rid, roots={})
    assert str(source) in evaluation.direct_available
    assert required >= 5
    assert errors == []
    gui = Path("tlo-ggi.py").read_text(encoding="utf-8")
    assert "evaluation.available or evaluation.direct_available" in gui


def test_build503_documentation_describes_direct_copy_and_deconfliction():
    from docx import Document
    req = "\n".join(p.text for p in Document("TLO_Inventory_Requirements_Working_v518.docx").paragraphs)
    manual = Path("TLO_Inventory_User_Manual_v518.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = Path("TLO-FAQ.txt").read_text(encoding="utf-8", errors="ignore")
    assert "direct filesystem path/volume item" in req
    assert "[Volume] path" in req
    assert "de-conflicted in the same pass and on later passes" in req
    assert "Build 503: direct path/volume Copy Request items" in req
    assert "direct filesystem path or volume item" in manual
    assert "rooted filesystem path" in faq
