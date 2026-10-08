"""Suite-level CI display support for Tkinter behavior coverage."""


import atexit
import importlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import pytest


_XVFB_PROCESS = None
_XVFB_DISPLAY = ""
_XVFB_FAILURE = ""


_TKINTER_DEPENDENT_TEST_MODULES = {
    "test_build432_bounded_traversal_and_io.py",
    "test_build469_gui_tag_and_controls.py",
    "test_build479_stabilization.py",
    "test_build480_requirements_and_mp3.py",
    "test_build483_setlistfm_upgrade_env.py",
    "test_build497_delete_extra_tags_state.py",
    "test_build499_linux_gui_startup.py",
    "test_build501_review_remediation.py",
    "test_build504_gui_state_and_upgrade_env.py",
    "test_build506_review_remediation.py",
    "test_build508_remove_dead_tagger_window.py",
    "test_build512_main_gui_workers_copy_wildcards.py",
    "test_build515_setlist_search_filename_alignment.py",
    "test_build520_partial_date_search_filename.py",
    "test_build521_behavior_security_tests.py",
    "test_build524_closure_audit.py",
    "test_build528_security_build_consistency.py",
    "test_build530_verification_accuracy.py",
}


def _tkinter_is_available():
    try:
        importlib.import_module("tkinter")
        return True
    except (ImportError, ModuleNotFoundError):
        return False


_TKINTER_AVAILABLE = _tkinter_is_available()


class _TkUnavailableModule(pytest.Module):
    def collect(self):
        pytest.skip("Tkinter is not installed; skipping Tk-dependent regression module.", allow_module_level=True)


def pytest_pycollect_makemodule(module_path, parent):
    """Skip known Tk-importing modules before Python imports them."""
    if not _TKINTER_AVAILABLE and Path(str(module_path)).name in _TKINTER_DEPENDENT_TEST_MODULES:
        return _TkUnavailableModule.from_parent(parent, path=module_path)
    return None


def _ci_enabled():
    return str(os.environ.get("CI", "")).strip().lower() not in {"", "0", "false", "no", "off"}



def _display_is_usable():
    if not os.environ.get("DISPLAY"):
        return False
    try:
        import tkinter
        root = tkinter.Tk()
        root.withdraw()
        root.update_idletasks()
        root.destroy()
        return True
    except Exception:
        return False


def _display_socket_path(display):
    number = str(display or "").lstrip(":").split(".", 1)[0]
    return Path("/tmp/.X11-unix") / f"X{number}" if number.isdigit() else None


def _stop_xvfb():
    global _XVFB_PROCESS
    proc = _XVFB_PROCESS
    _XVFB_PROCESS = None
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=2)


def _start_ci_xvfb_if_needed():
    global _XVFB_PROCESS, _XVFB_DISPLAY, _XVFB_FAILURE
    if not _ci_enabled() or not sys.platform.startswith("linux"):
        return
    if _display_is_usable():
        return
    executable = shutil.which("Xvfb")
    if not executable:
        _XVFB_FAILURE = "Xvfb is not installed"
        return

    # GitHub-hosted runners execute one TLO suite per job. Probe a short range so
    # local CI reproductions also avoid colliding with an existing X server.
    for number in range(90, 110):
        display = f":{number}"
        socket_path = _display_socket_path(display)
        if socket_path and socket_path.exists():
            continue
        proc = subprocess.Popen(
            [executable, display, "-screen", "0", "1280x1024x24", "-nolisten", "tcp"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            if socket_path and socket_path.exists():
                os.environ["DISPLAY"] = display
                _XVFB_PROCESS = proc
                _XVFB_DISPLAY = display
                atexit.register(_stop_xvfb)
                return
            time.sleep(0.05)
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1)

    _XVFB_FAILURE = "Xvfb could not start on displays :90 through :109"


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not _ci_enabled():
        return
    skipped = terminalreporter.stats.get("skipped", [])
    display_skips = []
    for report in skipped:
        reason = str(getattr(report, "longrepr", "")).lower()
        nodeid = str(getattr(report, "nodeid", ""))
        keywords = getattr(report, "keywords", {}) or {}
        if "gui" in keywords or "display" in reason or "tkinter" in reason or "research_gui" in nodeid:
            display_skips.append(nodeid)
    if not display_skips:
        return
    terminalreporter.write_sep("!", "CI COVERAGE WARNING", red=True, bold=True)
    detail = _XVFB_FAILURE or "display-dependent tests were skipped despite CI display setup"
    terminalreporter.write_line(
        f"{len(display_skips)} GUI/display test(s) were skipped: {detail}. "
        "The build should not treat this run as complete GUI coverage."
    )
    for nodeid in display_skips[:10]:
        terminalreporter.write_line(f"  - {nodeid}")


_start_ci_xvfb_if_needed()
