"""Build 504 GUI state and setlist.fm upgrade environment regressions."""

__version__ = "v505"

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

import tlo_setlistfm_lookup as sfm

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
    spec = spec_from_file_location("tlo_ggi_build504", ROOT / "tlo-ggi.py")
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_delete_extra_tags_is_cleared_when_last_tag_mode_turns_off():
    gui = _load_gui()
    app = gui.App.__new__(gui.App)
    app.bool_vars = {
        "tag_during_inventory": _Var(False),
        "tag_copy_during_inventory": _Var(False),
        "tag_copy_and_delete_enabled": _Var(False),
        "delete_extra_tags": _Var(True),
    }
    widget = _Widget()
    app.checkbox_widgets = {"delete_extra_tags": widget}

    gui.App._sync_delete_extra_tags_state(app)

    assert app.bool_vars["delete_extra_tags"].get() is False
    assert widget.state == "disabled"


def test_delete_extra_tags_remains_available_when_any_tag_mode_is_on():
    gui = _load_gui()
    app = gui.App.__new__(gui.App)
    app.bool_vars = {
        "tag_during_inventory": _Var(True),
        "tag_copy_during_inventory": _Var(False),
        "tag_copy_and_delete_enabled": _Var(False),
        "delete_extra_tags": _Var(True),
    }
    widget = _Widget()
    app.checkbox_widgets = {"delete_extra_tags": widget}

    gui.App._sync_delete_extra_tags_state(app)

    assert app.bool_vars["delete_extra_tags"].get() is True
    assert widget.state == "normal"


def test_upgrade_key_accepts_underscore_alias(monkeypatch):
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY, raising=False)
    for alias in sfm.ENV_UPGRADE_API_KEY_ALIASES:
        monkeypatch.delenv(alias, raising=False)
    monkeypatch.setenv(sfm.ENV_API_KEY, "secret")
    monkeypatch.setenv("SETLISTFM_UPGRADE_API_KEY", "secret")
    assert sfm.upgrade_api_key_available() is True


def test_key_availability_can_use_persistent_windows_environment(monkeypatch):
    monkeypatch.delenv(sfm.ENV_API_KEY, raising=False)
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY, raising=False)
    for alias in sfm.ENV_UPGRADE_API_KEY_ALIASES:
        monkeypatch.delenv(alias, raising=False)
    persisted = {
        sfm.ENV_API_KEY: "same-secret",
        sfm.ENV_UPGRADE_API_KEY: "same-secret",
    }
    monkeypatch.setattr(sfm, "_persistent_windows_environment_value", lambda name: persisted.get(name, ""))

    assert sfm.api_key_available() is True
    assert sfm.upgrade_api_key_available() is True
    assert sfm.get_api_key() == "same-secret"


def test_gui_enables_upgrade_from_persistent_environment(monkeypatch):
    gui = _load_gui()
    monkeypatch.delenv(sfm.ENV_API_KEY, raising=False)
    monkeypatch.delenv(sfm.ENV_UPGRADE_API_KEY, raising=False)
    for alias in sfm.ENV_UPGRADE_API_KEY_ALIASES:
        monkeypatch.delenv(alias, raising=False)
    persisted = {
        sfm.ENV_API_KEY: "same-secret",
        sfm.ENV_UPGRADE_API_KEY: "same-secret",
    }
    monkeypatch.setattr(sfm, "_persistent_windows_environment_value", lambda name: persisted.get(name, ""))

    app = gui.App.__new__(gui.App)
    app.bool_vars = {"setlistfm_lookup": _Var(True), "setlistfm_upgrade": _Var(True)}
    app.checkbox_widgets = {"setlistfm_lookup": _Widget(), "setlistfm_upgrade": _Widget()}

    gui.App._apply_setlistfm_key_availability(app)

    assert app.checkbox_widgets["setlistfm_lookup"].state == "normal"
    assert app.checkbox_widgets["setlistfm_upgrade"].state == "normal"
    assert app._setlistfm_upgrade_key_available is True


def test_build504_documentation_records_both_gui_fixes():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / "TLO_Inventory_Requirements_Working_v518.docx").paragraphs)
    manual = (ROOT / "TLO_Inventory_User_Manual_v518.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = (ROOT / "TLO-FAQ.txt").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v518 (TLO v1.7)." in req
    assert "disabled/greyed and forced unchecked" in req
    assert "SETLISTFM_UPGRADE_API_KEY" in req
    assert "persisted User/System environment" in req
    assert "Delete Extra Tags is greyed out and unchecked" in manual
    assert "SETLISTFM_UPGRADE_API_KEY" in manual
    assert "setx" in faq
