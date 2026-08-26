"""Build 400 corruption classification and fail-closed mutation safeguards."""
__version__ = "v406"

import builtins
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit

import tlo_corruption as C


def test_build400_permission_error_is_unverifiable_not_corrupt(monkeypatch):
    monkeypatch.setattr(C, "FLAC", lambda path: (_ for _ in ()).throw(PermissionError("locked")))
    bad, unverifiable = C.classify_audio_paths(["x.flac"])
    assert bad == []
    assert unverifiable and unverifiable[0][0] == "x.flac"
    assert "PermissionError" in unverifiable[0][1]


def test_build400_oserror_is_unverifiable_not_corrupt(monkeypatch):
    monkeypatch.setattr(C, "FLAC", lambda path: (_ for _ in ()).throw(OSError("device unavailable")))
    bad, unverifiable = C.classify_audio_paths(["x.flac"])
    assert bad == []
    assert unverifiable and "OSError" in unverifiable[0][1]


def test_build400_parse_failure_is_proven_corrupt(monkeypatch):
    from mutagen import MutagenError
    monkeypatch.setattr(C, "FLAC", lambda path: (_ for _ in ()).throw(MutagenError("bad stream")))
    bad, unverifiable = C.classify_audio_paths(["x.flac"])
    assert bad == ["x.flac"]
    assert unverifiable == []


def test_build400_unknown_validator_exception_is_unverifiable(monkeypatch):
    monkeypatch.setattr(C, "FLAC", lambda path: (_ for _ in ()).throw(RuntimeError("validator bug")))
    bad, unverifiable = C.classify_audio_paths(["x.flac"])
    assert bad == []
    assert unverifiable and "RuntimeError" in unverifiable[0][1]


def test_build400_group_listing_error_is_unverifiable(monkeypatch, tmp_path):
    group = {"main_dir_path": str(tmp_path), "music_dirs": [str(tmp_path)]}
    monkeypatch.setattr(C.os, "listdir", lambda path: (_ for _ in ()).throw(OSError("share dropped")))
    paths, errors = C.group_audio_snapshot(group)
    assert paths == []
    assert errors and errors[0][0] == str(tmp_path)


def test_build400_all_proven_corrupt_still_overrides_100_percent_setting():
    assert C.corruption_action(3, 3, 100) == "trash_folder_all_corrupt"


def test_build400_windows_trash_has_no_legacy_shfileoperation_fallback():
    import inspect
    source = inspect.getsource(C._trash_windows)
    assert "SHFileOperationW" not in source
    assert "FOFX_RECYCLEONDELETE" in source
    assert "FOFX_EARLYFAILURE" in source
    assert "shutil.rmtree" not in source
    assert "os.remove" not in source


def test_build400_windows_trash_checks_source_disappearance():
    import inspect
    source = inspect.getsource(C._trash_windows)
    assert "source still exists" in source
