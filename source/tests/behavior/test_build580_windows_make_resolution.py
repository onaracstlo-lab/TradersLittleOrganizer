"""Build 580: MSYS2 make command-name resolution without suffix assumptions."""
from pathlib import Path
import os
import subprocess

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "build_audio_ffmpeg.sh"


def _mock_ffmpeg(tmp_path):
    source = tmp_path / "source with spaces"
    source.mkdir()
    (source / "Makefile").write_text("# verified upstream source placeholder\n")
    config = source / "configure"
    config.write_text(
        "#!/bin/sh\nset -eu\nmkdir -p ffbuild\n"
        "printf 'ok' > ffbuild/config.log\n"
        "printf EXESUF= > ffbuild/config.mak\n"
        "cat > Makefile <<'EOF'\n"
        "all: ffmpeg\nffmpeg:\n\tprintf 'test-ffmpeg' > ffmpeg\n"
        "EOF\n"
    )
    config.chmod(0o755)
    return source


def test_non_windows_make_compiles_out_of_tree(tmp_path):
    source = _mock_ffmpeg(tmp_path)
    target = tmp_path / "out space" / "ffmpeg"
    env = {**os.environ, "MSYSTEM": ""}
    completed = subprocess.run(
        ["bash", str(SCRIPT), str(source), str(target), str(tmp_path / "build space")],
        env=env, capture_output=True, text=True, timeout=35
    )
    assert completed.returncode == 0, completed.stderr + completed.stdout
    assert target.read_bytes() == b'test-ffmpeg'
    assert (Path(str(target) + '.config.log')).is_file()


def test_windows_make_selection_does_not_depend_on_host_path():
    text = SCRIPT.read_text(encoding='utf8')
    assert 'make_command=/usr/bin/make.exe' in text
    assert 'make_command=/usr/bin/make' in text
    assert 'readlink -f -- "$make_command"' in text
    assert '/usr/bin/make|/usr/bin/make.exe' in text
    assert 'PATH=/usr/bin:' not in text
    assert 'command -v make' not in text
    assert 'MSYS2 POSIX Make path escaped trusted' in text


def test_native_windows_build_uses_source_local_configure():
    text = SCRIPT.read_text(encoding='utf8')
    assert 'cd -- "$source_dir"' in text
    assert 'configure_command=./configure' in text
    assert 'cd -- "$build_dir"' in text
    assert 'configure_command="${source_dir}/configure"' in text
    assert '$configure_command' in text


def test_source_recipe_never_requires_exact_exe_suffix():
    text = SCRIPT.read_text(encoding='utf8')
    assert '[[ -x /usr/bin/make.exe ]]' in text
    assert 'command -v make' not in text
    assert '/usr/bin/make|/usr/bin/make.exe' in text
    assert 'MSYS2 POSIX Make identity check failed' in text
    assert '"$make_command" -j' in text
