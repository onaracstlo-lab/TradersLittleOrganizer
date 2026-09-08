"""Build 433 directly testable corruption assessment/mutation regressions."""
__version__ = "v448"

from types import SimpleNamespace

import pytest

import tlo_corruption as C

pytestmark = pytest.mark.unit


class _Logs:
    def __init__(self):
        self.conflict_lines = []
        self.tag_lines = []

    @staticmethod
    def _fmt(value, args):
        return value % args if args else value

    def conflicts(self, value, *args):
        self.conflict_lines.append(self._fmt(value, args))

    def tag(self, value, *args):
        self.tag_lines.append(self._fmt(value, args))


def _config():
    return SimpleNamespace(
        logs=_Logs(),
        current_search_corruption_groups_removed=0,
        current_search_corruption_removed_paths=[],
    )


def _record(path="/shows/show"):
    return SimpleNamespace(
        main_dir_path=path,
        music_dirs=[path],
        music_file_count=1,
        setlist_files=[],
        setlist_file="",
    )


def _group(path="/shows/show"):
    return {
        "main_dir_path": path,
        "music_dirs": [path],
        "music_files": [],
        "music_sample_files": [],
        "setlist_files": [],
        "txt_files": [],
        "setlist_file": "",
        "music_file_count": 1,
    }


def test_assessment_is_separate_and_unverifiable_forces_no_action(monkeypatch):
    monkeypatch.setattr(C, "group_audio_snapshot", lambda group: (["a.flac", "b.flac"], []))
    monkeypatch.setattr(C, "classify_audio_paths", lambda paths: (["a.flac"], [("b.flac", "OSError: offline")]))
    monkeypatch.setattr(C, "fully_corrupt_music_dirs", lambda *args: pytest.fail("must not derive destructive targets when unverifiable"))

    result = C.assess_group_corruption(_group(), "delete", "all", 100)

    assert result.audio_files == ["a.flac", "b.flac"]
    assert result.corrupt_files == ["a.flac"]
    assert result.unverifiable
    assert result.action == "none"


def test_positive_all_corrupt_assessment_authorizes_whole_show_trash(monkeypatch):
    monkeypatch.setattr(C, "group_audio_snapshot", lambda group: (["a.flac", "b.flac"], []))
    monkeypatch.setattr(C, "classify_audio_paths", lambda paths: (list(paths), []))
    monkeypatch.setattr(C, "fully_corrupt_music_dirs", lambda *args: ["/shows/show"])

    result = C.assess_group_corruption(_group(), "delete", "all", 100)

    assert not result.unverifiable
    assert result.action == "trash_folder_all_corrupt"
    assert result.corruption_percent == 100.0


def test_apply_whole_show_trash_returns_structured_outcome(monkeypatch):
    moved = []
    monkeypatch.setattr(C, "move_to_trash", lambda path: moved.append(path))
    assessment = C.CorruptionAssessment(
        audio_files=["a.flac"],
        corrupt_files=["a.flac"],
        action="trash_folder_all_corrupt",
        corruption_percent=100.0,
        corrupt_files_policy="delete",
        corrupt_folders_policy="all",
        folder_threshold=100,
        folder_candidates=["/shows/show"],
    )
    config = _config()
    record = _record()

    outcome = C.apply_corruption_assessment(config, _group(), record, assessment)

    assert outcome.show_removed
    assert moved == ["/shows/show"]
    assert config.current_search_corruption_groups_removed == 1
    assert config.current_search_corruption_removed_paths == ["/shows/show"]
    assert any("REMOVED_CORRUPTION" in line for line in config.logs.conflict_lines)


def test_unverifiable_assessment_never_calls_trash(monkeypatch):
    monkeypatch.setattr(C, "move_to_trash", lambda path: pytest.fail("unverifiable content must not be trashed"))
    assessment = C.CorruptionAssessment(
        audio_files=["a.flac"],
        corrupt_files=[],
        unverifiable_details=[("a.flac", "PermissionError: locked")],
        action="none",
        corrupt_files_policy="delete",
        corrupt_folders_policy="all",
        folder_threshold=100,
    )
    config = _config()

    outcome = C.apply_corruption_assessment(config, _group(), _record(), assessment)

    assert outcome.unverifiable
    assert not outcome.show_removed
    assert any("CORRUPTION_UNVERIFIABLE" in line for line in config.logs.conflict_lines)


def test_handle_group_corruption_fails_closed_on_unexpected_assessment_error(monkeypatch):
    def explode(*args, **kwargs):
        raise RuntimeError("validator infrastructure failed")

    monkeypatch.setattr(C, "assess_group_corruption", explode)
    monkeypatch.setattr(C, "move_to_trash", lambda path: pytest.fail("unexpected failure must not trash"))
    config = _config()

    outcome = C.handle_group_corruption(config, _group(), _record(), "delete", "all", 100)

    assert outcome.unverifiable
    assert outcome.unexpected_error.startswith("RuntimeError:")
    assert outcome.assessment.action == "none"
    assert any("CORRUPTION_CHECK_FAILED_UNVERIFIABLE" in line for line in config.logs.conflict_lines)
