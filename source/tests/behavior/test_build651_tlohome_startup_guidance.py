"""Build 651: useful missing-TLOHome startup messages and working examples."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest

from tlo_path_inputs import resolve_tlo_home
from tlo_startup_help import (SETUP_HEADING,
                              missing_tlo_home_message, report_missing_tlo_home)
from tlo_version import BUNDLE_BUILD

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _entry(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), ROOT / name)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module


@pytest.mark.parametrize("app", ["tlo-main", "tlo-search", "tlo-tag", "tlo-gi",
                                  "tlo-research", "tlo-reverse", "tlo-deleteDupes"])
def test_complete_copyable_examples_use_actual_executable(app):
    message = missing_tlo_home_message(app)
    windows = f'"C:\\.tlo\\apps\\Windows\\{app}.exe" --TLOHome "C:\\.tlo"'
    linux = f'"/mnt/c/.tlo/apps/Linux/{app}" --TLOHome "/mnt/c/.tlo"'
    assert message.startswith(SETUP_HEADING)
    assert message.count(windows) == 2
    assert linux in message
    assert "Windows shortcut" in message and "Target field" in message
    assert "set TLOHome" in message
    assert "https://traderslittleorganizer.com" in message
    assert "actual folder" in message


def test_shared_resolver_uses_help_only_when_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("TLOHome", raising=False)
    with pytest.raises(ValueError, match="TLOHome is not set") as error:
        resolve_tlo_home(app_name="tlo-tag")
    assert 'tlo-tag.exe' in str(error.value)
    p = tmp_path / 'tlo'; p.mkdir()
    assert resolve_tlo_home(tlo_home=str(p), app_name="tlo-tag") == str(p)
    with pytest.raises(ValueError, match="does not exist"):
        resolve_tlo_home(tlo_home=str(tmp_path/'missing'))


def test_main_blocks_unconfigured_startup_before_creating_root(monkeypatch):
    app = _entry('tlo-main.py')
    monkeypatch.setattr(sys, 'argv', ['tlo-main'])
    monkeypatch.delenv('TLOHome', raising=False)
    monkeypatch.setattr(app, 'report_missing_tlo_home', lambda name: 2 if name=='tlo-main' else 1)
    monkeypatch.setattr(app, 'create_tk_root', lambda *_: pytest.fail('GUI opened without home'))
    assert app.main() == 2


def test_search_displays_same_setup_guidance_not_generic_error(monkeypatch):
    app = _entry('tlo-search.py')
    monkeypatch.delenv('TLOHome', raising=False)
    called=[]
    monkeypatch.setattr(app, 'report_missing_tlo_home', lambda name: called.append(name) or 2)
    monkeypatch.setattr(app, 'show_config_error_dialog', lambda *_: pytest.fail('generic error dialog used'))
    assert app.main([]) == 2
    assert called==['tlo-search']


def test_no_display_prints_complete_instructions(monkeypatch, capsys):
    import tlo_startup_help as help_module
    monkeypatch.setattr(help_module, 'show_missing_tlo_home_dialog',
                        lambda _app: (_ for _ in ()).throw(RuntimeError('No display')))
    assert report_missing_tlo_home('tlo-search') == 2
    stderr = capsys.readouterr().err
    assert 'tlo-search.exe' in stderr
    assert SETUP_HEADING in stderr
    assert 'https://traderslittleorganizer.com' in stderr


def test_release_artifacts_and_versioned_requirements():
    from docx import Document
    assert BUNDLE_BUILD >= 651
    docs = list(ROOT.glob('TLO_Inventory_Requirements_Working_v*.docx'))
    assert len(docs) == 1
    text = '\n'.join(p.text for p in Document(docs[0]).paragraphs)
    assert 'Copy Instructions' in text
    assert 'C:\\.tlo\\apps\\Windows\\tlo-main.exe' in text
    assert 'https://traderslittleorganizer.com' in text
