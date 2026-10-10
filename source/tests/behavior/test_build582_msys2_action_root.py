"""Build 582: tie the Windows native FFmpeg build to setup-msys2's root."""
from pathlib import Path
from types import SimpleNamespace

import pytest
import ffmpeg_source_build as ff

pytestmark = pytest.mark.behavior


def test_hosted_windows_requires_action_root(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.delenv('TLO_MSYS2_BASH', raising=False)
    with pytest.raises(RuntimeError, match='msys2-location'):
        ff._windows_msys2_bash()


def test_hosted_windows_uses_exact_action_bash_not_preinstalled_root(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('TLO_MSYS2_BASH', r'D:\a\_temp\msys64\usr\bin\bash.exe')
    assert str(ff._windows_msys2_bash()) == r'D:\a\_temp\msys64\usr\bin\bash.exe'


def test_explicit_bash_argument_overrides_environment(monkeypatch):
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('TLO_MSYS2_BASH', 'not-the-action-root')
    explicit = Path('/tmp/synthetic/bin/bash.exe')
    assert ff._windows_msys2_bash(explicit) == explicit


def test_local_windows_fallback_preserved_without_action(monkeypatch):
    monkeypatch.delenv('GITHUB_ACTIONS', raising=False)
    monkeypatch.delenv('TLO_MSYS2_BASH', raising=False)
    assert str(ff._windows_msys2_bash()).lower() == r'c:\msys64\usr\bin\bash.exe'


def test_action_bash_reaches_compile_command(monkeypatch, tmp_path):
    native = tmp_path / 'installed-msys2' / 'usr' / 'bin'
    native.mkdir(parents=True)
    (native / 'bash.exe').touch()
    recipe = tmp_path / 'build_audio_ffmpeg.sh'
    recipe.touch()
    dest = tmp_path / 'out' / 'ffmpeg.exe'
    dest.parent.mkdir()
    monkeypatch.setenv('GITHUB_ACTIONS', 'true')
    monkeypatch.setenv('TLO_MSYS2_BASH', str(native / 'bash.exe'))
    monkeypatch.setattr(ff, '_cygpath', lambda bash, path: '/d/a/' + path.name)
    calls = []
    def pretend_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        dest.touch()
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(ff.subprocess, 'run', pretend_run)
    ff.build(tmp_path, dest, platform_name='windows', build_root=tmp_path, recipe=recipe)
    assert calls[0][0][0] == str(native / 'bash.exe')
    assert calls[0][1]['env']['MSYSTEM'] == 'UCRT64'
