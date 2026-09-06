"""Build 400/431 corruption classification and fail-closed mutation safeguards."""
__version__ = "v440"

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

import tlo_corruption as C


def _touch_audio(tmp_path, name="x.flac", payload=b"fLaC" + b"\0" * 128):
    path = tmp_path / name
    path.write_bytes(payload)
    return path


def test_build400_permission_error_is_unverifiable_not_corrupt(monkeypatch, tmp_path):
    path = _touch_audio(tmp_path)
    monkeypatch.setattr(C, "FLAC", lambda p: (_ for _ in ()).throw(PermissionError("locked")))
    bad, unverifiable = C.classify_audio_paths([str(path)])
    assert bad == []
    assert unverifiable and unverifiable[0][0] == str(path)
    assert "PermissionError" in unverifiable[0][1]


def test_build400_oserror_is_unverifiable_not_corrupt(monkeypatch, tmp_path):
    path = _touch_audio(tmp_path)
    monkeypatch.setattr(C, "FLAC", lambda p: (_ for _ in ()).throw(OSError("device unavailable")))
    bad, unverifiable = C.classify_audio_paths([str(path)])
    assert bad == []
    assert unverifiable and "OSError" in unverifiable[0][1]


def test_build431_real_missing_flac_is_unverifiable_without_mocking_mutagen(tmp_path):
    path = tmp_path / "vanished.flac"
    bad, unverifiable = C.classify_audio_paths([str(path)])
    assert bad == []
    assert unverifiable and unverifiable[0][0] == str(path)
    assert "FileNotFoundError" in unverifiable[0][1]


def test_build431_mutagen_wrapped_oserror_is_unverifiable(monkeypatch, tmp_path):
    from mutagen import MutagenError
    path = _touch_audio(tmp_path)

    def wrapped(_path):
        try:
            raise PermissionError("share reauthentication required")
        except PermissionError as cause:
            raise MutagenError("validator read failed") from cause

    monkeypatch.setattr(C, "FLAC", wrapped)
    bad, unverifiable = C.classify_audio_paths([str(path)])
    assert bad == []
    assert unverifiable and "PermissionError" in unverifiable[0][1]


def test_build400_parse_failure_is_proven_corrupt(monkeypatch, tmp_path):
    from mutagen import MutagenError
    path = _touch_audio(tmp_path)
    monkeypatch.setattr(C, "FLAC", lambda p: (_ for _ in ()).throw(MutagenError("bad stream")))
    bad, unverifiable = C.classify_audio_paths([str(path)])
    assert bad == [str(path)]
    assert unverifiable == []


def test_build400_unknown_validator_exception_is_unverifiable(monkeypatch, tmp_path):
    path = _touch_audio(tmp_path)
    monkeypatch.setattr(C, "FLAC", lambda p: (_ for _ in ()).throw(RuntimeError("validator bug")))
    bad, unverifiable = C.classify_audio_paths([str(path)])
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
