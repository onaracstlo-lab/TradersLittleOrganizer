"""Build 495 regressions for Add New Shows Search Path and standalone tlo-tag CLI defaults."""

__version__ = "v497"

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_inventory_update as update
from tlo_ux import preview_add_shows

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_tag_cli():
    spec = spec_from_file_location("tlo_tag_build495", ROOT / "tlo-tag.py")
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build495_add_new_shows_gui_has_prefilled_search_path_and_folder_drop():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("class AddToInventoryWindow:")
    block = source[start:source.index("    def _current_main_checkbox_values", start)]
    assert 'self.search_path_var = tk.StringVar(value=os.path.join(self.config.TLOHome, "readyForXfer"))' in block
    assert 'ttk.Label(frm, text="Search Path")' in block
    assert "enable_folder_path_drop(" in block
    assert 'field_label="Search Path"' in block


def test_build495_process_new_shows_uses_selected_search_path(monkeypatch, tmp_path):
    source = tmp_path / "incoming"
    source.mkdir()
    ready = tmp_path / "readyForXfer"
    ready.mkdir()
    seen = []

    monkeypatch.setattr(update, "prepare_updater_config", lambda config: config)
    monkeypatch.setattr(update, "ensure_updater_directories", lambda _home: {
        "ready": str(ready),
        "dups": str(tmp_path / "dups"),
        "staged": str(tmp_path / "staged"),
        "setlists": str(tmp_path / "setlists"),
    })
    monkeypatch.setattr(update, "load_artist_matcher", lambda _config: object())
    monkeypatch.setattr(update, "_iter_top_level_dirs", lambda path: seen.append(path) or [])

    result = update.process_new_shows(
        SimpleNamespace(TLOHome=str(tmp_path)),
        current_volume="VOL",
        search_path=str(source),
    )
    assert seen == [str(source)]
    assert result["processed"] == 0


def test_build495_add_shows_preview_uses_selected_search_path(tmp_path):
    source = tmp_path / "incoming"
    source.mkdir()
    config = SimpleNamespace(TLOHome=str(tmp_path))
    result = preview_add_shows(config, mode="new", search_path=str(source))
    assert result.roots == [str(source)]


def test_build495_tlo_tag_requires_search_folder_and_defaults_corrupt_folders_to_keep():
    cli = _load_tag_cli()
    with pytest.raises(SystemExit):
        cli._parse_args([])

    positional = cli._parse_args(["/tmp/shows"])
    assert positional.tagPath == "/tmp/shows"
    assert positional.corrupt_folders == "never"

    named = cli._parse_args(["--search-folder", "/tmp/shows"])
    assert named.tagPath == "/tmp/shows"
    assert named.corrupt_folders == "never"

    compatibility = cli._parse_args(["--tag-path", "/tmp/shows"])
    assert compatibility.tagPath == "/tmp/shows"


def test_build495_tlo_tag_explicit_corrupt_folder_policy_overrides_keep_default():
    cli = _load_tag_cli()
    args = cli._parse_args(["/tmp/shows", "--corrupt-folders", "all"])
    assert args.corrupt_folders == "all"


def test_build495_documentation_records_new_search_path_and_tagger_contract():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / "TLO_Inventory_Requirements_Working_v510.docx").paragraphs)
    manual = (ROOT / "TLO_Inventory_User_Manual_v510.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = (ROOT / "TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "Current document version: v510 (TLO v1.7)." in req
    assert "Build 495: Add New Shows Search Path and explicit tlo-tag search folder" in req
    assert "pre-filled with the current TLOHome/readyForXfer path" in req
    assert "A search folder is required on every command-line run" in req
    assert "--corrupt-folders defaults to never" in req
    assert "Version v1.7 Build 510" in manual
    assert "Build 495: Add New Shows now has a Search Path textbox" in manual
    assert "requires an explicit search folder" in faq
