"""Build 581: no PATH-sourced Windows GNU Make or absolute out-of-tree include."""
from pathlib import Path
import os
import subprocess

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "build_audio_ffmpeg.sh"


def test_win_make_is_absolute_trusted_posix_executable_only():
    content = SCRIPT.read_text(encoding="utf8")
    assert 'if [[ -x /usr/bin/make.exe ]]' in content
    assert 'elif [[ -x /usr/bin/make ]]' in content
    assert 'make_real="$(readlink -f -- "$make_command")"' in content
    assert 'MSYS2 POSIX Make path escaped trusted' in content
    assert '"$make_command" -j' in content
    assert 'command -v make' not in content
    assert 'mingw32-make' in content


def test_windows_configure_is_in_source_to_avoid_absolute_makefile_include():
    content = SCRIPT.read_text(encoding="utf8")
    assert 'cd -- "$source_dir"' in content
    assert 'configure_command=./configure' in content
    assert 'configure_command="${source_dir}/configure"' in content
    assert '$configure_command' in content
    assert '[[ -f "$source_dir/Makefile" ]]' in content
    assert '[[ -f Makefile ]]' in content


def test_non_windows_out_of_tree_build_preserves_source(tmp_path):
    source = tmp_path / 'src space'
    source.mkdir()
    (source / 'Makefile').write_text('# source\n')
    config = source / 'configure'
    config.write_text('#!/bin/sh\nset -e\nmkdir -p ffbuild\n'
                      'echo config > ffbuild/config.log\n'
                      'printf EXESUF= > ffbuild/config.mak\n'
                      "printf 'all: ffmpeg\\nffmpeg:\\n\\tprintf mock > ffmpeg\\n' > Makefile\n")
    config.chmod(0o755)
    dest = tmp_path / 'out space' / 'ffmpeg'
    make_dir = tmp_path / 'build space'
    env = {**os.environ, 'MSYSTEM': ''}
    result = subprocess.run(['bash', str(SCRIPT), str(source), str(dest), str(make_dir)],
                            env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr + result.stdout
    assert dest.read_bytes() == b'mock'
    assert (make_dir / 'Makefile').is_file()
    assert (source / 'Makefile').read_text() == '# source\n'


def test_synthetic_ucrt64_in_tree_configure_avoids_absolute_source_include(tmp_path):
    # Execute the actual Windows branch on a POSIX test host: the system's
    # /usr/bin/make is the trusted-path analogue to MSYS2 /usr/bin/make.exe.
    source = tmp_path / 'source with spaces'
    source.mkdir()
    (source / 'Makefile').write_text('# upstream source Makefile\n')
    configure = source / 'configure'
    configure.write_text(
        '#!/bin/sh\nset -eu\n'
        'mkdir -p ffbuild\n'
        "printf 'EXESUF=.exe\\n' > ffbuild/config.mak\n"
        "printf 'configured' > ffbuild/config.log\n"
        "printf 'all: ffmpeg.exe\\nffmpeg.exe:\\n\\tprintf built-in-tree > ffmpeg.exe\\n' > Makefile\n"
    )
    configure.chmod(0o755)
    output = tmp_path / 'out' / 'ffmpeg.exe'
    build = tmp_path / 'build_unused_out_of_tree'
    env = {**os.environ, 'MSYSTEM': 'UCRT64'}
    result = subprocess.run(
        ['bash', str(SCRIPT), str(source), str(output), str(build)],
        env=env, capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    assert output.read_bytes() == b'built-in-tree'
    assert (source / 'ffbuild' / 'config.log').is_file()
    assert not (build / 'Makefile').exists()
    assert 'FFmpeg GNU Make: /usr/bin/make ' in result.stdout
