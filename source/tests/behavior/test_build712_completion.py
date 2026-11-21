"""Build 713: linked undo chains, source-only previews and cross-root safety."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_main_lib
import tlo_manual_undo as undo
import tlo_ux

pytestmark = pytest.mark.behavior


def test_batch_undo_uses_signed_catalog_chain_and_leaves_audio_uncopied(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'private'))
    home = tmp_path / 'TLOHome'
    (home / 'setlists').mkdir(parents=True)
    folder = tmp_path / 'concert'
    folder.mkdir()
    media = folder / '01.flac'
    media.write_bytes(b'original recording placeholder that is never copied')
    boot = home / 'bootlist.csv'
    boot.write_text('before', encoding='utf-8')
    journals = []
    for value in ('first', 'second'):
        journal = undo.begin_manual_undo(str(home), str(folder), str(folder),
                                         mode='unidentified', update_tags=False,
                                         setlist_paths=[])
        boot.write_text(value, encoding='utf-8')
        undo.finish_manual_undo(str(home), journal)
        journals.append(journal)
    plan = undo.plan_manual_updates_batch(str(home), 2)
    assert [entry['journal'] for entry in plan] == journals[::-1]
    assert undo.reverse_manual_updates_batch(str(home), 2, dry_run=True)['planned'] == 2
    assert boot.read_text() == 'second'
    assert undo.reverse_manual_updates_batch(str(home), 2)['reversed'] == 2
    assert boot.read_text() == 'before'
    assert media.read_bytes() == b'original recording placeholder that is never copied'
    assert sorted(f.name for f in folder.iterdir()) == ['01.flac']
    assert all(undo._load_journal(str(home), j)['state'] == 'reversed' for j in journals)


def test_batch_refuses_later_untracked_inventory_change_without_writing(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'private'))
    home = tmp_path / 'home'
    (home / 'setlists').mkdir(parents=True)
    folder = tmp_path / 'show'
    folder.mkdir()
    boot = home / 'bootlist.csv'
    boot.write_text('earlier')
    journal = undo.begin_manual_undo(str(home), str(folder), str(folder),
                                     mode='unidentified', update_tags=False, setlist_paths=[])
    boot.write_text('committed')
    undo.finish_manual_undo(str(home), journal)
    boot.write_text('later inventory run')
    with pytest.raises(undo.ManualUndoError, match='no changes made'):
        undo.reverse_manual_updates_batch(str(home), 1)
    assert boot.read_text() == 'later inventory run'
    assert undo._load_journal(str(home), journal)['state'] == 'committed'


def test_cross_root_preflight_rejects_conflict_before_mutation(monkeypatch):
    config = SimpleNamespace(tag_during_inventory=True, tag_copy_during_inventory=False,
                             rename_compliantly=False, convert_shn=False,
                             tag_copy_and_delete_path='')
    monkeypatch.setattr(tlo_ux, '_inventory_roots', lambda _c: [('/r/a', '', ''), ('/r/b', '', '')])
    monkeypatch.setattr(tlo_ux, 'preview_operation', lambda *_a, **_kw: SimpleNamespace(
        samples=[SimpleNamespace(show_name='Band 2026-01-01', path='/r/a/one'),
                 SimpleNamespace(show_name='BAND 2026-01-01', path='/r/b/two')],
        truncated=False, issues=[]))
    with pytest.raises(RuntimeError, match='SHOW_IDENTITY_COLLISION across search paths'):
        tlo_main_lib._preflight_cross_root_show_identities(config)


def test_cross_root_preflight_refuses_incomplete_plan(monkeypatch):
    config = SimpleNamespace(tag_during_inventory=True, tag_copy_during_inventory=False,
                             rename_compliantly=False, convert_shn=False,
                             tag_copy_and_delete_path='')
    monkeypatch.setattr(tlo_ux, '_inventory_roots', lambda _c: [('/r/a', '', ''), ('/r/b', '', '')])
    monkeypatch.setattr(tlo_ux, 'preview_operation', lambda *_a, **_kw: SimpleNamespace(
        samples=[], truncated=True, issues=[]))
    with pytest.raises(RuntimeError, match='preflight incomplete'):
        tlo_main_lib._preflight_cross_root_show_identities(config)


def test_cross_root_read_only_does_not_trigger_expensive_preflight(monkeypatch):
    config = SimpleNamespace(tag_during_inventory=False, tag_copy_during_inventory=False,
                             rename_compliantly=False, convert_shn=False,
                             tag_copy_and_delete_path='')
    monkeypatch.setattr(tlo_ux, '_inventory_roots', lambda _c: [('/r/a', '', ''), ('/r/b', '', '')])
    monkeypatch.setattr(tlo_ux, 'preview_operation',
                        lambda *_a, **_kw: pytest.fail('read-only inventories must not pay preview cost'))
    tlo_main_lib._preflight_cross_root_show_identities(config)


def test_current_msi_worker_prevents_implicit_signing_certificate_rotation():
    contents = (Path(__file__).resolve().parents[2] / 'msi' /
                'TLO-MSI-Update-Worker.ps1').read_text(encoding='utf-8')
    assert '$signature.SignerCertificate.Thumbprint -ine $installedSignature.SignerCertificate.Thumbprint' in contents
    assert 'install the new verified MSI manually' in contents


def test_windows_key_acl_uses_actual_current_sid_not_account_name():
    contents = (Path(__file__).resolve().parents[2] / 'tlo_manual_undo.py').read_text(encoding='utf-8')
    assert "['whoami.exe', '/user', '/fo', 'csv', '/nh']" in contents
    assert "'icacls.exe'" in contents
    assert '/inheritance:r' in contents
    assert 'os.chmod' in contents  # POSIX retains 0700/0600 semantics
