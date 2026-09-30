"""Build 497 regressions for Delete Extra Tags GUI availability."""

__version__ = "v497"

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_gui():
    spec = spec_from_file_location("tlo_ggi_build497", ROOT / "tlo-ggi.py")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeVar:
    def __init__(self, value=False):
        self.value = bool(value)

    def get(self):
        return self.value

    def set(self, value):
        self.value = bool(value)


class FakeWidget:
    def __init__(self):
        self.state = None

    def configure(self, **kwargs):
        if "state" in kwargs:
            self.state = kwargs["state"]


def _app_with_modes(gui, *, in_place=False, copy=False, delete=False, extra=True):
    app = object.__new__(gui.App)
    app.bool_vars = {
        "tag_during_inventory": FakeVar(in_place),
        "tag_copy_during_inventory": FakeVar(copy),
        "tag_copy_and_delete_enabled": FakeVar(delete),
        "delete_extra_tags": FakeVar(extra),
    }
    widget = FakeWidget()
    app.checkbox_widgets = {"delete_extra_tags": widget}
    app._tag_mode_syncing = False
    app._schedule_inline_validation = lambda *_args: None
    return app, widget


def test_build497_delete_extra_tags_is_disabled_when_no_tag_mode_is_selected():
    gui = _load_gui()
    app, widget = _app_with_modes(gui, extra=True)

    app._sync_delete_extra_tags_state()

    assert widget.state == "disabled"
    assert app.bool_vars["delete_extra_tags"].get() is False


@pytest.mark.parametrize(
    "field",
    ["tag_during_inventory", "tag_copy_during_inventory", "tag_copy_and_delete_enabled"],
)
def test_build497_any_tag_mode_enables_delete_extra_tags(field):
    gui = _load_gui()
    app, widget = _app_with_modes(gui)
    app.bool_vars[field].set(True)

    app._sync_delete_extra_tags_state()

    assert widget.state == "normal"


def test_build497_tag_mode_click_keeps_modes_exclusive_and_syncs_delete_extra_tags():
    gui = _load_gui()
    app, widget = _app_with_modes(gui, in_place=True, copy=True, delete=True)

    app._tag_mode_clicked("tag_copy_and_delete_enabled")

    assert app.bool_vars["tag_during_inventory"].get() is False
    assert app.bool_vars["tag_copy_during_inventory"].get() is False
    assert app.bool_vars["tag_copy_and_delete_enabled"].get() is True
    assert widget.state == "normal"

    app.bool_vars["tag_copy_and_delete_enabled"].set(False)
    app._tag_mode_clicked("tag_copy_and_delete_enabled")
    assert widget.state == "disabled"


def test_build497_gui_wires_initial_state_sync_after_tag_mode_exclusivity():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    assert "def _sync_delete_extra_tags_state" in source
    assert 'widget.configure(state=("normal" if tag_mode_enabled else "disabled"))' in source
    assert "self._reapply_tag_mode_exclusivity()" in source
    assert "self._sync_delete_extra_tags_state()" in source


def test_build497_documentation_records_delete_extra_tags_gui_state_rule():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / "TLO_Inventory_Requirements_Working_v517.docx").paragraphs)
    manual = (ROOT / "TLO_Inventory_User_Manual_v517.rtf").read_text(encoding="utf-8", errors="ignore")

    assert "Current document version: v517 (TLO v1.7)." in req
    assert "Build 497: Delete Extra Tags GUI availability" in req
    assert "The main-GUI checkbox is disabled/greyed and forced unchecked whenever Tag in Place, Tag Copy, and Tag Copy/Delete Original are all unchecked" in req
    assert "Version v1.7 Build 517" in manual
    assert "Delete Extra Tags is greyed out and unchecked whenever Tag in Place, Tag Copy, and Tag Copy/Delete Original are all unchecked" in manual
    assert "The three tag modes remain mutually exclusive" in req
