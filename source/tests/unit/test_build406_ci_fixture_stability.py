"""Build 406 regression-fixture stability checks."""

__version__ = "v440"

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit
ROOT = Path(__file__).resolve().parents[2]
LEGACY = ROOT / "tests" / "_legacy_suite.py"


def test_non_corruption_legacy_tests_explicitly_neutralize_corruption_classification():
    source = LEGACY.read_text(encoding="utf-8")
    helper = "_disable_corruption_for_non_corruption_test(monkeypatch)"
    # One helper definition plus exactly five targeted callers.
    assert source.count(helper) == 6
    for test_name in (
        "test_v265_inventory_leaves_unidentified_show_in_place_before_copy_delete_or_tag",
        "test_v266_inventory_copy_delete_tags_transferred_compliant_folder",
        "test_v286_process_groups_returns_destination_record_for_copy_delete",
        "test_v303_rename_only_inventory_renames_in_place_without_tagging",
        "test_v356_full_inventory_tag_in_place_passes_artist_in_album_to_album_builder",
    ):
        start = source.index(f"def {test_name}(")
        body = source[start : start + 350]
        assert helper in body


def test_fixture_neutralization_is_classifier_only_not_trash_suppression():
    source = LEGACY.read_text(encoding="utf-8")
    start = source.index("def _disable_corruption_for_non_corruption_test")
    body = source[start : start + 900]
    assert 'monkeypatch.setattr(C, "classify_audio_paths", lambda paths: ([], []))' in body
    assert "trash_path" not in body
