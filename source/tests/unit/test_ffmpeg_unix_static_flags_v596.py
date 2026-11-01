"""Build 596: strict Bash and native Unix FFmpeg configure flag regression."""
import os
from pathlib import Path
import subprocess
import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
RECIPE = ROOT / "build_audio_ffmpeg.sh"


def test_ffmpeg_recipe_uses_safe_optional_flags_under_nounset():
    code = RECIPE.read_text(encoding="utf-8")
    assert 'extra_link_options[@]' not in code
    assert 'set -- --extra-ldexeflags=-static' in code
    assert 'set --\nfi\n"$configure_command"' in code
    assert '"$@" \\' in code


def test_nonwindows_configure_and_make_run_under_strict_bash(tmp_path):
    source = tmp_path / "ffmpeg-src"
    build = tmp_path / "work"
    source.mkdir()
    (source / "Makefile").write_text("# upstream source fixture\n")
    (source / "configure").write_text("""#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\\n' "$@" > configure-args.txt
mkdir -p ffbuild
printf 'config=ok\\n' > ffbuild/config.mak
printf 'log=ok\\n' > ffbuild/config.log
cat > Makefile <<'MAKEFILE'
all:
\tprintf 'fake ffmpeg executable\\n' > ffmpeg
MAKEFILE
""")
    (source / "configure").chmod(0o755)
    out = tmp_path / "out" / "ffmpeg"
    env = {**os.environ, "MSYSTEM": "", "TLO_FFMPEG_MAKE_JOBS": "1"}
    result = subprocess.run(["bash", str(RECIPE), str(source), str(out), str(build)], env=env, text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert out.exists()
    flags = (build / "configure-args.txt").read_text()
    assert "--enable-demuxer=shorten,flac" in flags
    assert "--extra-ldexeflags=-static" not in flags
    assert out.with_name("ffmpeg.config.log").exists()
    assert out.with_name("ffmpeg.build-recipe.txt").exists()


def test_windows_static_and_import_gate_remains():
    code = RECIPE.read_text()
    assert "--extra-ldexeflags=-static" in code
    assert "/ucrt64/bin/objdump.exe" in code
    assert "Non-system FFmpeg DLL dependency rejected" in code
