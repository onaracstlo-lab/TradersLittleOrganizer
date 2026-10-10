"""Build 583: reproduce FFmpeg 9's platform-specific EXESUF target and test packaging."""
import os
import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / 'build_audio_ffmpeg.sh'


def _fixture(tmp_path, *, windows: bool, valid_binary: bool = True):
    source = tmp_path / 'FFmpeg source with spaces'
    source.mkdir()
    (source / 'Makefile').write_text('# verified FFmpeg upstream source placeholder\n')
    cfg = source / 'configure'
    suffix = '.exe' if windows else ''
    target = 'ffmpeg' + (suffix if valid_binary else '')
    cfg.write_text(
        '#!/bin/sh\nset -eu\nmkdir -p ffbuild\n'
        + 'printf %s EXESUF=' + suffix + ' > ffbuild/config.mak\n'
        + 'echo configure-ok > ffbuild/config.log\n'
        + "cat > Makefile <<'EOF'\n"
        + 'all: ' + target + '\n'
        + target + ':\n\tprintf native-ffmpeg > ' + target + '\n'
        + 'EOF\n'
    )
    cfg.chmod(0o755)
    output = tmp_path / 'packaged executable' / ('ffmpeg.exe' if windows else 'ffmpeg')
    result = subprocess.run(
        ['bash', str(RECIPE), str(source), str(output), str(tmp_path / 'native-compile')],
        env={**os.environ, 'MSYSTEM': 'UCRT64' if windows else ''},
        capture_output=True, text=True, timeout=35,
    )
    return result, source, output


def test_windows_ffmpeg_exe_target_builds_even_without_plain_ffmpeg_target(tmp_path):
    result, source, output = _fixture(tmp_path, windows=True)
    assert result.returncode == 0, result.stderr + result.stdout
    assert output.read_bytes() == b'native-ffmpeg'
    assert not (source / 'ffmpeg').exists()
    assert (source / 'ffmpeg.exe').is_file()
    assert (Path(str(output) + '.config.log')).is_file()
    assert (Path(str(output) + '.build-recipe.txt')).is_file()


def test_windows_fails_closed_if_output_executable_is_missing(tmp_path):
    result, source, output = _fixture(tmp_path, windows=True, valid_binary=False)
    assert result.returncode != 0
    assert 'expected executable ffmpeg.exe missing' in result.stderr
    assert not output.exists()


def test_linux_out_of_tree_compilation_remains_supported(tmp_path):
    result, source, output = _fixture(tmp_path, windows=False)
    assert result.returncode == 0, result.stderr + result.stdout
    assert output.read_bytes() == b'native-ffmpeg'
    assert not (source / 'ffmpeg').exists()  # out-of-tree on POSIX


def test_script_uses_upstream_all_target_and_platform_output_guard():
    text = RECIPE.read_text(encoding='utf-8')
    assert re.search(r'(?m)^"\$make_command" -j "\$\{TLO_FFMPEG_MAKE_JOBS:-2\}" all$', text)
    assert 'binary=ffmpeg.exe' in text
    assert 'binary=ffmpeg' in text
    assert 'EXESUF=.exe' in text
    assert '[[ -f "$binary" ]]' in text
    assert 'ffbuild/config.log' in text
    assert '--enable-ffmpeg' in text
    assert '--disable-everything' in text
