"""Build 430 regressions for re-inventory detail, unknown-date sibling safety, and Ctrl+A."""

from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("tkinter", reason="Tkinter is required for GUI regression tests")

import tlo_gui_shortcuts as shortcuts
import tlo_postprocess as post
import tlo_sibling_collections as sibling

__version__ = "v433"

pytestmark = [pytest.mark.behavior, pytest.mark.gui]


def _audio(folder: Path, name="01.flac"):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(b"audio")


def test_unknown_full_date_placeholder_blocks_sibling_collection_consolidation(tmp_path):
    root = tmp_path / "boots"
    d1 = root / "Artist - xxxx-xx-xx Mystery D1"
    d2 = root / "Artist - xxxx-xx-xx Mystery D2"
    _audio(d1)
    _audio(d2)
    paths = [str(d1 / "01.flac"), str(d2 / "01.flac")]

    assert sibling.discover_collection_plans(str(root), paths) == []


@pytest.mark.parametrize("placeholder", ["xxxx-xx-xx", "XXXX-XX-XX", "xxxx.xx.xx", "xxxx/xx/xx"])
def test_unknown_full_date_placeholder_variants_block_collection(tmp_path, placeholder):
    root = tmp_path / "boots"
    left = root / f"Artist - {placeholder} Archive CD1"
    right = root / f"Artist - {placeholder} Archive CD2"
    _audio(left)
    _audio(right)
    assert sibling.discover_collection_plans(
        str(root), [str(left / "01.flac"), str(right / "01.flac")]
    ) == []


class _FakeRoot:
    def __init__(self):
        self.bindings = []

    def bind_class(self, class_name, sequence, callback, add=None):
        self.bindings.append((class_name, sequence, callback, add))


class _FakeEntry:
    def __init__(self):
        self.selected = None
        self.cursor = None

    def selection_range(self, start, end):
        self.selected = (start, end)

    def icursor(self, index):
        self.cursor = index


class _FakeText:
    def __init__(self):
        self.calls = []

    def tag_remove(self, *args):
        self.calls.append(("remove",) + args)

    def tag_add(self, *args):
        self.calls.append(("add",) + args)

    def mark_set(self, *args):
        self.calls.append(("mark",) + args)

    def see(self, *args):
        self.calls.append(("see",) + args)


def test_global_ctrl_a_installs_for_entry_combobox_and_text_classes():
    root = _FakeRoot()
    shortcuts.install_global_ctrl_a(root)
    pairs = {(class_name, sequence) for class_name, sequence, _callback, _add in root.bindings}

    for class_name in ("Entry", "TEntry", "TCombobox", "Text"):
        assert (class_name, "<Control-a>") in pairs
        assert (class_name, "<Control-A>") in pairs


def test_ctrl_a_entry_handler_selects_complete_input():
    widget = _FakeEntry()
    assert shortcuts._select_all_entry(SimpleNamespace(widget=widget)) == "break"
    assert widget.selected[0] == 0
    assert widget.cursor is not None


def test_ctrl_a_text_handler_selects_main_console_style_text_widget():
    widget = _FakeText()
    assert shortcuts._select_all_text(SimpleNamespace(widget=widget)) == "break"
    assert ("add", "sel", "1.0", "end-1c") in widget.calls


def _row(show, path, volume="VOL"):
    return {"Show": show, "Volume": volume, "Path": path, "VolumePath": f"[{volume}] {path}"}


def test_reinventory_detail_accounts_for_terminal_and_mutation_dispositions():
    old_rows = [
        _row("Same Show", "/boots/same"),
        _row("Old Metadata", "/boots/metadata"),
        _row("Renamed Show", "/boots/old-name"),
        _row("Corrupt Show", "/boots/corrupt"),
        _row("Unknown Show", "/boots/unresolved"),
        _row("Missing Show", "/boots/missing"),
    ]
    new_rows = [
        _row("Same Show", "/boots/same"),
        _row("New Metadata", "/boots/metadata"),
        _row("Renamed Show", "/boots/new-name"),
        _row("Brand New", "/boots/new"),
    ]
    records = [{
        "volume_label": "VOL",
        "main_dir_path": "/boots/new-name",
        "original_main_dir_path": "/boots/old-name",
        "show_name": "Renamed Show",
    }]

    details, new_only, counts = post._build_reinventory_entry_dispositions(
        old_rows,
        records,
        new_rows,
        ["/boots/unresolved"],
        ["/boots/corrupt"],
    )

    statuses = {item["old_show"]: item["status"] for item in details}
    assert statuses == {
        "Same Show": "UNCHANGED",
        "Old Metadata": "METADATA_CHANGED",
        "Renamed Show": "RENAMED",
        "Corrupt Show": "CORRUPTION_REMOVED",
        "Unknown Show": "UNRESOLVED",
        "Missing Show": "MISSING",
    }
    assert [item["show"] for item in new_only] == ["Brand New"]
    assert counts["NEW"] == 1


def test_reinventory_delta_log_contains_per_entry_detail_but_summary_formatter_can_stay_compact(tmp_path):
    data = {
        "scopes": ["[vol] /boots"],
        "previous_rows_replaced": 1,
        "groups_prepared": 1,
        "prepared_vs_previous_delta": 0,
        "stage3_records": 1,
        "stage3_groups_omitted": 0,
        "corruption_groups_removed": 0,
        "corruption_removed_paths": [],
        "final_new_rows": 1,
        "unresolved_rows_omitted": 0,
        "unidentified_paths": [],
        "net_replacement_row_change": 0,
        "disposition_counts": {"UNCHANGED": 1, "NEW": 0},
        "entry_dispositions": [{
            "status": "UNCHANGED",
            "old_show": "Artist 2000-01-01",
            "old_volume_path": "[VOL] /boots/show",
            "current": [{"show": "Artist 2000-01-01", "volume_path": "[VOL] /boots/show"}],
            "reason": "same volume/path and same Show value",
        }],
        "new_only_rows": [],
    }

    compact = "\n".join(post._format_reinventory_reconciliation_lines(data))
    detailed = "\n".join(post._format_reinventory_reconciliation_lines(data, include_details=True))
    assert "Previous-row dispositions" not in compact
    assert "Previous-row dispositions" in detailed
    assert "STATUS: UNCHANGED" in detailed

    path = post._write_reinventory_delta_log(str(tmp_path), data)
    written = Path(path).read_text(encoding="utf-8")
    assert "STATUS: UNCHANGED" in written
    assert "OLD PATH: [VOL] /boots/show" in written


def test_all_gui_entry_points_install_global_ctrl_a_class_bindings():
    root = Path(__file__).resolve().parents[2]
    for filename in ("tlo-ggi.py", "tlo-gsi.py", "search-artist-db.py"):
        text = (root / filename).read_text(encoding="utf-8")
        assert "from tlo_gui_shortcuts import install_global_ctrl_a" in text
        assert "install_global_ctrl_a(self.root)" in text


def test_record_path_rewrite_preserves_first_original_main_dir_path():
    import tlo_models
    import tlo_tag_lib

    record = tlo_models.ShowMetadata(
        group_number=1,
        main_dir_name="Old",
        main_dir_path="/boots/Old",
        setlist_file="/boots/Old/info.txt",
        music_file_count=1,
        music_dirs=["/boots/Old"],
        show_name="Artist 2000-01-01",
    )
    once = tlo_tag_lib._rewrite_record_paths(record, "/boots/Old", "/boots/New", mutate=False)
    twice = tlo_tag_lib._rewrite_record_paths(once, "/boots/New", "/archive/New", mutate=False)

    assert once.main_dir_path == "/boots/New"
    assert once.original_main_dir_path == "/boots/Old"
    assert twice.main_dir_path == "/archive/New"
    assert twice.original_main_dir_path == "/boots/Old"
