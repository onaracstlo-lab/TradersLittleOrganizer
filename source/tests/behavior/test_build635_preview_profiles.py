"""Build 638 retirement contract for the short-lived Build 635 Startup Profiles."""
from pathlib import Path
import pytest
import tlo_preferences as prefs

ROOT = Path(__file__).resolve().parents[2]


def test_startup_profiles_removed_from_release():
    main = (ROOT / 'tlo-main.py').read_text(encoding='utf-8')
    assert 'Startup Profiles (preview)' not in main
    assert '_preview_startup_profile' not in main
    assert 'tlo_profiles' not in main
    assert not (ROOT / 'tlo_profiles.py').exists()


def test_one_preferences_file_is_preserved(tmp_path):
    old = prefs.load(tmp_path)
    assert old['main']['artist_in_album'] is True
    assert [path.name for path in tmp_path.iterdir()] == [prefs.FILENAME]
    assert prefs.load(tmp_path) == old


pytestmark = pytest.mark.behavior
