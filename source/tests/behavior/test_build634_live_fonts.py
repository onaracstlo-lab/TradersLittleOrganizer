"""Build 638 supersedes Build 634: preferences (including fonts) apply next launch only."""
from pathlib import Path
import pytest
import tlo_preferences as pref

ROOT = Path(__file__).resolve().parents[2]


def test_invalid_preferences_still_rejected(tmp_path):
    pref.load(tmp_path)
    text = pref.default_text().replace('font_size = 0', 'font_size = 1000')
    with pytest.raises(ValueError, match='font_size'):
        pref.save_text(tmp_path, text)


def test_font_changes_are_only_saved_for_next_launch(tmp_path):
    current_session = pref.load(tmp_path)
    modified_text = pref.default_text().replace('font_size = 0', 'font_size = 16')
    pref.save_text(tmp_path, modified_text)
    assert current_session['main']['font_size'] == 0
    assert current_session['search']['font_size'] == 0
    assert pref.load(tmp_path)['main']['font_size'] == 16
    assert pref.load(tmp_path)['search']['font_size'] == 16


def test_gui_has_no_live_preferences_refresh():
    main = (ROOT / 'tlo-main.py').read_text(encoding='utf-8')
    search = (ROOT / 'tlo-search.py').read_text(encoding='utf-8')
    assert '_apply_live_cosmetic_preferences' not in main
    assert '_apply_live_cosmetic_preferences' not in search
    assert 'on_saved=' not in main and 'on_saved=' not in search
    assert 'tlo_preferences.edit(self.root, tlo_home)' in main
    assert 'tlo_preferences.edit(self.root, self.paths.tlohome)' in search


pytestmark = pytest.mark.behavior
