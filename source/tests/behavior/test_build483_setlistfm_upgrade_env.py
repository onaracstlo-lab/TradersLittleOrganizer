"""Build 483: setlist.fm upgrade requires its own explicit environment gate."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

import tlo_setlistfm_lookup as sfm
from tlo_options import SETLISTFM_UPGRADE_KEY_ERROR, validate_setlistfm_upgrade_environment

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


class _Var:
    def __init__(self, value=False):
        self.value = bool(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)


class _Widget:
    def __init__(self):
        self.state = None

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]


def _load_gui():
    spec = spec_from_file_location("tlo_ggi_build483", ROOT / "tlo-ggi.py")
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _app_stub(gui, *, lookup=True, upgrade=True):
    app = gui.App.__new__(gui.App)
    app.bool_vars = {
        "setlistfm_lookup": _Var(lookup),
        "setlistfm_upgrade": _Var(upgrade),
    }
    app.checkbox_widgets = {
        "setlistfm_lookup": _Widget(),
        "setlistfm_upgrade": _Widget(),
    }
    return app


def test_upgrade_environment_presence_is_independent(monkeypatch):
    monkeypatch.delenv(sfm.ENV_API_KEY, raising=False)
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY, raising=False)
    assert sfm.api_key_available() is False
    assert sfm.upgrade_api_key_available() is False

    monkeypatch.setenv(sfm.ENV_API_KEY, "same-secret")
    assert sfm.api_key_available() is True
    assert sfm.upgrade_api_key_available() is False

    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "same-secret")
    assert sfm.upgrade_api_key_available() is True


def test_gui_enables_lookup_but_greys_upgrade_when_upgrade_variable_missing(monkeypatch):
    gui = _load_gui()
    monkeypatch.setenv(sfm.ENV_API_KEY, "same-secret")
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY, raising=False)
    app = _app_stub(gui, lookup=True, upgrade=True)

    gui.App._apply_setlistfm_key_availability(app)

    assert app.bool_vars["setlistfm_lookup"].get() is True
    assert app.bool_vars["setlistfm_upgrade"].get() is False
    assert app.checkbox_widgets["setlistfm_lookup"].state == "normal"
    assert app.checkbox_widgets["setlistfm_upgrade"].state == "disabled"
    assert app._setlistfm_key_available is True
    assert app._setlistfm_upgrade_key_available is False


def test_gui_enables_upgrade_only_when_both_variables_are_present(monkeypatch):
    gui = _load_gui()
    monkeypatch.setenv(sfm.ENV_API_KEY, "same-secret")
    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "same-secret")
    app = _app_stub(gui, lookup=True, upgrade=True)

    gui.App._apply_setlistfm_key_availability(app)

    assert app.bool_vars["setlistfm_lookup"].get() is True
    assert app.bool_vars["setlistfm_upgrade"].get() is True
    assert app.checkbox_widgets["setlistfm_lookup"].state == "normal"
    assert app.checkbox_widgets["setlistfm_upgrade"].state == "normal"
    assert app._setlistfm_upgrade_key_available is True


def test_gui_disables_both_when_normal_key_is_missing_even_if_upgrade_variable_exists(monkeypatch):
    gui = _load_gui()
    monkeypatch.delenv(sfm.ENV_API_KEY, raising=False)
    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "same-secret")
    app = _app_stub(gui, lookup=True, upgrade=True)

    gui.App._apply_setlistfm_key_availability(app)

    assert app.bool_vars["setlistfm_lookup"].get() is False
    assert app.bool_vars["setlistfm_upgrade"].get() is False
    assert app.checkbox_widgets["setlistfm_lookup"].state == "disabled"
    assert app.checkbox_widgets["setlistfm_upgrade"].state == "disabled"


def test_upgrade_cli_validation_requires_second_environment_variable(monkeypatch):
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY, raising=False)
    with pytest.raises(ValueError, match="SETLISTFMUPGRADE_API_KEY"):
        validate_setlistfm_upgrade_environment({"setlistfm_upgrade": True})
    assert "same setlist.fm API key" in SETLISTFM_UPGRADE_KEY_ERROR

    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "same-secret")
    validate_setlistfm_upgrade_environment({"setlistfm_upgrade": True})
    validate_setlistfm_upgrade_environment({"setlistfm_upgrade": False})
