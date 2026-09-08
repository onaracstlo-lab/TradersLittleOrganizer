"""Build 442 corruption-policy GUI/CLI and decision regressions."""

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

import inventory_parser_lib as IPL
import tlo_corruption as C
import tlo_options as O

pytestmark = pytest.mark.behavior

__version__ = "v446"
ROOT = Path(__file__).resolve().parents[2]


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


def _record(path):
    return SimpleNamespace(
        main_dir_path=str(path),
        music_dirs=[str(path)],
        music_file_count=0,
        setlist_files=[],
        setlist_file="",
    )


def test_build442_options_replace_acceptable_corruption_cli():
    fields = {option.config_field for option in O.OPTIONS}
    assert "acceptable_corruption_percent" not in fields
    assert O.OPTIONS_BY_FIELD["corrupt_files"].flag == "--corrupt-files"
    assert O.OPTIONS_BY_FIELD["corrupt_folders"].flag == "--corrupt-folders"
    assert O.OPTIONS_BY_FIELD["corrupt_folder_threshold"].flag == "--corrupt-folder-threshold"
    assert O.OPTIONS_BY_FIELD["corrupt_files"].default == "delete"
    assert O.OPTIONS_BY_FIELD["corrupt_folders"].default == "all"


def test_build442_cli_threshold_requires_matching_folder_mode():
    values = {"corrupt_files": "keep", "corrupt_folders": "threshold"}
    with pytest.raises(ValueError, match="requires --corrupt-folder-threshold"):
        O.validate_corruption_policy(values, require_explicit_threshold=True)

    values = {"corrupt_files": "delete", "corrupt_folders": "never", "corrupt_folder_threshold": 75}
    with pytest.raises(ValueError, match="only valid with --corrupt-folders threshold"):
        O.validate_corruption_policy(values, require_explicit_threshold=True)

    values = {"corrupt_files": "keep", "corrupt_folders": "threshold", "corrupt_folder_threshold": 75}
    O.validate_corruption_policy(values, require_explicit_threshold=True)
    assert values == {"corrupt_files": "keep", "corrupt_folders": "threshold", "corrupt_folder_threshold": 75}


def test_build442_main_cli_accepts_new_policy_and_rejects_old_option(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "argv", [
        "tlo-gi.py", "--TLOHome", str(tmp_path),
        "--corrupt-files", "keep",
        "--corrupt-folders", "threshold",
        "--corrupt-folder-threshold", "75",
    ])
    values = IPL.parse_command_line()
    assert values["corrupt_files"] == "keep"
    assert values["corrupt_folders"] == "threshold"
    assert values["corrupt_folder_threshold"] == 75

    monkeypatch.setattr(sys, "argv", ["tlo-gi.py", "--TLOHome", str(tmp_path), "--acceptable-corruption-percent", "75"])
    with pytest.raises(SystemExit):
        IPL.parse_command_line()


def test_build442_action_matrix_keeps_file_and_folder_decisions_independent():
    assert C.corruption_action(10, 3, "keep", "never", 75) == "report_only"
    assert C.corruption_action(10, 3, "delete", "never", 75) == "trash_corrupt_files"
    assert C.corruption_action(10, 10, "keep", "all", 75) == "trash_folder_all_corrupt"
    assert C.corruption_action(10, 9, "keep", "all", 75) == "report_only"
    assert C.corruption_action(10, 8, "keep", "threshold", 80) == "trash_folder_threshold"
    assert C.corruption_action(10, 7, "delete", "threshold", 80) == "trash_corrupt_files"


def test_build442_threshold_folder_candidates_use_original_direct_folder_percentages(tmp_path):
    disc1 = tmp_path / "Disc 1"
    disc2 = tmp_path / "Disc 2"
    disc1.mkdir(); disc2.mkdir()
    d1 = [str(disc1 / f"{i:02d}.flac") for i in range(1, 5)]
    d2 = [str(disc2 / f"{i:02d}.flac") for i in range(1, 5)]
    audio = d1 + d2
    bad = d1[:3] + d2[:2]
    group = {"main_dir_path": str(tmp_path), "music_dirs": [str(disc1), str(disc2)]}
    assert C.qualifying_corrupt_music_dirs(group, audio, bad, "threshold", 75) == [str(disc1)]


def test_build442_keep_and_report_never_moves_any_corrupt_content(monkeypatch, tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    bad = str(show / "01.flac")
    good = str(show / "02.flac")
    assessment = C.CorruptionAssessment(
        audio_files=[bad, good],
        corrupt_files=[bad],
        action="report_only",
        corruption_percent=50.0,
        corrupt_files_policy="keep",
        corrupt_folders_policy="never",
        folder_threshold=100,
        folder_candidates=[],
    )
    monkeypatch.setattr(C, "move_to_trash", lambda path: pytest.fail(f"must retain {path}"))
    monkeypatch.setattr(C, "group_audio_files", lambda group: [bad, good])
    group = {"main_dir_path": str(show), "music_dirs": [str(show)], "music_files": [bad, good], "music_sample_files": [], "setlist_files": [], "txt_files": [], "setlist_file": ""}
    record = _record(show)
    out = C.apply_corruption_assessment(_config(), group, record, assessment)
    assert not out.trashed_dirs and not out.trashed_files


def test_build442_folder_failure_does_not_override_keep_file_policy(monkeypatch, tmp_path):
    show = tmp_path / "Show"
    show.mkdir()
    bad = str(show / "01.flac")
    assessment = C.CorruptionAssessment(
        audio_files=[bad],
        corrupt_files=[bad],
        action="trash_folder_all_corrupt",
        corruption_percent=100.0,
        corrupt_files_policy="keep",
        corrupt_folders_policy="all",
        folder_threshold=100,
        folder_candidates=[],
    )
    calls = []
    def fail_folder(path):
        calls.append(path)
        raise OSError("trash unavailable")
    monkeypatch.setattr(C, "move_to_trash", fail_folder)
    monkeypatch.setattr(C, "group_audio_files", lambda group: [bad])
    group = {"main_dir_path": str(show), "music_dirs": [str(show)], "music_files": [bad], "music_sample_files": [], "setlist_files": [], "txt_files": [], "setlist_file": ""}
    out = C.apply_corruption_assessment(_config(), group, _record(show), assessment)
    assert out.whole_folder_trash_failed
    assert calls == [str(show)]
    assert out.trashed_files == []


def test_build442_gui_groups_corruption_controls_and_disables_threshold_when_unused():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert 'ttk.LabelFrame(frm, text="Corruption Handling"' in source
    assert 'text="Corrupt files"' in source
    assert 'text="Folder removal"' in source
    assert 'text="Folder corruption\\nthreshold"' in source
    assert '"Keep and report"' in source
    assert '"Delete corrupt files"' in source
    assert '"100% corrupt only"' in source
    assert '"At threshold"' in source
    assert 'entry.configure(state=("normal" if policy == "threshold" else "disabled"))' in source
    assert "acceptable corruption %" not in source
