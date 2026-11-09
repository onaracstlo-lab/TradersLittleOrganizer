import pytest
"""Build 630: new installations keep bad files, old preferences survive."""
import tlo_preferences as P
from tlo_options import OPTIONS_BY_FIELD
from inventory_parser_lib import Config

def test_new_install_keep_never(tmp_path):
    settings = P.load(tmp_path)
    assert (settings['main']['corrupt_files'], settings['main']['corrupt_folders']) == ('keep', 'never')
    assert OPTIONS_BY_FIELD['corrupt_files'].default == 'keep'
    assert OPTIONS_BY_FIELD['corrupt_folders'].default == 'never'
    assert Config(False, False, str(tmp_path)).corrupt_files == 'keep'
    assert Config(False, False, str(tmp_path)).corrupt_folders == 'never'
    assert 'corrupt_files = keep' in P.path_for(tmp_path).read_text()

def test_existing_explicit_deletion_settings_unchanged(tmp_path):
    content = P.default_text().replace('corrupt_files = keep', 'corrupt_files = delete').replace(
        'corrupt_folders = never', 'corrupt_folders = all')
    P.path_for(tmp_path).write_text(content)
    settings = P.load(tmp_path)
    assert (settings['main']['corrupt_files'], settings['main']['corrupt_folders']) == ('delete', 'all')
    assert P.path_for(tmp_path).read_text() == content

def test_no_silent_deletion_default_with_tagging(tmp_path):
    content = P.default_text().replace('tag_during_inventory = false', 'tag_during_inventory = true')
    P.path_for(tmp_path).write_text(content)
    values = P.load(tmp_path)['main']
    assert values['tag_during_inventory'] is True
    assert values['corrupt_files'] == 'keep' and values['corrupt_folders'] == 'never'


pytestmark = pytest.mark.behavior
