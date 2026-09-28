"""Build 499: map the main Tk root before first-open sizing/stabilization."""

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v499"


def _gui_module():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[2] / "tlo-ggi.py"
    spec = importlib.util.spec_from_file_location("tlo_ggi_build499", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


class _Root:
    def __init__(self, state="withdrawn"):
        self.current_state = state
        self.calls = []
        self.idle_callback = None

    def state(self, value=None):
        if value is None:
            self.calls.append(("state-get", self.current_state))
            return self.current_state
        self.calls.append(("state-set", value))
        self.current_state = value

    def deiconify(self):
        self.calls.append(("deiconify",))
        self.current_state = "normal"

    def update_idletasks(self):
        self.calls.append(("update-idletasks",))

    def lift(self):
        self.calls.append(("lift",))

    def after_idle(self, callback):
        self.calls.append(("after-idle",))
        self.idle_callback = callback
        return "idle-1"


def test_build499_show_maps_before_first_fit_and_schedules_second_stabilization():
    gui = _gui_module()
    app = gui.App.__new__(gui.App)
    app.root = _Root()
    calls = []
    app._fit_initial_window_to_screen = lambda: calls.append("fit")

    app._show_main_window()

    assert app.root.current_state == "normal"
    assert ("deiconify",) in app.root.calls
    assert "fit" in calls
    assert app.root.calls.index(("deiconify",)) < app.root.calls.index(("lift",))
    assert app.root.idle_callback is not None


def test_build499_idle_stabilizer_recovers_withdrawn_or_iconic_root():
    gui = _gui_module()
    app = gui.App.__new__(gui.App)
    app.root = _Root(state="iconic")
    calls = []
    app._fit_initial_window_to_screen = lambda: calls.append("fit")

    app._stabilize_main_window()

    assert app.root.current_state == "normal"
    assert calls == ["fit"]
    assert ("lift",) in app.root.calls


def test_build499_main_uses_mapped_startup_helper_instead_of_raw_deiconify():
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2] / "tlo-ggi.py").read_text(encoding="utf-8")
    main = source[source.index("def main() -> int:"):]
    assert "root.withdraw()" in main
    assert "app = App(root, cli_args=cli_args)" in main
    assert "app._show_main_window()" in main
    assert "root.deiconify()" not in main
