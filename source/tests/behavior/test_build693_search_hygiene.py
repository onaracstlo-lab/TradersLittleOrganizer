"""Build 693: real Search CSV semantics and low-risk hygiene regressions."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def load_search():
    spec = importlib.util.spec_from_file_location("tlo_search_build693", ROOT / "tlo-search.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_search_loads_excel_protected_leading_symbols_without_display_apostrophe(tmp_path):
    search = load_search()
    csv = tmp_path / "bootlist.csv"
    csv.write_text("sep=^\nShow^VolumePath\n'+44 2006-05-05^/plus\n'-M- 2010-03-03^/minus\n", encoding="utf-8")
    rows = search.load_bootlist_rows(csv)
    assert [r.show for r in rows] == ["+44 2006-05-05", "-M- 2010-03-03"]
    assert search.search_rows(rows, "+44") == rows[:1]
    assert search.search_rows(rows, "-M-") == rows[1:]


def test_search_formatting_identifies_utf8_and_structural_errors(tmp_path):
    search = load_search()
    csv = tmp_path / "bootlist.csv"
    csv.write_bytes(b"sep=^\nShow^VolumePath\nBeyonc\xe9^/music\n")
    with pytest.raises(UnicodeError) as error:
        search.load_bootlist_rows(csv)
    message = search.format_bootlist_search_error(csv, error.value)
    assert "bootlist.csv" in message and "CSV UTF-8" in message
    assert "No changes were made" in message
    import csv as csv_module
    bad = search.format_bootlist_search_error(csv, csv_module.Error('bad quoted row'))
    assert "Invalid bootlist.csv" in bad and "bad quoted row" in bad


def test_csv_search_gui_presents_encoding_specific_message(tmp_path, monkeypatch):
    search = load_search()
    csv = tmp_path / "bootlist.csv"
    csv.write_bytes(b"sep=^\nShow^VolumePath\nBeyonc\xe9^/music\n")
    errors = []
    monkeypatch.setattr(search.messagebox, 'showerror', lambda title, text, parent: errors.append((title, text)))
    app = object.__new__(search.BootlistSearchApp)
    app.paths = SimpleNamespace(bootlist_csv=csv)
    app.root = object()
    app._execute_csv_search('Beyonce')
    assert len(errors) == 1
    assert errors[0][0] == 'CSV search error'
    assert 'CSV UTF-8' in errors[0][1]


def test_city_diagnostic_identifies_external_catalog_instead_of_internal_bundle(tmp_path, monkeypatch):
    # Use real physical catalog files. This replaces a source-inspection-only
    # assertion with a behavior check of the warning users actually receive.
    import tlo_cities

    from tests._city_fixture import city_db
    master = city_db(tmp_path / 'packaged' / 'TLO_DBs' / 'cities.sqlite', [('Boston','MA',())])
    local = city_db(tmp_path / 'local' / 'cities.sqlite', [('Lowell','MA',())])
    monkeypatch.setattr(tlo_cities, '_bundled_path', lambda: master)
    tlo_cities._cached_catalog.cache_clear()
    assert tlo_cities.catalog_for_tlo().lookup_exact('Boston')
    catalog = tlo_cities.catalog_for_tlo(tlo_dbs_dir=str(local.parent))
    assert catalog.lookup_exact('Lowell') and not catalog.lookup_exact('Boston')
    local.write_bytes(b'invalid database')
    seen = []
    assert tlo_cities.catalog_for_tlo(tlo_dbs_dir=str(local.parent), on_warning=seen.append) is None
    assert any('SQLite city reference unavailable' in message for message in seen)
