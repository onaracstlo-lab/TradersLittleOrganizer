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


# Detect collection-time Tk dependencies from each test's import tree.  Do
# not maintain a manually updated list of build-numbered test filenames.
import ast


def _needs_tk_at_collection(path):
    try:
        module = ast.parse(Path(path).read_text(encoding='utf-8'))
    except (OSError, SyntaxError, UnicodeError):
        return False  # Let pytest report the real syntax/file failure.
    for item in module.body:
        # The GUI scheduling module imports Tk at module import time. Tests
        # that transitively import it also need collection-time gating on
        # minimal/headless Python installations.
        if isinstance(item, ast.Import) and any(alias.name == 'tlo_gui_shortcuts'
                                                     for alias in item.names):
            return True
        if isinstance(item, ast.Import):
            if any(alias.name == 'tkinter' or alias.name.startswith('tkinter.')
                   or alias.name in ('tkinterdnd2',) for alias in item.names):
                return True
        if isinstance(item, ast.ImportFrom):
            if item.module and (item.module == 'tkinter' or item.module.startswith('tkinter.')
                                or item.module == 'tkinterdnd2'):
                return True
        # A few GUI tests load the hyphenated GUI modules through a module
        # spec at import time.  Treat these as display-bound test modules.
        if isinstance(item, ast.Assign) and any(isinstance(v, ast.Call)
                and isinstance(v.func, ast.Attribute) and v.func.attr == 'spec_from_file_location'
                and any(isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                        and arg.value in ('tlo-main.py', 'tlo-search.py') for arg in v.args)
                for v in ast.walk(item)):
            return True
    # Modules that dynamically load the GUI in a test function must also
    # be skipped when Tk is absent; inspecting top-level imports alone
    # misses these dependencies. The module name and loader call are
    # both necessary, to avoid skipping harmless source-text inspections.
    gui_names = {'tlo-main.py', 'tlo-search.py'}
    has_gui_filename = any(isinstance(node, ast.Constant) and
                           isinstance(node.value, str) and node.value in gui_names
                           for node in ast.walk(module))
    has_dynamic_import = any(isinstance(node, ast.Call) and
                             ((isinstance(node.func, ast.Attribute) and node.func.attr == 'spec_from_file_location') or
                              (isinstance(node.func, ast.Name) and node.func.id == 'spec_from_file_location'))
                             for node in ast.walk(module))
    return has_gui_filename and has_dynamic_import


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
    if not _TKINTER_AVAILABLE and _needs_tk_at_collection(module_path):
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
