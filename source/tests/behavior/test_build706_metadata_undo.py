"""Regression tests for metadata-only Manual Tweaks undo and logging clarity."""
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from mutagen.flac import FLAC
from mutagen.id3 import ID3

import tlo_manual_updates as MU
from tlo_manual_undo import ManualUndoError, reverse_manual_update
from logging_lib import setup_logging

pytestmark = pytest.mark.behavior


def _tone(path: Path, kind: str = 'flac') -> None:
    command = [
        'ffmpeg', '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
        'sine=frequency=440:duration=0.3', '-y', str(path),
    ]
    try:
        subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       check=True, timeout=20)
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        pytest.skip(f'FFmpeg is required for real audio metadata test: {exc}')


def _fixture(tmp_path: Path, monkeypatch, *, kind='flac', update_tags=True):
    home = tmp_path / 'home'
    (home / 'setlists').mkdir(parents=True)
    old = tmp_path / 'music' / 'Old Show'
    old.mkdir(parents=True)
    file_name = old / f'01.{kind}'
    _tone(file_name, kind=kind)
    if kind == 'flac':
        tags = FLAC(str(file_name))
        tags['ARTIST'] = ['Björk']
        tags['TITLE'] = ['Original Title 🎵']
        tags['ALBUM'] = ['Old Album']
        tags['CUSTOM'] = ['kept']
        tags.save()
    else:
        from mutagen.mp3 import MP3
        from mutagen.id3 import TPE1, TIT2, TALB, TXXX
        tags = MP3(str(file_name))
        if tags.tags is None:
            tags.add_tags()
        tags.tags.add(TPE1(encoding=3, text=['Björk']))
        tags.tags.add(TIT2(encoding=3, text=['Original Title']))
        tags.tags.add(TALB(encoding=3, text=['Old Album']))
        tags.tags.add(TXXX(encoding=3, desc='Test', text=['keep']))
        tags.save()
    MU.write_bootlist(str(home), [{'Show': 'Old Show', 'VolumePath': str(old)}])
    old_setlist = home / 'setlists' / 'OldShow.txt'
    old_setlist.write_text('Original setlist 🎶', encoding='utf-8')
    monkeypatch.setattr(MU, 'identify_folder_dict', lambda _cfg, folder: {
        'artist': 'Björk', 'album_name': 'New Album', 'main_dir_path': folder,
        'show_name': 'New Show',
    })

    def change_tags(_config, folder, _record):
        file_path = str(Path(folder) / f'01.{kind}')
        if kind == 'flac':
            audio = FLAC(file_path)
            audio.clear()
            audio['ARTIST'] = ['New Artist']
            audio['TITLE'] = ['New Title']
            audio.save()
        else:
            from mutagen.mp3 import MP3
            from mutagen.id3 import TPE1, TIT2
            audio = MP3(file_path)
            audio.tags.clear()
            audio.tags.add(TPE1(encoding=3, text=['New Artist']))
            audio.tags.add(TIT2(encoding=3, text=['New Title']))
            audio.save()
        return {'errors': 0, 'skipped': 0}, []

    monkeypatch.setattr(MU, '_update_manual_folder_tags', change_tags)

    def write_setlist(h, record):
        path = Path(h) / 'setlists' / 'NewShow.txt'
        path.write_text('New setlist', encoding='utf-8')
        return str(path)

    monkeypatch.setattr(MU, 'create_or_replace_generated_setlist', write_setlist)
    result = MU.apply_folder_manual_update(SimpleNamespace(TLOHome=str(home)), str(old),
                                           'New Show', update_tags=update_tags)
    return home, old, file_name, old_setlist, result


def test_build706_flac_restores_original_tags_inventory_setlist_without_audio_copies(tmp_path, monkeypatch):
    home, old, file_name, old_setlist, result = _fixture(tmp_path, monkeypatch)
    new = Path(result['new_path'])
    assert not old.exists()
    assert FLAC(str(new / file_name.name))['artist'] == ['New Artist']
    log = Path(result['undo_journal'])
    journal_text = log.read_text(encoding='ascii')
    assert 'tags_before' in journal_text and 'frames' not in journal_text
    assert log.stat().st_size < 25_000
    assert list((home / 'logs').rglob('*.flac')) == []
    assert reverse_manual_update(str(new), tlo_home=str(home), dry_run=True)['reversed'] == 0
    assert new.exists()
    assert reverse_manual_update(str(new), tlo_home=str(home))['reversed'] == 1
    assert old.exists() and not new.exists()
    restored = FLAC(str(file_name))
    assert restored['artist'] == ['Björk']
    assert restored['title'] == ['Original Title 🎵']
    assert restored['album'] == ['Old Album']
    assert restored['custom'] == ['kept']
    assert old_setlist.read_text(encoding='utf-8') == 'Original setlist 🎶'
    assert not (home / 'setlists' / 'NewShow.txt').exists()
    assert MU.read_bootlist(str(home))[0]['Show'] == 'Old Show'
    with pytest.raises(ManualUndoError, match='exactly one matching'):
        reverse_manual_update(str(new), tlo_home=str(home))


def test_build706_mp3_id3_frames_reversible_without_copy(tmp_path, monkeypatch):
    home, old, file_name, _old_setlist, result = _fixture(tmp_path, monkeypatch, kind='mp3')
    assert reverse_manual_update(result['new_path'], tlo_home=str(home))['reversed'] == 1
    tags = ID3(str(file_name))
    assert str(tags.getall('TPE1')[0].text[0]) == 'Björk'
    assert str(tags.getall('TIT2')[0].text[0]) == 'Original Title'
    assert tags.getall('TXXX:Test')[0].text[0] == 'keep'
    assert list((home / 'logs').rglob('*.mp3')) == []


def test_build706_later_audio_change_refuses_undo_without_mutation(tmp_path, monkeypatch):
    home, old, file_name, _old_setlist, result = _fixture(tmp_path, monkeypatch)
    new = Path(result['new_path'])
    edited = FLAC(str(new / file_name.name))
    edited['ARTIST'] = ['Later user edit']
    edited.save()
    with pytest.raises(ManualUndoError, match='changed after'):
        reverse_manual_update(str(new), tlo_home=str(home))
    assert new.is_dir() and not old.exists()
    assert MU.read_bootlist(str(home))[0]['Show'] == 'New Show'


def test_build706_changed_bootlist_refuses_without_mutation(tmp_path, monkeypatch):
    home, old, _file_name, _old_setlist, result = _fixture(tmp_path, monkeypatch)
    MU.write_bootlist(str(home), [{'Show': 'later', 'VolumePath': '/changed'}])
    with pytest.raises(ManualUndoError, match='inventory/setlist changed'):
        reverse_manual_update(result['new_path'], tlo_home=str(home))
    assert not old.exists()


def test_build706_tampered_metadata_journal_refuses_undo(tmp_path, monkeypatch):
    home, old, _file_name, _old_setlist, result = _fixture(tmp_path, monkeypatch)
    journal = Path(result['undo_journal'])
    payload = json.loads(journal.read_text())
    payload['record']['source'] = str(tmp_path / 'unrelated')
    journal.write_text(json.dumps(payload), encoding='ascii')
    with pytest.raises(ManualUndoError, match='integrity'):
        reverse_manual_update(result['new_path'], tlo_home=str(home), log_path=str(journal))
    assert not old.exists()


def test_build706_no_tagging_does_not_store_audio_tags(tmp_path, monkeypatch):
    home, _old, _file_name, _old_setlist, result = _fixture(tmp_path, monkeypatch, update_tags=False)
    record = json.loads(Path(result['undo_journal']).read_text())['record']
    assert record['tags_before'] == {} and record['tags_after'] == {}
    assert reverse_manual_update(result['new_path'], tlo_home=str(home))['reversed'] == 1


def test_build706_standalone_search_header_shows_actual_path(tmp_path):
    config = SimpleNamespace(TLOHome=str(tmp_path))
    setup_logging(config)
    config.logs.start_search_path('/music/test', 1, log_token='T', display_full_path=True)
    header = Path(config.logs.paths.groups).read_text(encoding='utf-8')
    assert '# groupsLog for search path: /music/test' in header
    assert 'SEARCH_PATH: /music/test' in header
    assert 'SEARCH_PATH: []' not in header


@pytest.mark.skipif(os.name == 'nt', reason='POSIX byte filenames only')
def test_build706_non_utf8_directory_has_readable_path_warning(tmp_path, monkeypatch):
    from initial_dir_walk_lib import initial_dir_walk
    import initial_dir_walk_lib as IW
    home = tmp_path / 'home'
    home.mkdir()
    root = tmp_path / 'music'
    root.mkdir()
    bad_dir = os.fsdecode(os.fsencode(str(root)) + b'/bad-\xff')
    os.mkdir(bad_dir)
    Path(bad_dir, 'song.flac').write_bytes(b'x')
    messages = []
    monkeypatch.setattr(IW, 'console_emit', messages.append)
    config = SimpleNamespace(TLOHome=str(home), performance_mode='balanced', dry_run=False)
    setup_logging(config)
    config.logs.start_search_path(str(root), 1)
    initial_dir_walk(config, str(root))
    assert any('bad-\\xff' in m and 'bytes_hex=' in m for m in messages)
    assert 'UNIDENTIFIED_NON_UTF8_PATH:' in (home / 'unidentifiedShows.txt').read_text()


def test_build706_unidentified_undo_restores_unidentified_and_tags(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    (home / 'setlists').mkdir(parents=True)
    unknown = tmp_path / 'old' / 'Mystery'
    final = tmp_path / 'dest' / 'Named Show'
    final.mkdir(parents=True)
    audio_file = final / '01.flac'
    _tone(audio_file)
    old_tags = FLAC(str(audio_file))
    old_tags['ARTIST'] = ['Кино']
    old_tags['TITLE'] = ['Группа крови']
    old_tags.save()
    (home / 'unidentifiedShows.txt').write_text(str(unknown) + '\n', encoding='utf-8')
    monkeypatch.setattr(MU, 'identify_folder_dict', lambda _cfg, folder: {
        'show_name': 'Named Show', 'main_dir_path': folder,
    })

    def tag_change(_cfg, folder, _rec):
        audio = FLAC(str(Path(folder) / '01.flac'))
        audio['ARTIST'] = ['Wrong Artist']
        audio.save()
        return {'errors': 0, 'skipped': 0}, []

    def make_setlist(h, _rec):
        target = Path(h) / 'setlists' / 'NamedShow.txt'
        target.write_text('Generated', encoding='utf-8')
        return str(target)

    monkeypatch.setattr(MU, '_update_manual_folder_tags', tag_change)
    monkeypatch.setattr(MU, 'create_or_replace_generated_setlist', make_setlist)
    result = MU.apply_unidentified_manual_update(
        SimpleNamespace(TLOHome=str(home)), str(unknown), 'Named Show', str(final.parent),
        update_tags=True,
    )
    assert FLAC(str(audio_file))['artist'] == ['Wrong Artist']
    assert not (home / 'unidentifiedShows.txt').read_text()
    reverse_manual_update(str(final), tlo_home=str(home))
    assert final.exists() and not unknown.exists()  # Never moves an unidentified show
    assert FLAC(str(audio_file))['artist'] == ['Кино']
    assert FLAC(str(audio_file))['title'] == ['Группа крови']
    assert (home / 'unidentifiedShows.txt').read_text() == str(unknown) + '\n'
    assert MU.read_bootlist(str(home)) == []
    assert result['undo_journal'].endswith('.json')


def test_build706_failed_update_rolls_back_tag_metadata_without_media_copy(tmp_path, monkeypatch):
    home = tmp_path / 'home'
    (home / 'setlists').mkdir(parents=True)
    old = tmp_path / 'music' / 'Old Show'
    old.mkdir(parents=True)
    audio_file = old / '01.flac'
    _tone(audio_file)
    audio = FLAC(str(audio_file))
    audio['ARTIST'] = ['Original Artist']
    audio.save()
    MU.write_bootlist(str(home), [{'Show': 'Old Show', 'VolumePath': str(old)}])
    monkeypatch.setattr(MU, 'identify_folder_dict', lambda _cfg, folder: {
        'show_name': 'New Show', 'artist': 'Other', 'main_dir_path': folder,
    })

    def fail_after_changing_tags(_cfg, folder, _record):
        changed = FLAC(str(Path(folder) / '01.flac'))
        changed['ARTIST'] = ['Wrong']
        changed.save()
        raise RuntimeError('simulated tag write interrupted')

    monkeypatch.setattr(MU, '_update_manual_folder_tags', fail_after_changing_tags)
    with pytest.raises(MU.ManualUpdateError, match='simulated tag write interrupted'):
        MU.apply_folder_manual_update(SimpleNamespace(TLOHome=str(home)),
                                      str(old), 'New Show', update_tags=True)
    assert old.is_dir() and not (old.parent / 'New Show').exists()
    assert FLAC(str(audio_file))['artist'] == ['Original Artist']
    assert MU.read_bootlist(str(home))[0]['Show'] == 'Old Show'
    assert list((home / 'logs').rglob('*.flac')) == []
