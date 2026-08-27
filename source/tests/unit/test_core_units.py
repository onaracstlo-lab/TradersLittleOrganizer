"""Fast isolated tests for options, metadata formatting, and settings logging."""

__version__ = "v407"

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.unit


def test_inventory_parser_executes_registry_defaults_and_overrides():
    import inventory_parser_lib as parser_lib

    parser = parser_lib.build_inventory_parser()
    parsed = parser.parse_args([
        "--compliant",
        "--as-is-artist-name",
        "--no-artist-in-album",
        "--performance-mode", "fast",
        "--max-workers", "6",
    ])

    assert parsed.compliant is True
    assert parsed.as_is_artist_name is True
    assert parsed.artist_in_album is False
    assert parsed.performance_mode == "fast"
    assert parsed.max_workers == 6


def test_artist_in_album_changes_album_value_by_execution():
    import tlo_tag_lib as tag_lib

    record = SimpleNamespace(
        artist="Miles Davis",
        date="1970-04-09",
        venue="Fillmore West",
        location="San Francisco, CA",
        parentheticals="(late show)",
        album_name="",
        show_name="Miles Davis 1970-04-09 Fillmore West San Francisco, CA (late show)",
    )

    with_artist = tag_lib._album_for_record(SimpleNamespace(artist_in_album=True), record)
    without_artist = tag_lib._album_for_record(SimpleNamespace(artist_in_album=False), record)

    assert with_artist == "Miles Davis 1970-04-09 Fillmore West San Francisco, CA (late show)"
    assert without_artist == "1970-04-09 Fillmore West San Francisco, CA (late show)"


def test_parenthetical_normalization_preserves_trailing_qualifiers():
    import tlo_phase23_v2 as phase

    assert phase._merge_parenthetical_items(
        "(set 2)", "(SBD) (set 2)", "(24-bit)"
    ) == "(set 2) (SBD) (24-bit)"


def test_run_settings_log_exactly_preserves_review_lines(tmp_path):
    from tlo_run_settings import append_run_settings

    review_lines = [
        "Operation: Full Inventory",
        "Main-window checkbox values:",
        "  Compliant: Yes",
        "  Artist in Album Tag: No",
        "  Dry run: Yes",
        "Original files may be changed: No",
    ]
    started = datetime(2026, 8, 3, 20, 15, 30, tzinfo=timezone.utc)

    path = append_run_settings(
        str(tmp_path),
        "Full Inventory Dry Run",
        review_lines,
        started_at=started,
    )

    text = Path(path).read_text(encoding="utf-8")
    assert text == (
        "Action: Full Inventory Dry Run | Date: 2026-08-03 | Time: 8:15:30 PM UTC\n"
        + "\n".join(review_lines)
        + "\n\n"
    )
