"""Build 628: consistent preference read/write and comment handling."""
import pytest
import tlo_preferences as pref

@pytest.mark.parametrize('delimiter', ['=', ':'])
@pytest.mark.parametrize('comment', ['', '  # shared toggle', '  ; retained'])
def test_toggle_preserves_syntax_and_comments(tmp_path, delimiter, comment):
    text = pref.default_text().replace('auto_update = false', f'auto_update {delimiter} false{comment}')
    (tmp_path / pref.FILENAME).write_text(text, encoding='utf-8')
    pref.set_auto_update(tmp_path, True)
    saved = (tmp_path / pref.FILENAME).read_text(encoding='utf-8')
    assert f'auto_update {delimiter} true{comment}' in saved
    assert pref.load(tmp_path)['general']['auto_update'] is True
    assert saved.count('auto_update ') == 1


def test_inline_comments_validate_and_preserve_user_text(tmp_path):
    text = pref.default_text().replace('max_workers = 0', 'max_workers = 4 # work cap')
    text = text.replace('search_query = ', 'search_query = Jazz # Not a comment unless tokenized')
    text += '\n# user comment\n'
    pref.save_text if False else None
    (tmp_path / pref.FILENAME).write_text(pref.default_text(), encoding='utf-8')
    parsed = pref.save_text(tmp_path, text)
    assert parsed['main']['max_workers'] == 4
    assert parsed['search']['search_query'] == 'Jazz'
    assert (tmp_path / pref.FILENAME).read_text(encoding='utf-8') == text


def test_malformed_colon_value_rejected_without_mutation(tmp_path):
    pref.load(tmp_path)
    old = (tmp_path / pref.FILENAME).read_text(encoding='utf-8')
    with pytest.raises(ValueError, match=r'\[main\] max_workers'):
        pref.save_text(tmp_path, old.replace('max_workers = 0', 'max_workers: woops # invalid'))
    assert (tmp_path / pref.FILENAME).read_text(encoding='utf-8') == old


def test_bad_or_duplicate_section_does_not_toggle(tmp_path):
    text = pref.default_text().replace('[general]', '[general]\n[general]')
    (tmp_path / pref.FILENAME).write_text(text, encoding='utf-8')
    with pytest.raises(ValueError, match='Duplicate section'):
        pref.set_auto_update(tmp_path, True)
    assert (tmp_path / pref.FILENAME).read_text(encoding='utf-8') == text


pytestmark = pytest.mark.behavior
