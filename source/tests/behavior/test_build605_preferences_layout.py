"""Build 605: approved concise startup preferences template is release-stable."""

from pathlib import Path
import pytest
import tlo_preferences as pref

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
EXPECTED_SHA256 = "4d70521d2199bd3e63994466dc1e5003f574d1bc464d8346757a7e0f07caa524"


def test_approved_template_matches_exact_user_format():
    actual = (ROOT / pref.FILENAME).read_text(encoding='utf-8')
    # Build 630+ updates the safety defaults; keep the embedded template and distributed INI equal.
    assert pref.default_text() == actual
    assert pref.parse_text(actual) == pref.DEFAULTS
    assert actual.count('true | false') == 1


def test_first_startup_writes_approved_template_without_clobbering(tmp_path):
    pref.load(tmp_path)
    path = pref.path_for(tmp_path)
    assert path.read_text(encoding='utf-8') == pref.default_text()
    path.write_text(path.read_text(encoding='utf-8').replace('max_workers = 0', 'max_workers = 12'), encoding='utf-8')
    assert pref.load(tmp_path)['main']['max_workers'] == 12
    assert 'max_workers = 12' in path.read_text(encoding='utf-8')


def test_auto_update_option_preserves_layout_and_validation(tmp_path):
    text = pref.default_text(auto_update=True)
    assert pref.parse_text(text)['general']['auto_update'] is True
    assert text.replace('auto_update = true', 'auto_update = false', 1) == pref.default_text()
    pref.load(tmp_path)
    saved = pref.path_for(tmp_path).read_bytes()
    with pytest.raises(ValueError, match=r'Line .*performance_mode'):
        pref.save_text(tmp_path, pref.default_text().replace('performance_mode = balanced', 'performance_mode = turbo'))
    assert pref.path_for(tmp_path).read_bytes() == saved


def test_allowed_values_remain_documented_for_nonnumeric_modes():
    contents = pref.default_text()
    for (section, field), options in pref.CHOICES.items():
        assert f'# {field}: ' + ' | '.join(options) in contents
    assert '0 (automatic for Performance Mode) or 1-256' in contents
    assert 'case preserved' in contents
