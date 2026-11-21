"""Build 686 safety regressions for the v685 independent deep review."""
import importlib.util
import sys
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest
pytestmark = pytest.mark.behavior

import logging_lib
from tlo_bootlist_volume_policy import validate_bootlist_utf8
from tlo_postprocess import _write_bootlist_csv
from tlo_rename_safety import safe_rename_target
from tlo_reverse_folders import prepare_reverse_plan

ROOT = Path(__file__).resolve().parents[2]


def test_numeric_source_ids_dates_and_resolution_never_rename_lossily():
    for source, target in [
        ('Phish 1997-11-28 Worcester 101589', 'Phish 1997-11-28 The Centrum Worcester, MA'),
        ('Grateful Dead 1977-05-08 Ithaca 24-96', 'Grateful Dead 1977-05-08 Barton Hall Ithaca, NY'),
        ('Dead 1977-05-08 Ithaca', 'Dead 1977-05-09 Ithaca'),
    ]:
        result, reason = safe_rename_target(source, target, artist=source.split()[0], date='1977-05-08')
        assert result == '', (source, result)
        assert reason


def test_child_prune_archives_only_removed_reverse_ops(tmp_path):
    home = tmp_path / 'home'
    logs = home / 'logs'
    logs.mkdir(parents=True)
    a = tmp_path / 'music' / 'area1'
    b = tmp_path / 'music' / 'area2'
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    (a / 'After').mkdir()
    (b / 'After').mkdir()
    op_a = f'RENAME_COMPLIANTLY: {a / "Before"} -> {a / "After"}\n'
    op_b = f'RENAME_COMPLIANTLY: {b / "Before"} -> {b / "After"}\n'
    (logs / 'tags0.txt').write_text(op_a + op_b, encoding='utf-8')
    logging_lib.prune_logs_for_tokens_and_paths(str(home), ['0'], [str(a)])
    archive = (logs / 'folderOperations.log').read_text(encoding='utf-8')
    assert op_a in archive and op_b not in archive
    assert op_b in (logs / 'tags0.txt').read_text(encoding='utf-8')
    plan = prepare_reverse_plan(str(b / 'After'), tlo_home=str(home))
    assert len(plan.operations) == 1
    logging_lib.prune_logs_for_tokens_and_paths(str(home), ['0'], [str(a)])
    assert (logs / 'folderOperations.log').read_text(encoding='utf-8') == archive


def test_bootlist_encoding_is_preflighted_without_modification(tmp_path):
    payload = b'sep=^\nShow^VolumePath\nBeyonc\xe9^/archive/show\n'
    (tmp_path / 'bootlist.csv').write_bytes(payload)
    with pytest.raises(ValueError, match=r'bootlist.csv.*UTF-8.*CSV UTF-8'):
        validate_bootlist_utf8(str(tmp_path))
    assert (tmp_path / 'bootlist.csv').read_bytes() == payload


def test_formula_escape_and_atomic_writer_preserve_search_identity(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location('tlo_search_686', ROOT / 'tlo-search.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    rows = [{'Show': '+44 2006-05-05', 'VolumePath': '[Disk] /music/+44', 'Setlist': 'plus44.txt'},
            {'Show': '-M- 2010-03-03', 'VolumePath': '[Disk] /music/-M-', 'Setlist': 'minusm.txt'}]
    file_path = Path(_write_bootlist_csv(str(tmp_path), rows))
    data = file_path.read_text(encoding='utf-8')
    assert "'+44" in data and "'-M-" in data
    found = module.load_bootlist_rows(file_path)
    assert [row.show for row in found] == ['+44 2006-05-05', '-M- 2010-03-03']
    index = (tmp_path / 'setlist-index.json').read_text(encoding='utf-8')
    assert '"show": "+44 2006-05-05"' in index
    # An os.replace failure must leave the existing master CSV untouched.
    original = file_path.read_bytes()
    def fail_replace(*_args):
        raise OSError('forced write failure')
    monkeypatch.setattr('tlo_bootlist_volume_policy.os.replace', fail_replace)
    with pytest.raises(OSError, match='forced'):
        _write_bootlist_csv(str(tmp_path), [{'Show': '=EVIL', 'VolumePath': '[Disk] /bad'}])
    assert file_path.read_bytes() == original


def test_msi_start_menu_shortcut_for_artist_search(tmp_path):
    spec = importlib.util.spec_from_file_location('tlo_wix_686', ROOT / 'msi' / 'generate_wix.py')
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    stage = tmp_path / 'stage'
    stage.mkdir()
    for filename in ('tlo-main.exe', 'tlo-search.exe', 'search-artist-db.exe'):
        (stage / filename).write_bytes(b'fake stage executable')
    wxs = tmp_path / 'test.wxs'
    gen.generate(stage, wxs, '1.7.686')
    tree = ET.parse(wxs)
    node = tree.find('.//{*}Shortcut[@Id="TLOArtistDatabaseSearchShortcut"]')
    assert node is not None
    assert node.attrib['Name'] == 'TLO Artist Database Search'
    assert node.attrib['Target'].endswith('search-artist-db.exe')


def test_invalid_bootlist_aborts_actual_inventory_before_scanning_or_tagging(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import tlo_main_lib

    (tmp_path / 'bootlist.csv').write_bytes(b'sep=^\nShow^VolumePath\nBad\xe9^/bad\n')
    calls = []
    monkeypatch.setattr(tlo_main_lib, 'walk_trees', lambda _cfg: calls.append('scan'))
    cfg = SimpleNamespace(TLOHome=str(tmp_path), silent=True)
    assert tlo_main_lib.run_inventory(cfg) == 1
    assert calls == []
    assert (tmp_path / 'bootlist.csv').read_bytes().endswith(b'Bad\xe9^/bad\n')


def test_multiple_path_prompt_close_does_not_start_reinventory():
    try:
        import tkinter as tk
        root = tk.Tk()
    except (ImportError, tk.TclError if 'tk' in locals() else ImportError):
        pytest.skip('Tk display is required')
    try:
        spec = importlib.util.spec_from_file_location('tlo_main_686', ROOT / 'tlo-main.py')
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        app = object.__new__(mod.App)
        app.root = root

        def close():
            for win in root.winfo_children():
                if isinstance(win, tk.Toplevel):
                    root.tk.call(win.protocol('WM_DELETE_WINDOW'))
                    return
        root.after(180, close)
        result = app._ask_multiple_existing_path_actions([
            {'item_index': 0, 'volume': 'Disk', 'path': '/a', 'related_count': 1},
            {'item_index': 1, 'volume': 'Disk', 'path': '/b', 'related_count': 1},
        ])
        assert result == {0: 'skip', 1: 'skip'}
    finally:
        root.destroy()


def test_release_hygiene_catches_stale_documents_and_unused_test_imports(tmp_path):
    import shutil
    import subprocess

    # Exercise the actual offline checker on a minimal fake source tree so it
    # cannot pass merely by checking that a literal helper name exists.
    fake = tmp_path / 'stage'
    (fake / 'tests').mkdir(parents=True)
    from tests import _release_artifacts as artifacts
    shutil.copy2(ROOT / artifacts.REQUIREMENTS_FILENAME, fake)
    shutil.copy2(ROOT / artifacts.MANUAL_FILENAME, fake)
    bad = fake / 'tests' / 'test_bad.py'
    bad.write_text('import json\n\ndef test_ok():\n    assert True\n', encoding='utf-8')
    script = ROOT / 'tools' / 'check_release_hygiene.py'
    args = [sys.executable, str(script), '--source-root', str(fake), '--build-number', str(__import__('tlo_version').BUNDLE_BUILD)]
    failed = subprocess.run(args, capture_output=True, text=True, check=False)
    assert failed.returncode == 1 and 'possibly unused import json' in failed.stdout
    bad.write_text('import json\n\ndef test_ok():\n    assert json.loads("true")\n', encoding='utf-8')
    clean = subprocess.run(args, capture_output=True, text=True, check=False)
    assert clean.returncode == 0, clean.stdout + clean.stderr
