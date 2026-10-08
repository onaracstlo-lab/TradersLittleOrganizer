"""Build 552: bounded parser work and shutdown-safe Tk worker completion."""

from __future__ import annotations
from tests._release_artifacts import release_history

import time
from pathlib import Path

import pytest

import tlo_gui_shortcuts as GUI
import tlo_phase23_v2 as PHASE
import tlo_research_lib as RESEARCH

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build552_long_date_analysis_is_bounded_and_preserves_absolute_offsets():
    source = "x" * 5000 + " Artist 1977-05-08 Barton Hall"
    floor = len(source) - PHASE.DATE_ANALYSIS_MAX_CHARS

    matches = PHASE._find_date_matches(source)
    target = next(item for item in matches if item["normalized"] == "1977-05-08")

    assert PHASE.DATE_ANALYSIS_MAX_CHARS == 1024
    assert target["start"] == source.index("1977-05-08")
    assert target["end"] == target["start"] + len("1977-05-08")
    assert all(int(item["start"]) >= floor for item in matches)


def test_build552_adversarial_numeric_date_text_no_longer_scales_with_full_input():
    # Build 540 Part 2 measured this exact 6 KB shape at roughly 1.7 seconds;
    # Build 549 closure still measured about 1.0 second. The bounded 1 KB
    # analysis window should keep it well below that while retaining matches in
    # the trailing window.
    started = time.perf_counter()
    matches = PHASE._find_date_matches("12-" * 2000)
    elapsed = time.perf_counter() - started

    assert elapsed < 0.75
    assert matches
    assert max(int(item["end"]) for item in matches) <= 6000
    assert min(int(item["start"]) for item in matches) >= 6000 - PHASE.DATE_ANALYSIS_MAX_CHARS


def test_build552_research_query_length_is_explicitly_bounded():
    assert RESEARCH.MAX_RESEARCH_QUERY_CHARS == 2048
    too_long = "May " * 700
    started = time.perf_counter()
    with pytest.raises(ValueError, match=r"maximum is 2048 characters"):
        RESEARCH.parse_research_query(too_long)
    assert time.perf_counter() - started < 0.25


def test_build552_research_date_suffix_scan_is_bounded_and_keeps_longest_date(monkeypatch):
    seen_lengths: list[int] = []
    real = RESEARCH._exact_date_normalizations

    def recording(value: str):
        seen_lengths.append(len(value))
        return real(value)

    monkeypatch.setattr(RESEARCH, "_exact_date_normalizations", recording)
    artist, dates = RESEARCH._split_artist_trailing_date(
        "Very Long Artist Name " + ("descriptor " * 80) + "April 14, 2001"
    )

    assert artist.endswith("descriptor")
    assert dates == ("2001-04-14",)
    assert seen_lengths
    assert max(seen_lengths) <= RESEARCH.MAX_RESEARCH_DATE_SUFFIX_CHARS == 256


@pytest.mark.parametrize("exc", [RuntimeError("main thread is not in main loop"), GUI.tk.TclError("application has been destroyed")])
def test_build552_schedule_tk_after_treats_shutdown_runtimeerror_as_closed_window(exc):
    class ClosedWidget:
        def after(self, _delay, _callback):
            raise exc

    called = []
    assert GUI.schedule_tk_after(ClosedWidget(), 0, lambda: called.append(True)) is False
    assert called == []


def test_build552_schedule_tk_after_still_schedules_live_widget():
    class LiveWidget:
        def after(self, delay, callback):
            assert delay == 0
            callback()

    called = []
    assert GUI.schedule_tk_after(LiveWidget(), 0, lambda: called.append(True)) is True
    assert called == [True]


def test_build552_worker_completion_paths_use_shutdown_safe_scheduler():
    main_source = (ROOT / "tlo-main.py").read_text(encoding="utf-8")
    search_source = (ROOT / "tlo-search.py").read_text(encoding="utf-8")
    helper_source = (ROOT / "tlo_gui_shortcuts.py").read_text(encoding="utf-8")

    assert main_source.count("schedule_tk_after(") >= 8
    assert search_source.count("schedule_tk_after(") >= 2
    assert "except (tk.TclError, RuntimeError):" in helper_source
    assert "except (tk.TclError, RuntimeError) as exc:" in main_source

    # The completion paths called from daemon workers should no longer use raw
    # Tk after(0, ...) calls. Two raw calls intentionally remain: synchronous
    # GUI-thread marshaling and a capacity dialog guarded by a broad boundary.
    assert main_source.count(".after(0,") == 2
    assert search_source.count(".after(0,") == 0


def test_build552_version_and_documentation_contract():
    from docx import Document
    from tests import _release_artifacts as A

    req_doc = Document(ROOT / A.REQUIREMENTS_FILENAME)
    req = "\n".join(p.text for p in req_doc.paragraphs)

    assert "Build 552 - " in release_history()
    assert "Build 552: parser/GUI robustness" in req
    assert "trailing 1,024 characters" in req
    assert "2,048 characters" in req
    assert "daemon-thread tracebacks" in req
