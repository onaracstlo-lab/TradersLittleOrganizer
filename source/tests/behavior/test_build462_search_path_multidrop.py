import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_dragdrop as DD

pytestmark = pytest.mark.behavior
__version__ = "v468"


class _FakeTk:
    def __init__(self):
        import tkinter as tk
        self._tcl = tk.Tcl()

    def splitlist(self, value):
        return self._tcl.splitlist(value)


class _Widget:
    def __init__(self):
        self.tk = _FakeTk()
        self.handler = None
        self.sequence = None

    def drop_target_register(self, *_args):
        pass

    def dnd_bind(self, name, handler):
        self.sequence = name
        self.handler = handler

    def icursor(self, *_args):
        pass

    def focus_set(self):
        pass


class _Var:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def _folder(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.mkdir()
    return path


def _event(data, action="copy"):
    return SimpleNamespace(data=data, action=action)


def _tcl_payload(*paths: Path) -> str:
    # Explorer/TkDND supplies a Tcl list. Bracing each item faithfully covers
    # spaces and ensures the regression exercises Tcl-list parsing, not tuples.
    return " ".join("{" + str(path).replace("\\", "/") + "}" for path in paths)


def test_build462_search_path_drop_appends_across_multiple_drag_actions(tmp_path, monkeypatch):
    monkeypatch.setattr(DD, "is_drag_drop_platform", lambda: True)
    first = _folder(tmp_path, "first")
    second = _folder(tmp_path, "second")
    third = _folder(tmp_path, "third")
    fourth = _folder(tmp_path, "fourth")

    widget = _Widget()
    var = _Var()
    status = DD.enable_search_path_folder_drop(widget, var)

    assert status.enabled is True
    assert widget.sequence == "<<Drop:DND_Files>>"
    assert widget.handler is not None

    assert widget.handler(_event(_tcl_payload(first))) == "copy"
    assert var.value == os.path.normpath(str(first))

    assert widget.handler(_event(_tcl_payload(second))) == "copy"
    assert var.value == ";".join(os.path.normpath(str(p)) for p in (first, second))

    assert widget.handler(_event(_tcl_payload(third, fourth))) == "copy"
    assert var.value == ";".join(os.path.normpath(str(p)) for p in (first, second, third, fourth))


def test_build462_single_drop_with_multiple_folders_inserts_semicolons(tmp_path, monkeypatch):
    monkeypatch.setattr(DD, "is_drag_drop_platform", lambda: True)
    one = _folder(tmp_path, "one")
    two = _folder(tmp_path, "two")
    three = _folder(tmp_path, "three")

    widget = _Widget()
    var = _Var()
    DD.enable_search_path_folder_drop(widget, var)

    assert widget.handler(_event(_tcl_payload(one, two, three))) == "copy"

    assert var.value == ";".join(os.path.normpath(str(p)) for p in (one, two, three))


def test_build462_drop_appends_txt_control_file_and_preserves_existing_value(tmp_path, monkeypatch):
    monkeypatch.setattr(DD, "is_drag_drop_platform", lambda: True)
    folder = _folder(tmp_path, "shows")
    control = tmp_path / "next-run.txt"
    control.write_text("# template\n", encoding="utf-8")

    widget = _Widget()
    var = _Var(str(folder))
    DD.enable_search_path_folder_drop(widget, var)
    assert widget.handler(_event(_tcl_payload(control))) == "copy"

    assert var.value == f"{os.path.normpath(str(folder))};{os.path.normpath(str(control))}"


def test_build462_dropped_path_with_semicolon_is_quoted_for_search_path_parser(tmp_path, monkeypatch):
    monkeypatch.setattr(DD, "is_drag_drop_platform", lambda: True)
    folder = _folder(tmp_path, "one;two")

    widget = _Widget()
    var = _Var()
    DD.enable_search_path_folder_drop(widget, var)
    assert widget.handler(_event(_tcl_payload(folder))) == "copy"

    assert var.value == f'"{os.path.normpath(str(folder))}"'

def test_build463_search_path_drop_returns_copy_when_tkdnd_action_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(DD, "is_drag_drop_platform", lambda: True)
    folder = _folder(tmp_path, "missing-action")
    widget = _Widget()
    var = _Var()
    DD.enable_search_path_folder_drop(widget, var)

    assert widget.handler(SimpleNamespace(data=_tcl_payload(folder))) == "copy"
    assert var.value == os.path.normpath(str(folder))


def test_build463_search_path_drop_refuses_empty_payload(monkeypatch):
    monkeypatch.setattr(DD, "is_drag_drop_platform", lambda: True)
    widget = _Widget()
    var = _Var("already-there")
    errors = []
    DD.enable_search_path_folder_drop(widget, var, on_error=errors.append)

    assert widget.handler(_event("")) == "refuse_drop"
    assert var.value == "already-there"
    assert errors


def test_build462_documentation_records_cumulative_multidrop_behavior():
    from docx import Document

    root = Path(__file__).resolve().parents[2]
    req = "\n".join(p.text for p in Document(root / "TLO_Inventory_Requirements_Working_v472.docx").paragraphs)
    manual = (root / "TLO_Inventory_User_Manual_v472.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = (root / "TLO-FAQ.txt").read_text(encoding="utf-8")

    assert "Current document version: v472 (v1.6 Build 472)." in req
    assert "Repeated drag actions are cumulative" in req
    assert "complete file list supplied by File Explorer" in req
    assert "A;B;C;D" in req
    assert "processes the complete Windows drag payload" in manual
    assert "Each drag appends its items to the existing Search Path value" in manual
    assert "Build 463 corrects the Windows TkDND handling" in faq
