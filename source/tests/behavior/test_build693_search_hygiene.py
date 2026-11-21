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

    master = tmp_path / 'packaged' / 'TLO_DBs' / 'cities.csv'
    master.parent.mkdir(parents=True)
    master.write_text('city,region,country,aliases\nBoston,MA,United States,\n', encoding='utf-8')
    local = tmp_path / 'local' / 'cities.csv'
    local.parent.mkdir(parents=True)
    local.write_text('city,region,country,aliases\nLowell,MA,United States,\n', encoding='utf-8')
    monkeypatch.setattr(tlo_cities, '_bundled_path', lambda: master)
    tlo_cities._cached_layered.cache_clear()
    seen = []
    catalog = tlo_cities.catalog_for_tlo(tlo_dbs_dir=str(local.parent), on_warning=seen.append)
    assert catalog is not None and catalog.lookup_exact('Boston')
    assert catalog.lookup_exact('Lowell')
    assert any('1 catalog + 1 local' in message for message in seen)
    assert not any('bundled +' in message for message in seen)
