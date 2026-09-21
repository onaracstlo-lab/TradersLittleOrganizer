"""Build 485 persistent multi-pass Copy Request workflow."""

__version__ = "v486"

import pytest

pytestmark = pytest.mark.behavior

import json
import os
import sqlite3
from pathlib import Path

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
    return db


def _request(tmp_path: Path, name="wanted.txt", text="Grateful Dead\n"):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _music_folder(root: Path, rel: str, payload=b"music"):
    path = root / Path(rel)
    path.mkdir(parents=True, exist_ok=True)
    (path / "track01.flac").write_bytes(payload)
    (path / "info.txt").write_text("setlist\n", encoding="utf-8")
    return path


def _row(show: str, volume: str, rel: str):
    return {"Show": show, "VolumePath": format_volume_path(volume, "/" + rel.replace(os.sep, "/"))}


def test_build485_request_file_comments_and_range_wraparound():
    text = """# comment
REM another comment

Grateful Dead 99-01
Grateful Dead 1972-1978
"""
    assert CR.request_lines_from_text(text) == ["Grateful Dead 99-01", "Grateful Dead 1972-1978"]
    assert CR.resolve_year_range("99", "01", current_year=2026) == (1999, 2001)
    assert CR.resolve_year_range("72", "78", current_year=2026) == (1972, 1978)
    assert CR.resolve_year_range("24", "26", current_year=2026) == (2024, 2026)
    with pytest.raises(CR.CopyRequestError):
        CR.resolve_year_range("1978", "1972")


def test_build485_mixed_exact_show_alias_date_range_and_artist_matching(tmp_path):
    home = tmp_path / "home"
    _artist_db(home)
    matcher = CR._load_matcher(str(home))
    shows = [
        "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY",
        "Grateful Dead 1999-07-01 Venue City, ST",
        "Grateful Dead 2001-01-02 Venue City, ST",
        "Miles Davis 1970-04-10 Fillmore West San Francisco, CA",
    ]
    text = "\n".join([
        shows[0],
        "GD 1977",
        "GD 1977-05-08",
        "GD 99-01",
        "Miles",
    ])
    items = CR.parse_request_items(text, shows, matcher)
    matches, unmatched, invalid = CR.match_request_items(items, shows, matcher)
    assert unmatched == []
    assert invalid == {}
    assert matches[shows[0]] == [shows[0]]
    assert matches["GD 1977"] == [shows[0]]
    assert matches["GD 1977-05-08"] == [shows[0]]
    assert matches["GD 99-01"] == shows[1:3]
    assert matches["Miles"] == [shows[3]]


def test_build485_multi_pass_resume_skips_prior_copy_and_uses_later_volume(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    vol1 = tmp_path / "vol1"
    vol2 = tmp_path / "vol2"
    show1 = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    show2 = "Grateful Dead 1978-04-24 Horton Field House Normal, IL"
    source1 = _music_folder(vol1, "Dead/show-one", b"one")
    source2 = _music_folder(vol2, "Dead/show-two", b"two")
    write_bootlist_rows(str(home), [
        _row(show1, "VOL1", "Dead/show-one"),
        _row(show2, "VOL2", "Dead/show-two"),
    ])
    request = _request(tmp_path)
    destination = tmp_path / "dest"
    destination.mkdir()
    state = CR.create_or_open_request(str(home), str(request), str(destination))
    rid = state["request_id"]

    first = CR.evaluate_request(str(home), rid, roots={"vol1": [str(vol1)]})
    assert set(first.available) == {show1}
    assert set(first.waiting) == {show2}
    assert first.volume_opportunities == {"VOL2": 1}
    result1 = CR.copy_available(str(home), rid, roots={"vol1": [str(vol1)]})
    assert [row[0] for row in result1.copied] == [show1]
    assert (destination / source1.name / "track01.flac").read_bytes() == b"one"

    second = CR.evaluate_request(str(home), rid, roots={"vol2": [str(vol2)]})
    assert show1 in second.completed_shows
    assert set(second.available) == {show2}
    result2 = CR.copy_available(str(home), rid, roots={"vol2": [str(vol2)]})
    assert [row[0] for row in result2.copied] == [show2]
    assert (destination / source2.name / "track01.flac").read_bytes() == b"two"
    final = CR.evaluate_request(str(home), rid, roots={})
    assert final.status == CR.STATUS_COMPLETE
    assert set(final.completed_shows) == {show1, show2}


def test_build485_entire_current_pass_free_space_preflight_is_all_or_nothing(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    volume = tmp_path / "volume"
    show = "Miles Davis 1970-04-10 Fillmore West San Francisco, CA"
    source = _music_folder(volume, "Jazz/miles", b"x" * 1024)
    write_bootlist_rows(str(home), [_row(show, "JAZZ", "Jazz/miles")])
    request = _request(tmp_path, text="Miles\n")
    dest = tmp_path / "dest"
    dest.mkdir()
    rid = CR.create_or_open_request(str(home), str(request), str(dest))["request_id"]

    class Usage:
        total = 100
        used = 99
        free = 1

    monkeypatch.setattr(CR.shutil, "disk_usage", lambda _path: Usage())
    result = CR.copy_available(str(home), rid, roots={"jazz": [str(volume)]})
    assert result.insufficient_space is True
    assert result.copied == []
    assert not (dest / source.name).exists()


def test_build485_second_request_same_destination_marks_exact_existing_tree_satisfied(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    volume = tmp_path / "volume"
    show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    source = _music_folder(volume, "Dead/show-one", b"same")
    write_bootlist_rows(str(home), [_row(show, "VOL1", "Dead/show-one")])
    dest = tmp_path / "dest"
    dest.mkdir()
    req1 = _request(tmp_path, "one.txt", show + "\n")
    req2 = _request(tmp_path, "two.txt", "GD 1977-05-08\n")
    rid1 = CR.create_or_open_request(str(home), str(req1), str(dest))["request_id"]
    rid2 = CR.create_or_open_request(str(home), str(req2), str(dest))["request_id"]
    CR.copy_available(str(home), rid1, roots={"vol1": [str(volume)]})
    result2 = CR.copy_available(str(home), rid2, roots={"vol1": [str(volume)]})
    assert result2.copied == []
    assert result2.already_satisfied == [(show, str(dest / source.name))]
    assert CR.evaluate_request(str(home), rid2, roots={}).status == CR.STATUS_COMPLETE


def test_build485_request_update_preserves_completed_and_removed_lines_stop_future_selection(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    dest = tmp_path / "dest"
    dest.mkdir()
    request = _request(tmp_path, text="Grateful Dead\nMiles\n")
    state = CR.create_or_open_request(str(home), str(request), str(dest))
    rid = state["request_id"]
    state["completed"] = {"old show": {"show": "Old Show", "destination_path": str(dest), "completed_at": "now"}}
    CR.save_request(str(home), state)
    request.write_text("Miles\n", encoding="utf-8")
    assert CR.source_request_change_state(str(home), state) == "changed"
    updated = CR.update_request_from_source(str(home), state)
    assert "old show" in updated["completed"]
    assert CR.request_lines_from_text(CR.saved_request_text(str(home), rid)) == ["Miles"]


def test_build485_closed_request_is_terminal_and_delete_only_removes_request_state(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    dest = tmp_path / "dest"
    dest.mkdir()
    music = dest / "already-copied"
    music.mkdir()
    request = _request(tmp_path)
    rid = CR.create_or_open_request(str(home), str(request), str(dest))["request_id"]
    CR.close_request(str(home), rid)
    assert CR.load_request(str(home), rid)["status"] == CR.STATUS_CLOSED
    with pytest.raises(CR.CopyRequestError):
        CR.copy_available(str(home), rid, roots={})
    CR.delete_request(str(home), rid)
    assert not os.path.exists(CR.request_dir(str(home), rid))
    assert music.is_dir()


def test_build485_request_reports_keep_copied_pending_and_failed_lists(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    vol = tmp_path / "vol"
    show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    _music_folder(vol, "Dead/show", b"a")
    write_bootlist_rows(str(home), [_row(show, "VOL", "Dead/show")])
    req = _request(tmp_path, text="GD 1977-05-08\nNo Such Artist\n")
    dest = tmp_path / "dest"
    dest.mkdir()
    rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]
    result = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
    directory = Path(CR.request_dir(str(home), rid))
    assert (directory / CR.COPIED_REPORT_FILENAME).is_file()
    assert show in (directory / CR.COPIED_REPORT_FILENAME).read_text(encoding="utf-8")
    assert "No Such Artist" in (directory / CR.FAILED_REPORT_FILENAME).read_text(encoding="utf-8")
    assert result.report_path == str(directory / CR.LATEST_REPORT_FILENAME)


def test_build485_gui_exposes_copy_request_manager_and_process_all():
    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    assert 'label="Copy Requests"' in source
    assert "class CopyRequestsWindow" in source
    assert 'text="Process All Active Requests"' in source
    assert "Closed requests are kept for history" in source


def test_build485_overlapping_request_lines_copy_each_show_only_once(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    vol = tmp_path / "vol"
    show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    _music_folder(vol, "Dead/show", b"x")
    write_bootlist_rows(str(home), [_row(show, "VOL", "Dead/show")])
    req = _request(tmp_path, text=f"Grateful Dead\nGD 1977\nGD 1977-05-08\n{show}\n")
    dest = tmp_path / "dest"
    dest.mkdir()
    rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]
    evaluation = CR.evaluate_request(str(home), rid, roots={"vol": [str(vol)]})
    assert evaluation.matched_shows == [show]
    result = CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
    assert len(result.copied) == 1


def test_build485_duplicate_inventory_rows_use_one_connected_source(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    vol1 = tmp_path / "vol1"
    vol2 = tmp_path / "vol2"
    show = "Miles Davis 1970-04-10 Fillmore West San Francisco, CA"
    _music_folder(vol1, "Jazz/a", b"one")
    _music_folder(vol2, "Jazz/b", b"two")
    write_bootlist_rows(str(home), [_row(show, "A", "Jazz/a"), _row(show, "B", "Jazz/b")])
    req = _request(tmp_path, text="Miles\n")
    dest = tmp_path / "dest"
    dest.mkdir()
    rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]
    evaluation = CR.evaluate_request(str(home), rid, roots={"b": [str(vol2)]})
    assert evaluation.available[show].source_path == str(vol2 / "Jazz" / "b")
    result = CR.copy_available(str(home), rid, roots={"b": [str(vol2)]})
    assert len(result.copied) == 1
    assert (dest / "b" / "track01.flac").read_bytes() == b"two"


def test_build485_completed_artist_request_discovers_newly_inventoried_show_later(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    vol = tmp_path / "vol"
    first_show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    second_show = "Grateful Dead 1978-04-24 Horton Field House Normal, IL"
    _music_folder(vol, "Dead/one", b"one")
    _music_folder(vol, "Dead/two", b"two")
    write_bootlist_rows(str(home), [_row(first_show, "VOL", "Dead/one")])
    req = _request(tmp_path, text="Grateful Dead\n")
    dest = tmp_path / "dest"
    dest.mkdir()
    rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]
    CR.copy_available(str(home), rid, roots={"vol": [str(vol)]})
    assert CR.evaluate_request(str(home), rid, roots={}).status == CR.STATUS_COMPLETE
    write_bootlist_rows(str(home), [_row(first_show, "VOL", "Dead/one"), _row(second_show, "VOL", "Dead/two")])
    later = CR.evaluate_request(str(home), rid, roots={"vol": [str(vol)]})
    assert later.status == CR.STATUS_IN_PROGRESS
    assert set(later.available) == {second_show}



def test_build485_explicit_empty_roots_stays_disconnected_and_volume_counts_unique_shows(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    write_bootlist_rows(str(home), [
        _row(show, "ARCHIVE", "Dead/one"),
        _row(show, "ARCHIVE", "Dead/duplicate-row"),
    ])
    req = _request(tmp_path, text=show + "\n")
    dest = tmp_path / "dest"
    dest.mkdir()
    rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]
    monkeypatch.setattr(CR, "connected_volume_roots", lambda: (_ for _ in ()).throw(AssertionError("must not auto-discover roots")))
    evaluation = CR.evaluate_request(str(home), rid, roots={})
    assert set(evaluation.waiting) == {show}
    assert evaluation.volume_opportunities == {"ARCHIVE": 1}

def test_build485_documents_describe_persistent_copy_requests_and_closed_state():
    from docx import Document

    requirements = Document("TLO_Inventory_Requirements_Working_v486.docx")
    requirement_text = "\n".join(paragraph.text for paragraph in requirements.paragraphs)
    assert "Build 485 - persistent multi-pass Copy Requests" in requirement_text
    assert "Artist plus one calendar year in yyyy form" in requirement_text
    assert "99-01 means 1999 through 2001" in requirement_text
    assert "Close Request changes the terminal user-chosen state to Closed" in requirement_text

    manual = Path("TLO_Inventory_User_Manual_v486.rtf").read_text(encoding="utf-8")
    assert "Build 485 persistent Copy Requests" in manual
    assert "Grateful Dead 1977" in manual
    assert "Closed" in manual

    faq = Path("TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "Process All Active Requests" in faq
    assert "calendar year (yyyy)" in faq
