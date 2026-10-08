"""Build 558: documentation and user-facing copy/corruption policy regression tests."""
from __future__ import annotations
from tests._release_artifacts import release_history

from pathlib import Path
from types import SimpleNamespace

from docx import Document
import pytest

import tlo_options
import tlo_ux
from tests import _release_artifacts as A

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _req() -> str:
    return '\n'.join(p.text for p in Document(ROOT / A.REQUIREMENTS_FILENAME).paragraphs)


def test_build558_only_artist_album_checked_by_default_and_corruption_defaults_untouched():
    selected = {o.config_field for o in tlo_options.GUI_CHECKBOX_OPTIONS if bool(o.default)}
    assert selected == {'artist_in_album'}
    assert tlo_options.OPTIONS_BY_FIELD['deep_audio_check'].default is False
    assert tlo_options.OPTIONS_BY_FIELD['corrupt_files'].default == 'delete'
    assert tlo_options.OPTIONS_BY_FIELD['corrupt_folders'].default == 'all'


def test_build558_manual_explains_no_dry_run_deletion_and_clear_real_run_choice():
    rtf = (ROOT / A.MANUAL_FILENAME).read_text(encoding='utf-8')
    assert 'Artist In Album Tag is the only checkbox selected by default' in rtf
    assert 'If you do not want to move any corrupt files or folders' in rtf
    assert 'Dry Run never moves, Trashes, or deletes files or folders' in rtf
    assert 'regardless of the Corruption Handling settings' in rtf
    assert 'When selected, Deep Audio Check may read and decode' in rtf
    assert 'Build 558 - ' in release_history()


def test_build558_corruption_requirements_and_faq_match_behavior():
    req = _req()
    faq = (ROOT / 'TLO-FAQ.txt').read_text(encoding='utf-8')
    assert 'Dry Run must not write or restore a probe tag, rename, copy, move, Trash, or delete' in req
    assert 'readable header is not a guarantee of complete-stream integrity' in req
    assert 'successfully parsed header alone does not establish' in req
    assert 'Dry Run never moves or deletes files or folders' in faq
    assert 'a readable header does not prove the complete recording decodes' in faq


def test_build558_cli_and_review_copy_policy_are_mode_specific():
    tag_copy=tlo_options.OPTIONS_BY_FIELD['tag_copy_during_inventory'].help
    tag_copy_delete=tlo_options.OPTIONS_BY_FIELD['tag_copy_and_delete_enabled'].help
    assert 'folder structure' in tag_copy and 'file sizes' in tag_copy
    assert 'SHA-256' not in tag_copy
    assert 'directory moves' in tag_copy_delete and 'SHA-256' in tag_copy_delete
    config=SimpleNamespace(tag_copy_and_delete_path='/tmp/copies', rename_compliantly=False,
                           convert_shn=False, tag_during_inventory=False, tag_copy_during_inventory=False)
    actions=tlo_ux._preview_actions(config)
    assert any('SHA-256' in a and 'remove original' in a for a in actions)


def test_build558_transfer_reference_clarifies_different_verification_strengths():
    req=_req()
    faq=(ROOT / 'TLO-FAQ.txt').read_text(encoding='utf-8')
    gui=(ROOT / 'tlo-main.py').read_text(encoding='utf-8')
    assert 'Cross-filesystem Copy/Delete Original must additionally compare SHA-256 contents' in req
    assert 'ordinary Tag Copy does not require content hashing' in req
    assert 'Ordinary Tag Copy verifies the recursive relative file and folder structure and file sizes' in faq
    assert 'Cross-partition Copy/Delete Original additionally verifies SHA-256 contents' in faq
    assert 'SHA-256 contents, before deleting the original' in gui
