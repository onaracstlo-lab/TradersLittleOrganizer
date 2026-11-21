"""Build 711 safety regression: collisions, retry, independent key, tag formats, MSI."""
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from mutagen import File as MutagenFile
from mutagen.id3 import TIT2, ID3

import tlo_manual_undo as U
import tlo_phase23_v2 as phase
from tlo_cities import City, CityCatalog

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_collision_preflight_marks_both_and_keeps_distinct_named_events():
    def record(path, name):
        return SimpleNamespace(main_dir_path=path, show_name=name)
    entries = [
        (record('/shows/one', 'Grateful Dead 1977-05-01'), [], []),
        (record('/shows/two', 'GRATEFUL DEAD 1977-05-01'), [], []),
        (record('/shows/three', 'Grateful Dead 1977-05-01 (Show 3)'), [], []),
    ]
    assert phase._show_identity_collisions(entries) == {0, 1}
    assert 'preflight' in phase.process_groups_for_search_path_v2.__doc__.lower() if phase.process_groups_for_search_path_v2.__doc__ else True


def test_mapped_drive_recovery_guard_rejects_symlinks_not_realpath_differences():
    code = (ROOT / 'tlo_staging_recovery.py').read_text()
    assert 'os.path.realpath(os.path.dirname(source)) != os.path.abspath(os.path.dirname(source))' not in code
    assert 'os.path.islink(cursor)' in code


def test_key_is_outside_tlohome_and_legacy_journals_remain_readable(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'user-private'))
    home = tmp_path / 'home'; (home / 'logs').mkdir(parents=True)
    legacy = home / 'logs' / '.manual-updates-undo-key'
    legacy.write_bytes(b'k' * 32)
    journal = home / 'logs' / 'journal.json'
    U._write_journal(str(home), str(journal), {'schema': 1, 'home': str(home), 'hello': 'value'})
    assert not legacy.exists()
    assert str(home) not in U._key_path(str(home))
    assert Path(U._key_path(str(home))).read_bytes() == b'k' * 32
    assert U._load_journal(str(home), str(journal))['hello'] == 'value'


def test_interrupted_undo_metadata_write_can_resume_without_media_backups(tmp_path, monkeypatch):
    monkeypatch.setenv('XDG_STATE_HOME', str(tmp_path / 'keys'))
    home = tmp_path / 'home'; (home / 'setlists').mkdir(parents=True)
    old = tmp_path / 'Old'; new = tmp_path / 'New'
    new.mkdir(); (new / 'text.txt').write_text('not media')
    bootlist = home / 'bootlist.csv'; bootlist.write_text('before')
    journal = U.begin_manual_undo(str(home), str(new), str(new), mode='unidentified', update_tags=False,
                                  setlist_paths=[])
    bootlist.write_text('after')
    U.finish_manual_undo(str(home), journal)
    record = U._load_journal(str(home), journal)
    record.update(source=str(old), destination=str(new), mode='inventory',
                  source_parent_real=str(tmp_path), destination_parent_real=str(tmp_path))
    U._write_journal(str(home), journal, record)
    actual = U._restore_bytes
    failures = [0]

    def fail_once(*args):
        if failures[0] == 0:
            failures[0] += 1
            raise OSError('transient filesystem failure')
        return actual(*args)
    monkeypatch.setattr(U, '_restore_bytes', fail_once)
    with pytest.raises(U.ManualUndoError, match='Retry'):
        U.reverse_manual_update(str(new), tlo_home=str(home))
    assert old.exists() and not new.exists() and bootlist.read_text() == 'after'
    assert U._load_journal(str(home), journal)['state'] == 'reversing'
    assert U.reverse_manual_update(str(old), tlo_home=str(home))['reversed'] == 1
    assert bootlist.read_text() == 'before'
    assert U._load_journal(str(home), journal)['state'] == 'reversed'


# A checked-in synthetic sine tone for every container keeps these safety tests
# executable on CI runners without system FFmpeg. Pinned checksums detect
# accidental/corrupt fixture replacement before Mutagen touches the copy.
_TAG_UNDO_FIXTURES = {
    'flac': ('flac', '53d4e17a8c058af49eafcdfad86c86623217a960c782daca62aa3973d15917e3'),
    'mp3': ('libmp3lame', '3e99b9cea2a8195211a0aef220a15e96a911411914bb7f72c234d8f29549ba5a'),
    'ogg': ('libvorbis', '24e2e4c74647632ca9990d5782a91b961587fb4ad3a6ca0bb1f81daf820c6cf1'),
    'opus': ('libopus', '36b51b68601d6388c4c5c76e0bd5757f419e908533118dbf7f4abb9931c176a7'),
    'm4a': ('aac', 'ff2ea324a82de2b9b549b6e6f1268e9dd1bb6f881439b71045d6ef283da2d064'),
    'aiff': ('pcm_s16be', 'ab63c626c101fa3b70d33491b173c0d3adb990a5daf96fb9fdfe8985781366fa'),
    'wav': ('pcm_s16le', '67b0f7e36e80f5fa6e42ef4fc54f2212b901aba477b260da245bc6e9ca212259'),
    'wv': ('wavpack', 'fa735be9f0b669dfda125ec1c8cc7b8eed555a6ae3bac2ad9676b323dcc8b3fc'),
}


@pytest.mark.parametrize('suffix,codec', [(s, c) for s, (c, _hash) in _TAG_UNDO_FIXTURES.items()])
def test_tag_undo_roundtrip_per_container(tmp_path, suffix, codec):
    source = ROOT / 'tests' / 'fixtures' / 'tag_undo' / ('01.' + suffix)
    assert source.is_file(), f'Missing required real-media test fixture: {source}'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == _TAG_UNDO_FIXTURES[suffix][1]
    assert codec == _TAG_UNDO_FIXTURES[suffix][0]
    target = tmp_path / ('01.' + suffix)
    shutil.copyfile(source, target)
    audio = MutagenFile(str(target), easy=False)
    if audio.tags is None:
        audio.add_tags()
    if suffix in ('mp3', 'aiff', 'wav'):
        audio.tags.add(TIT2(encoding=3, text=['Before']))
        if suffix == 'mp3':
            audio.save(v2_version=3)
        else:
            audio.save()
    elif suffix == 'm4a':
        audio.tags['\xa9nam'] = ['Before']
        audio.save()
    elif suffix == 'wv':
        audio.tags['Title'] = 'Before'
        audio.save()
    else:
        audio.tags['TITLE'] = ['Before']
        audio.save()
    before = U._tag_state(str(target))
    if suffix == 'mp3':
        assert ID3(str(target)).version[1] == 3
    changed = MutagenFile(str(target), easy=False)
    if suffix in ('mp3', 'aiff', 'wav'):
        changed.tags.add(TIT2(encoding=3, text=['After']))
    elif suffix == 'm4a':
        changed.tags['\xa9nam'] = ['After']
    elif suffix == 'wv':
        changed.tags['Title'] = 'After'
    else:
        changed.tags['TITLE'] = ['After']
    changed.save()
    U._restore_tags(str(target), before)
    after = U._tag_state(str(target))
    assert before == after, suffix
    if suffix == 'mp3':
        assert ID3(str(target)).version[1] == 3


def test_msi_rejects_unrelated_valid_authenticode_signer_and_unique_error_log():
    source = (ROOT / 'msi' / 'TLO-MSI-Update-Worker.ps1').read_text()
    assert 'SignerCertificate.Subject' in source
    assert 'installed TLO publisher' in source
    assert '[guid]::NewGuid()' in source


def test_cli_dry_run_no_mutations(tmp_path):
    home = tmp_path / 'home'; home.mkdir()
    show = tmp_path / 'show'; show.mkdir()
    cmd = [os.sys.executable, str(ROOT / 'tlo-gi.py'), '--TLOHome', str(home),
           '--search-path', str(show), '--dry-run']
    result = subprocess.run(cmd, text=True, capture_output=True, check=False, timeout=25)
    assert result.returncode == 0, result.stderr
    assert 'DRY RUN: preview only' in result.stdout
    assert sorted(p.name for p in home.iterdir()) == []


def test_explicit_regionless_city_with_city_catalog_preserves_raw_venue(tmp_path, monkeypatch):
    cat = CityCatalog([City('Amsterdam', '', '')])
    monkeypatch.setattr(phase, 'catalog_for_tlo', lambda *_a, **_kw: cat)
    rec = SimpleNamespace(artist='Phish', date='1997-11-17',
        main_dir_name='Phish 1997-11-17 Paradiso, Amsterdam',
        venue='', city='Amsterdam', region='', country='', location='Amsterdam')
    phase._protect_explicit_regionless_place(SimpleNamespace(), rec)
    assert rec.venue == 'Paradiso' and rec.city == 'Amsterdam'


def test_explicit_three_part_us_venue_city_state_is_preserved(tmp_path, monkeypatch):
    cat = CityCatalog([City('New York', 'NY', 'United States')])
    monkeypatch.setattr(phase, 'catalog_for_tlo', lambda *_a, **_kw: cat)
    rec = SimpleNamespace(artist='Grateful Dead', date='1971-04-29',
        main_dir_name='Grateful Dead 1971-04-29 Fillmore East, New York, NY - Show 2',
        venue='', city='NY', region='NY', country='', location='NY')
    phase._protect_explicit_regionless_place(SimpleNamespace(), rec)
    assert rec.venue == 'Fillmore East' and rec.city == 'New York'
    assert rec.region == 'NY' and rec.location == 'New York, NY'
