from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_ffmpeg as FF
import tlo_tag_lib as TL

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_delete_dupes():
    name = "tlo_delete_dupes_build534"
    spec = importlib.util.spec_from_file_location(name, ROOT / "tlo-deleteDupes.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_build534_shared_resolver_ignores_imageio_ffmpeg_environment_override(monkeypatch, tmp_path):
    monkeypatch.setenv("IMAGEIO_FFMPEG_EXE", os.devnull)
    fake_module = tmp_path / "tlo_ffmpeg.py"
    fake_module.write_text("# resolver root", encoding="utf-8")
    bundled = tmp_path / "tlo_ffmpeg_bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    bundled.parent.mkdir()
    bundled.write_bytes(b"ffmpeg")
    if os.name != "nt":
        bundled.chmod(0o755)
    monkeypatch.setattr(FF, "__file__", str(fake_module))
    resolved = FF.bundled_ffmpeg_executable()
    assert Path(resolved) == bundled
    assert Path(resolved) != Path(os.devnull)


def test_build534_shared_resolver_is_the_only_application_resolver():
    delete_dupes = _load_delete_dupes()
    assert TL._bundled_ffmpeg_executable is FF.bundled_ffmpeg_executable
    assert delete_dupes._bundled_ffmpeg_executable is FF.bundled_ffmpeg_executable
    assert "imageio_ffmpeg.get_ffmpeg_exe(" not in (ROOT / "tlo_tag_lib.py").read_text(encoding="utf-8")
    assert "imageio_ffmpeg.get_ffmpeg_exe(" not in (ROOT / "tlo-deleteDupes.py").read_text(encoding="utf-8")


def test_build534_frozen_resolver_rejects_binary_outside_application(monkeypatch, tmp_path):
    monkeypatch.setattr(FF.sys, "frozen", True, raising=False)
    monkeypatch.setattr(FF.sys, "_MEIPASS", str(tmp_path / "bundle"), raising=False)
    monkeypatch.setattr(FF.sys, "executable", str(tmp_path / "app" / "tlo-gi"))
    assert FF.bundled_ffmpeg_executable() == ""


def test_build534_shn_conversion_forces_shn_demuxer_and_file_protocol(tmp_path, monkeypatch):
    source = tmp_path / "track.shn"
    source.write_bytes(b"shorten")
    commands = []
    monkeypatch.setattr(TL, "_bundled_ffmpeg_executable", lambda: "/app/ffmpeg")

    def fake_run(command, **_kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"converted-flac")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(TL.subprocess, "run", fake_run)
    target = TL.convert_shn_to_flac(str(source))

    command = commands[0]
    input_index = command.index("-i")
    assert command[input_index + 1] == str(source.resolve())
    assert command[input_index - 4 : input_index] == ["-f", "shn", "-protocol_whitelist", "file"]
    assert Path(target).read_bytes() == b"converted-flac"
    assert not source.exists()


def test_build534_flac_validation_forces_flac_demuxer_and_file_protocol(tmp_path):
    delete_dupes = _load_delete_dupes()
    source = tmp_path / "track.flac"
    source.write_bytes(b"not-real-flac-but-validator-is-stubbed")
    commands = []

    def fake_run(command, **_kwargs):
        commands.append(command)
        return SimpleNamespace(returncode=0, stderr="")

    assert delete_dupes.flac_file_is_healthy(
        str(source), ffmpeg_executable="/app/ffmpeg", run_func=fake_run
    ) is True
    command = commands[0]
    input_index = command.index("-i")
    assert command[input_index + 1] == os.path.normpath(str(source))
    assert command[input_index - 4 : input_index] == ["-f", "flac", "-protocol_whitelist", "file"]
    assert command[command.index("-map") + 1] == "0:a:0"


def test_build534_packaging_smoke_tests_cannot_be_satisfied_by_imageio_override():
    linux = (ROOT / "createLinuxDist.sh").read_text(encoding="utf-8")
    mac = (ROOT / "createMacOSDist.sh").read_text(encoding="utf-8")
    windows = (ROOT / "createWindowsDist.ps1").read_text(encoding="utf-8")

    assert "IMAGEIO_FFMPEG_EXE=/bin/true TLO_PACKAGING_SMOKE_TEST=1" in linux
    assert "IMAGEIO_FFMPEG_EXE=/usr/bin/true TLO_PACKAGING_SMOKE_TEST=1" in mac
    assert "$env:IMAGEIO_FFMPEG_EXE = 'C:\\definitely-not-tlo\\ffmpeg.exe'" in windows
    assert "$HadImageioFfmpegExe = Test-Path Env:IMAGEIO_FFMPEG_EXE" in windows
