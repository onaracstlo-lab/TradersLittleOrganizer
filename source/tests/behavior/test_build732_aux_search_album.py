"""Build 732 album separator, search launch, and read-only catalog regressions."""
from pathlib import Path
from types import SimpleNamespace
import importlib.util
import sqlite3
import sys
import tkinter as tk

import pytest

import searchAuxDBs as aux
from tlo_rename_safety import safe_rename_target, spaced_album_separator
from tlo_tag_lib import _album_for_record, prepare_inventory_tagging_target
from tlo_inventory_update import _rename_add_shows_folder_compliantly
from tlo_manual_updates import _apply_manual_name_tag_identity

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
ARTIST = "Allman Brothers Band"
TITLE = "Eat a Peach"
TARGET = f"{ARTIST} - {TITLE}"


@pytest.mark.parametrize("compliant", [False, True])
@pytest.mark.parametrize("checked", [False, True])
def test_undated_album_tag(compliant, checked):
    record = SimpleNamespace(artist=ARTIST, date="", album_name=TITLE, show_name=TARGET,
                             venue="", location="", parentheticals="")
    config = SimpleNamespace(compliant=compliant, artist_in_album=checked)
    assert _album_for_record(config, record) == TITLE
    record.date = "1971-01-01"
    record.album_name = ""
    record.venue = "Fillmore"
    assert _album_for_record(config, record).startswith(ARTIST if checked else record.date)


@pytest.mark.parametrize("separator", ["-", "- ", " -", " – ", "—"])
def test_lossless_undated_rename(separator):
    source = ARTIST + separator + TITLE + " - Deluxe (24)"
    target = TARGET + " - Deluxe (24)"
    assert spaced_album_separator(source, ARTIST, "") == target
    assert safe_rename_target(source, target, artist=ARTIST) == (target, "")
    assert not safe_rename_target(source, TARGET, artist=ARTIST)[0]
    assert not safe_rename_target(source, target.replace("Deluxe", "Other"), artist=ARTIST)[0]


def test_physical_inventory_and_add_shows_rename(tmp_path):
    config = SimpleNamespace(rename_compliantly=True)
    for direction in ("inventory", "add"):
        parent = tmp_path / direction
        source = parent / f"{ARTIST}-{TITLE}"
        source.mkdir(parents=True)
        (source / "track.flac").write_bytes(b"original")
        if direction == "inventory":
            record = SimpleNamespace(main_dir_path=str(source), main_dir_name=source.name,
                                     artist=ARTIST, date="", album_name=TITLE, show_name=TARGET,
                                     parentheticals="")
            _, record = prepare_inventory_tagging_target(config, {"main_dir_path": str(source)}, record)
            assert Path(record.main_dir_path) == parent / TARGET
        else:
            record = dict(main_dir_path=str(source), artist=ARTIST, date="", album_name=TITLE,
                          show_name=TARGET)
            result = _rename_add_shows_folder_compliantly(config, str(source), record)
            assert Path(result) == parent / TARGET
        assert not source.exists()
        assert (parent / TARGET / "track.flac").read_bytes() == b"original"


def test_manual_name_clears_stale_performance_date():
    row = _apply_manual_name_tag_identity({"date": "1970-01-01", "venue": "Old venue"}, TARGET)
    assert row["date"] == ""
    assert row["album_name"] == TITLE


@pytest.mark.parametrize("separator", ["-", " - ", " – ", "—"])
@pytest.mark.parametrize("compliant", [True, False])
def test_extraction_from_real_artist_db(separator, compliant, tmp_path):
    from tlo_artist_db import load_artist_matcher
    from tlo_phase23_v2 import _extract_metadata_for_group

    db = ROOT / "TLO_DBs"
    matcher = load_artist_matcher(SimpleNamespace(artist_sqlite_db_file=str(db / "artists.sqlite")))
    leaf = ARTIST + separator + TITLE
    path = tmp_path / leaf
    config = SimpleNamespace(compliant=compliant, current_slam="", current_volume_label="",
                             etree_lookup=False, setlistfm_lookup=False, setlistfm_upgrade=False,
                             TLOHome=str(tmp_path), tlo_dbs_dir=str(db), artist_in_album=True)
    group = dict(group_number=1, main_dir_name=leaf, main_dir_path=str(path), setlist_file="",
                 music_file_count=1, music_dirs=[str(path)], music_files=[], setlist_files=[],
                 flac_tag_samples=[], flac_tag_artist_values=[], flac_tag_album_values=[],
                 flac_tag_albumartist_values=[], flac_tag_date_values=[])
    record, _, unresolved = _extract_metadata_for_group(config, group, matcher)
    assert not unresolved
    assert record.show_name == TARGET
    assert record.date == ""
    assert _album_for_record(config, record) == TITLE


def test_three_real_database_searches():
    # Authoritative staged catalogs, with guaranteed examples from supplied files.
    db_dir = ROOT / "TLO_DBs"
    obj = SimpleNamespace(db_path=db_dir / "artists.sqlite",
                          _validate_required_tables=aux.AuxiliarySearchApp._validate_required_tables)
    matches = aux.AuxiliarySearchApp._query_database(obj, "ABB")
    assert any(m.master_name == ARTIST and any(t.term_text.casefold() == "abb" for t in m.associated_terms)
               for m in matches)
    cities = aux.query_places(db_dir / "cities.sqlite", "City", "Boston")
    assert len(cities) > 1
    assert any("Boston, MA" in block for block in cities)
    assert len(aux.query_places(db_dir / "cities.sqlite", "City", "Bostom, MA")) == 1
    old = aux.query_places(db_dir / "venues.sqlite", "Venue", "Boston Garden")
    new = aux.query_places(db_dir / "venues.sqlite", "Venue", "TDGarden")
    assert old and old[0].startswith("Venue: Boston Garden")
    assert new and new[0].startswith("Venue: TD Garden")
    assert aux.query_places(db_dir / "venues.sqlite", "Venue", "' OR 1=1 --") == []
    assert aux.query_places(db_dir / "cities.sqlite", "City", "Impossible-City-123454321") == []


def test_database_access_is_read_only(tmp_path):
    p = tmp_path / "catalog.sqlite"
    with sqlite3.connect(p) as conn:
        conn.execute("create table sample (name text)")
    conn = aux.read_only_database(p)
    try:
        with pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("insert into sample values ('new')")
    finally:
        conn.close()
    with pytest.raises(sqlite3.OperationalError):
        aux.read_only_database(tmp_path / "missing.sqlite")
    assert not (tmp_path / "missing.sqlite").exists()


@pytest.mark.parametrize("db", ["Inventory", "Artist", "City", "Venue"])
def test_main_search_launches_requested_tool_with_clipboard(monkeypatch, tmp_path, db):
    spec = importlib.util.spec_from_file_location("main732", ROOT / "tlo-main.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []
    monkeypatch.setattr(module.subprocess, "Popen", lambda command, **kwargs: calls.append((command, kwargs)))
    home = tmp_path / "TLO Home"
    fake = SimpleNamespace(_resolve_gui_tlo_home=lambda **kw: str(home),
                           root=SimpleNamespace(clipboard_get=lambda: "Boston"))
    module.App._open_search(fake, db)
    cmd, kwargs = calls[0]
    assert cmd[0] == sys.executable
    assert Path(cmd[1]).name == ("tlo-search.py" if db == "Inventory" else "searchAuxDBs.py")
    assert cmd[2:4] == ["--TLOHome", str(home)]
    assert kwargs["shell"] is False
    assert cmd[4:] == (["--find", "Boston"] if db == "Inventory" else ["--database", db, "--find=Boston"])


@pytest.mark.gui
def test_aux_checkboxes_are_mutually_exclusive_and_search_preloads():
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display required")
    try:
        root.withdraw()
        app = aux.AuxiliarySearchApp(root, ROOT / "TLO_DBs", "City", "Boston, MA")
        root.update()
        assert app.search_var.get() == "Boston, MA"
        assert app.results_window.title() == "City DB Matches"
        def descendants(widget):
            for child in widget.winfo_children():
                yield child
                yield from descendants(child)
        choices = {w.cget("text"): w for w in descendants(root) if isinstance(w, tk.Checkbutton)}
        assert set(choices) == {"Artist", "City", "Venue"}
        choices["Venue"].invoke()
        assert app.database_var.get() == "Venue"
        choices["Venue"].invoke()
        assert app.database_var.get() == "Venue"
        assert app.db_path.name == "venues.sqlite"
        choices["Artist"].invoke()
        assert app.database_var.get() == "Artist"
    finally:
        root.destroy()
