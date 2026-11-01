import pytest
pytestmark = pytest.mark.unit
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_windows_ffmpeg_static_executable_and_import_gate():
    recipe = (ROOT / "build_audio_ffmpeg.sh").read_text()
    for requirement in ("--extra-ldexeflags=-static", "/ucrt64/bin/objdump.exe", "DLL Name:", "Non-system FFmpeg DLL dependency rejected", "cp -- \"$binary\" \"$output\""):
        assert requirement in recipe
    assert recipe.index("Non-system FFmpeg DLL dependency rejected") < recipe.index('cp -- "$binary" "$output"')


def test_system_allowlist_excludes_pthread():
    recipe = (ROOT / "build_audio_ffmpeg.sh").read_text()
    assert 'kernel32.dll|user32.dll' in recipe
    assert 'libwinpthread-1.dll|' not in recipe
