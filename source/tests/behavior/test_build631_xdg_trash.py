"""Build 631: recoverable XDG Trash without gio, preserving originals on errors."""
import pytest
import tlo_corruption as C


def test_xdg_trash_round_trip_file_and_metadata(tmp_path, monkeypatch):
    home = tmp_path / 'home'; home.mkdir()
    monkeypatch.setenv('HOME', str(home)); monkeypatch.delenv('XDG_DATA_HOME', raising=False)
    src = home / 'a recording.shn'; src.write_bytes(b'important source')
    C._trash_linux_xdg(str(src))
    assert not src.exists()
    files = list((home / '.local/share/Trash/files').iterdir())
    info = list((home / '.local/share/Trash/info').iterdir())
    assert len(files) == len(info) == 1
    assert files[0].read_bytes() == b'important source'
    assert f'Path={str(src).replace(" ", "%20")}' in info[0].read_text()


def test_xdg_trash_name_collision_preserves_both(tmp_path, monkeypatch):
    home = tmp_path / 'home'; home.mkdir(); monkeypatch.setenv('HOME', str(home))
    src = home / 'same.flac'
    for content in (b'first', b'second'):
        src.write_bytes(content)
        C._trash_linux_xdg(str(src))
    files = list((home / '.local/share/Trash/files').iterdir())
    assert len(files) == 2
    assert {p.read_bytes() for p in files} == {b'first', b'second'}


def test_xdg_rename_failure_keeps_source(tmp_path, monkeypatch):
    home = tmp_path / 'home'; home.mkdir(); monkeypatch.setenv('HOME', str(home))
    src = home / 'original.shn'; src.write_bytes(b'unchanged')
    def broken(src_, dest_):
        raise OSError('simulated volume loss')
    monkeypatch.setattr(C.os, 'rename', broken)
    with pytest.raises(OSError, match='simulated'):
        C._trash_linux_xdg(str(src))
    assert src.read_bytes() == b'unchanged'
    assert not list((home / '.local/share/Trash/info').iterdir())


def test_xdg_missing_home_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('HOME', str(tmp_path / 'absent'))
    src = tmp_path / 'saved.shn'; src.write_bytes(b'original')
    with pytest.raises(OSError, match='home directory'):
        C._trash_linux_xdg(str(src))
    assert src.read_bytes() == b'original'


def test_xdg_rejects_symlink_source(tmp_path, monkeypatch):
    home = tmp_path / 'home'; home.mkdir(); monkeypatch.setenv('HOME', str(home))
    real = home / 'real'; real.write_text('x'); link = home / 'link'; link.symlink_to(real)
    with pytest.raises(OSError, match='symlink'):
        C._trash_linux_xdg(str(link))
    assert link.is_symlink() and real.read_text() == 'x'


pytestmark = pytest.mark.behavior
