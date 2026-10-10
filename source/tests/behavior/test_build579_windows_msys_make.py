"""Build 579 Windows FFmpeg Make compatibility and archive hygiene."""
from pathlib import Path
import os
import subprocess

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_windows_make_uses_msys_posix_binary_and_preserves_source_layout():
    text = (ROOT / 'build_audio_ffmpeg.sh').read_text(encoding='utf-8')
    assert '"${MSYSTEM:-}" == UCRT64' in text
    assert 'command -v make' not in text
    assert 'make_command=/usr/bin/make.exe' in text
    assert 'make_version' in text
    assert "MSYS2 POSIX Make identity check failed" in text
    assert 'make_real=' in text
    assert '"$make_command" -j' in text
    assert '\nmake -j ' not in text
    assert '[ [ -f ' not in text
    assert '[[ -f "$source_dir/Makefile" ]]' in text
    assert '[[ -f Makefile ]]' in text
    assert 'ffmpeg-9.0.2' not in text  # source folder is a parameter, not a hardcoded mount


def test_makefile_guard_stops_missing_source_before_compiler(tmp_path):
    source = tmp_path / 'source'
    source.mkdir()
    (source / 'configure').write_text('#!/bin/sh\nexit 0\n', encoding='utf-8')
    cmd = ['bash', str(ROOT / 'build_audio_ffmpeg.sh'), str(source),
           str(tmp_path / 'output'), str(tmp_path / 'build')]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    assert result.returncode != 0
    assert 'source Makefile not found' in result.stderr


def test_recipe_runs_out_of_tree_with_actual_posix_make(tmp_path):
    source = tmp_path / 'source with spaces'
    source.mkdir()
    (source / 'Makefile').write_text('# mock FFmpeg source root\n', encoding='utf-8')
    cfg = source / 'configure'
    cfg.write_text("#!/bin/sh\nset -eu\nmkdir -p ffbuild\n"
                   "printf 'test' > ffbuild/config.log\n"
                   "printf EXESUF= > ffbuild/config.mak\n"
                   "cat > Makefile <<'EOF'\n"
                   "all: ffmpeg\nffmpeg:\n\tprintf 'synthetic-bin' > ffmpeg\n"
                   "EOF\n", encoding='utf-8')
    cfg.chmod(0o755)
    result = tmp_path / 'output with spaces' / 'ffmpeg'
    subprocess.run(['bash', str(ROOT / 'build_audio_ffmpeg.sh'),
                    str(source), str(result), str(tmp_path / 'compile with spaces')],
                   check=True, timeout=30, env={**os.environ, 'MSYSTEM': ''})
    assert result.is_file()
    assert (Path(str(result) + '.config.log')).is_file()
    assert (Path(str(result) + '.build-recipe.txt')).is_file()
