"""Build 431 destructive-path safety regressions."""
__version__ = "v433"

import argparse
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

import logging_lib as L
import tlo_corruption as C
from tlo_options import parse_percent_0_100

pytestmark = pytest.mark.unit


def _load_delete_dupes():
    path = Path(__file__).resolve().parents[2] / "tlo-deleteDupes.py"
    spec = importlib.util.spec_from_file_location("tlo_deleteDupes_build431", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_blank_corruption_percent_is_invalid_not_zero():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_percent_0_100("")
    assert parse_percent_0_100("100") == 100
    assert parse_percent_0_100("0") == 0


def test_missing_flac_health_is_unverifiable(tmp_path):
    D = _load_delete_dupes()
    assert D.flac_file_is_healthy(str(tmp_path / "missing.flac")) is None
    assert D.flac_file_is_healthy(str(tmp_path / "not-a-flac.wav")) is False


def test_gio_trash_uses_argument_terminator_timeout_and_postcondition(monkeypatch, tmp_path):
    target = tmp_path / "-dangerous show"
    target.mkdir()
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        target.rmdir()
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(C.sys, "platform", "linux")
    monkeypatch.setattr(C.subprocess, "run", fake_run)
    C.move_to_trash(str(target))
    command, kwargs = calls[0]
    assert command[:3] == ["gio", "trash", "--"]
    assert kwargs["timeout"] == C.TRASH_SUBPROCESS_TIMEOUT_SECONDS


def test_gio_trash_timeout_is_failure_not_delete_fallback(monkeypatch, tmp_path):
    target = tmp_path / "show"
    target.mkdir()
    def fake_run(command, **kwargs):
        raise C.subprocess.TimeoutExpired(command, kwargs.get("timeout"))
    monkeypatch.setattr(C.sys, "platform", "linux")
    monkeypatch.setattr(C.subprocess, "run", fake_run)
    with pytest.raises(OSError, match="timed out"):
        C.move_to_trash(str(target))
    assert target.exists()


def test_all_log_mutators_reject_malformed_tokens_before_path_construction(tmp_path):
    for func, args in [
        (L.delete_logs_for_tokens, (str(tmp_path), ["../BAD"])),
        (L.truncate_logs_for_tokens, (str(tmp_path), ["../BAD"])),
        (L.prune_logs_for_tokens_and_paths, (str(tmp_path), ["../BAD"], ["/boots"])),
    ]:
        with pytest.raises(ValueError, match="Invalid log token"):
            func(*args)
