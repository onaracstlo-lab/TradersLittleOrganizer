"""Build 577: FFmpeg source configure and MSYS2 path hygiene regressions."""
from pathlib import Path
from types import SimpleNamespace

import pytest

import ffmpeg_source_build as ff

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_native_recipes_do_not_use_removed_postproc_flag():
    script = (ROOT / 'build_audio_ffmpeg.sh').read_text(encoding='utf-8')
    assert '--disable-postproc' not in script
    assert '--disable-postproc' not in ff.CONFIGURE_FLAGS
    for token in ('--disable-everything', '--enable-encoder=flac',
                  '--enable-decoder=shorten', '--enable-demuxer=shorten',
                  '--enable-muxer=flac,null,framemd5'):
        assert token in script


def test_cygpath_direct_invocation_discards_shell_startup(monkeypatch, tmp_path):
    bin_dir = tmp_path / 'usr' / 'bin'
    bin_dir.mkdir(parents=True)
    (bin_dir / 'bash.exe').touch()
    (bin_dir / 'cygpath.exe').touch()
    observed = []

    def fake_run(cmd, **kwargs):
        observed.append((cmd, kwargs))
        return SimpleNamespace(stdout='/d/a/native build/source\n')

    monkeypatch.setattr(ff.subprocess, 'run', fake_run)
    result = ff._cygpath(bin_dir / 'bash.exe', Path('D:/native build/source'))
    assert result == '/d/a/native build/source'
    assert observed[0][0][0].endswith('cygpath.exe')
    assert observed[0][0][1] == '-u'
    assert '-lc' not in observed[0][0]


@pytest.mark.parametrize('polluted', [
    'Copying skeleton files.\n/d/a/source\n',
    '/d/a/source\n/d/a/extra\n',
    'relative/source\n',
    '\n',
])
def test_cygpath_rejects_non_path_output(monkeypatch, tmp_path, polluted):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    (bin_dir / 'cygpath.exe').touch()
    monkeypatch.setattr(ff.subprocess, 'run', lambda *a, **kw: SimpleNamespace(stdout=polluted))
    with pytest.raises(RuntimeError, match='invalid or non-path'):
        ff._cygpath(bin_dir / 'bash.exe', Path('C:/somewhere'))


def test_windows_build_initializes_ucrt64_and_preserves_separate_args(monkeypatch, tmp_path):
    bash = tmp_path / 'bash.exe'
    bash.touch()
    recipe = tmp_path / 'build script.sh'
    recipe.write_text('#!/usr/bin/env bash\n', encoding='utf-8')
    source = tmp_path / 'source dir'
    source.mkdir()
    output = tmp_path / 'ffmpeg.exe'
    directory = tmp_path / 'build dir'
    observed = {}
    def fake_run(cmd, **kwargs):
        observed['cmd'] = cmd
        observed['env'] = kwargs['env']
        output.touch()
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(ff, '_cygpath', lambda bash_arg, path: '/d/a/' + path.name)
    monkeypatch.setattr(ff.subprocess, 'run', fake_run)
    assert ff.build(source, output, platform_name='windows', build_root=directory,
                    recipe=recipe, bash=bash) == output
    cmd = observed['cmd']
    assert cmd[:2] == [str(bash), '-c']
    assert 'exec bash "$@"' in cmd[2]
    assert '/ucrt64/bin:/usr/bin:/bin' in cmd[2]
    assert '/etc/profile' not in cmd[2]
    assert cmd[4:] == ['/d/a/build script.sh', '/d/a/source dir',
                       '/d/a/ffmpeg.exe', '/d/a/build dir']
    assert observed['env']['MSYSTEM'] == 'UCRT64'


def test_windows_build_rejects_missing_compiler_shell(tmp_path):
    recipe = tmp_path / 'r.sh'
    recipe.touch()
    with pytest.raises(RuntimeError, match='UCRT64 Bash'):
        ff.build(tmp_path, tmp_path / 'out.exe', platform_name='windows',
                 build_root=tmp_path, recipe=recipe, bash=tmp_path / 'absent.exe')
