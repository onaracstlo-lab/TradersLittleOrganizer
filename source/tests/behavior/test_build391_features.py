import pytest

pytestmark = pytest.mark.behavior
import tlo_corruption as corruption
import tlo_options

def test_build391_legacy_strict_threshold_helper_remains_stable():
    assert corruption.exceeds_threshold(20, 2, 10) is False
    assert corruption.exceeds_threshold(20, 3, 10) is True


def test_current_folder_threshold_uses_at_or_above_semantics():
    assert corruption.meets_corruption_threshold(20, 2, 10) is True
    assert corruption.meets_corruption_threshold(20, 1, 10) is False


def test_current_corruption_input_is_0_to_100():
    option = tlo_options.OPTIONS_BY_FIELD["corrupt_folder_threshold"]
    assert option.default == 100
    assert tlo_options.parse_percent_0_100("0") == 0
    assert tlo_options.parse_percent_0_100("100") == 100
    with pytest.raises(Exception):
        tlo_options.parse_percent_0_100("101")


def test_current_all_corrupt_folder_policy_removes_all_corrupt_show():
    assert corruption.corruption_action(10, 10, "keep", "all", 100) == "trash_folder_all_corrupt"


def test_current_partial_corruption_respects_individual_file_policy():
    assert corruption.corruption_action(10, 2, "delete", "all", 100) == "trash_corrupt_files"
    assert corruption.corruption_action(10, 2, "keep", "all", 100) == "report_only"


def test_current_threshold_policy_takes_precedence_at_equality():
    assert corruption.corruption_action(10, 2, "keep", "threshold", 20) == "trash_folder_threshold"


def test_current_no_corruption_requires_no_trash_action():
    assert corruption.corruption_action(10, 0, "delete", "threshold", 0) == "none"


def test_build398_all_corrupt_music_directory_is_detected_with_healthy_sibling(tmp_path):
    bad_dir = tmp_path / "Disc 1"
    good_dir = tmp_path / "Disc 2"
    bad_dir.mkdir(); good_dir.mkdir()
    bad1 = str(bad_dir / "01.flac")
    bad2 = str(bad_dir / "02.flac")
    good = str(good_dir / "01.flac")
    group = {"main_dir_path": str(tmp_path), "music_dirs": [str(bad_dir), str(good_dir)]}
    audio_files = [bad1, bad2, good]
    bad_files = [bad1, bad2]
    assert corruption.fully_corrupt_music_dirs(group, audio_files, bad_files) == [str(bad_dir)]


def test_build398_partially_corrupt_music_directory_is_not_folder_trash_candidate(tmp_path):
    music_dir = tmp_path / "Show"
    music_dir.mkdir()
    bad = str(music_dir / "01.flac")
    good = str(music_dir / "02.flac")
    group = {"main_dir_path": str(music_dir), "music_dirs": [str(music_dir)]}
    assert corruption.fully_corrupt_music_dirs(group, [bad, good], [bad]) == []
