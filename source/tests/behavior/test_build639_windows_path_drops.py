"""Build 639: all editable GUI path fields, including Tag Copy destination, support drops."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace
import os
import tkinter as tk

import pytest

import tlo_dragdrop as drops

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


class FakeWidget:
    def __init__(self):
        self.tk = tk.Tcl()
        self.registered = []
        self.callbacks = {}

    def drop_target_register(self, *args):
        self.registered.append(args)

    def dnd_bind(self, name, callback):
        self.callbacks[name] = callback

    def icursor(self, *_args):
        pass

    def focus_set(self):
        pass


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def test_native_windows_single_folder_drop_replaces_destination(tmp_path, monkeypatch):
    monkeypatch.setattr(drops, "is_drag_drop_platform", lambda: True)
    destination = tmp_path / "Destination With Spaces"
    destination.mkdir()
    other_file = tmp_path / "Some music.flac"
    other_file.write_bytes(b"music")
    widget, var = FakeWidget(), FakeVar("old destination")
    enabled = drops.enable_folder_path_drop(widget, var, field_label="Destination of Copies")

    assert enabled.enabled
    assert widget.registered == [("DND_Files",)]
    handler = widget.callbacks["<<Drop:DND_Files>>"]
    assert handler(SimpleNamespace(data="{" + str(destination) + "}", action="copy")) == "copy"
    assert var.value == os.path.normpath(str(destination))
    # A file dragged into a folder-only field uses its containing directory.
    assert handler(SimpleNamespace(data="{" + str(other_file) + "}", action="copy")) == "copy"
    assert var.value == os.path.normpath(str(tmp_path))


def test_other_platforms_do_not_register_drop_targets(monkeypatch):
    monkeypatch.setattr(drops, "is_drag_drop_platform", lambda: False)
    widget, var = FakeWidget(), FakeVar("original")
    status = drops.enable_folder_path_drop(widget, var, field_label="Destination of Copies")
    assert not status.enabled
    assert widget.registered == []
    assert var.value == "original"


def _load_main():
    spec = spec_from_file_location("tlo_main_build639", ROOT / "tlo-main.py")
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("delete_original", [False, True])
def test_copy_destination_dialog_wires_dnd_to_validated_path(tmp_path, monkeypatch, delete_original):
    gui = _load_main()
    try:
        root = tk.Tk()
    except tk.TclError:
        pytest.skip("Tk display required")
    root.withdraw()
    destination = tmp_path / "drop here"
    destination.mkdir()
    captured = {}

    def register(entry, var, *, field_label, on_error):
        captured.update(entry=entry, var=var, field_label=field_label, on_error=on_error)
        return drops.DragDropStatus(True, provider="test")

    def simulate_modal(dialog, *_args):
        assert captured["entry"].winfo_exists()
        assert captured["entry"].cget("textvariable") == str(captured["var"])
        assert captured["field_label"] == "Destination of Copies"
        captured["var"].set(str(destination))  # same operation as drop handler
        ok = next(widget for widget in dialog.winfo_children()
                  if isinstance(widget, __import__('tkinter').ttk.Button) and widget.cget("text") == "OK")
        assert str(ok.cget("state")) == "normal"
        ok.invoke()

    class App:
        def __init__(self):
            self.root = root

        def _destination_storage_status(self, text):
            path = Path(text)
            return (path.is_dir(), "Valid" if path.is_dir() else "Invalid", str(path) if path.is_dir() else "")

    monkeypatch.setattr(gui, "enable_folder_path_drop", register)
    monkeypatch.setattr(tk.Toplevel, "wait_visibility", lambda self: None)
    monkeypatch.setattr(tk.Toplevel, "wait_window", simulate_modal)
    try:
        result = gui.App._confirm_copy_destination(App(), delete_original=delete_original)
        assert result == str(destination)
    finally:
        root.destroy()


def test_path_entry_audit_covers_all_app_path_fields():
    source = (ROOT / "tlo-main.py").read_text(encoding="utf-8")
    # Each block has a separate path variable and matching drop registration.
    checked_blocks = {
        "Main Path(s)": ("self.search_path_entry = ttk.Entry(frm, textvariable=self.vars[\"search_path_override\"]", "self.search_path_drop_status = self._enable_search_path_drag_drop()"),
        "Tag Copy Destination": ("entry = ttk.Entry(dialog, textvariable=dest_var, width=72)", "enable_folder_path_drop(\n            entry,\n            dest_var"),
        "Copy Requests Path(s)": ("request_entry = ttk.Entry(frame, textvariable=request_var, width=72)", "enable_search_path_folder_drop(\n            request_entry,\n            request_var"),
        "Copy Requests Destination": ("destination_entry = ttk.Entry(frame, textvariable=destination_var, width=72)", "enable_folder_path_drop(\n            destination_entry,\n            destination_var"),
        "Manual Updates Original": ("self.original_entry = ttk.Entry(frm, textvariable=self.original_var, width=66)", "enable_single_folder_or_txt_drop(\n            self.original_entry"),
        "Manual Updates New Name": ("self.new_name_entry = ttk.Entry(frm, textvariable=self.new_name_var, width=66)", "enable_leaf_folder_drop(\n            self.new_name_entry"),
        "Unidentified Show Destination": ("path_entry = ttk.Entry(frame, textvariable=path_var, width=66)", "enable_folder_path_drop(\n            path_entry,\n            path_var"),
        "Add New Shows Search Path": ("self.search_path_entry = ttk.Entry(frm, textvariable=self.search_path_var, width=56)", "enable_folder_path_drop(\n            self.search_path_entry,\n            self.search_path_var"),
    }
    for label, (entry, registration) in checked_blocks.items():
        assert entry in source, f"{label}: path entry missing"
        assert registration in source, f"{label}: Windows drop registration missing"
    # Other editable entries contain worker counts, thresholds, drive labels,
    # research queries or search text; they are not path input fields.
