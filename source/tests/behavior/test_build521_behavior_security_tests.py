"""Build 521 behavior/security/test remediation regressions."""

from __future__ import annotations

import base64
import builtins
import importlib.util
import sys
from pathlib import Path

import pytest

import tlo_options as options
import tlo_update_trust as trust
import tlo_ux as ux
from tlo_text_utils import MAX_TEXT_FULL_BYTES

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build521_main_parser_accepts_documented_setlist_flags():
    gui = _load("tlo-main.py", "tlo_main_build521_parser")
    args = gui._parse_gui_command_line(["--thorough-setlist-matching"])
    assert args.thorough_setlist_matching is True
    args = gui._parse_gui_command_line([
        "--etree-lookup",
        "--setlistfm-lookup",
        "--setlistfm-upgrade",
    ])
    assert args.etree_lookup is True
    assert args.setlistfm_lookup is True
    assert args.setlistfm_upgrade is True
    seeded = gui._initial_checkbox_values(args)
    assert seeded["setlistfm_lookup"] is True
    assert seeded["setlistfm_upgrade"] is True

    thorough_args = gui._parse_gui_command_line(["--thorough-setlist-matching"])
    thorough_seeded = gui._initial_checkbox_values(thorough_args)
    assert thorough_seeded["thorough_setlist_matching"] is True


def test_build521_main_parser_accepts_every_help_registry_flag():
    gui = _load("tlo-main.py", "tlo_main_build521_all_help_flags")
    # Exercise representative valid values for every registry-backed field shown
    # in tlo-main's generated help table. Dependency-sensitive fields are grouped.
    probes = [
        ["--search-path", str(ROOT)],
        ["--compliant"],
        ["--as-is-artist-name"],
        ["--proper-grammar"],
        ["--tag-during-inventory"],
        ["--no-artist-in-album"],
        ["--tag-copy-during-inventory"],
        ["--tag-copy-destination", str(ROOT)],
        ["--tag-copy-delete-original"],
        ["--tag-copy-and-delete", str(ROOT)],
        ["--rename-compliantly"],
        ["--convert-shn"],
        ["--delete-extra-tags"],
        ["--etree-lookup"],
        ["--etree-lookup", "--setlistfm-lookup"],
        ["--setlistfm-upgrade"],
        ["--thorough-setlist-matching"],
        ["--corrupt-files", "keep"],
        ["--corrupt-folders", "never"],
        ["--corrupt-folders", "threshold", "--corrupt-folder-threshold", "50"],
        ["--performance-mode", "fast"],
        ["--max-workers", "2"],
        ["--current-storage-volume", "Archive"],
    ]
    for argv in probes:
        gui._parse_gui_command_line(argv)


def test_build521_main_help_is_registry_backed_and_complete():
    gui = _load("tlo-main.py", "tlo_main_build521_help")
    assert gui.HELP_TEXT.startswith("tlo-main\n")
    assert "Path(s)" in gui.HELP_TEXT
    for field in gui._MAIN_HELP_FIELDS:
        option = options.OPTIONS_BY_FIELD[field]
        assert option.flag in gui.HELP_TEXT
    for expected in (
        "--proper-grammar",
        "--no-artist-in-album",
        "--corrupt-files",
        "--corrupt-folders",
        "--corrupt-folder-threshold",
        "--setlistfm-upgrade",
        "--thorough-setlist-matching",
    ):
        assert expected in gui.HELP_TEXT
    assert "Search Path      --search-path" not in gui.HELP_TEXT


def test_build521_review_labels_come_from_option_registry():
    for field, label in ux.MAIN_WINDOW_CHECKBOX_SPECS:
        if field == "dry_run":
            assert label == "Dry Run"
        else:
            assert label == options.OPTIONS_BY_FIELD[field].gui_label
    labels = dict(ux.MAIN_WINDOW_CHECKBOX_SPECS)
    assert labels["tag_during_inventory"] == "Tag In Place"
    assert labels["artist_in_album"] == "Artist In Album Tag"
    assert labels["setlistfm_upgrade"] == "setlist.fm Upgrade"


def test_build521_search_uses_shared_bounded_reader(tmp_path):
    search = _load("tlo-search.py", "tlo_search_build521_reader")
    small = tmp_path / "small.txt"
    small.write_text("hello", encoding="utf-8")
    assert search.read_text_file(small) == "hello"

    oversized = tmp_path / "oversized.txt"
    oversized.write_bytes(b"x" * (MAX_TEXT_FULL_BYTES + 1))
    assert search.read_text_file(oversized) == ""


def test_build521_packaged_help_names_are_executable_style(capsys):
    main = _load("tlo-main.py", "tlo_main_build521_prog")
    tag = _load("tlo-tag.py", "tlo_tag_build521_prog")
    delete_dupes = _load("tlo-deleteDupes.py", "tlo_delete_dupes_build521_prog")
    search = _load("tlo-search.py", "tlo_search_build521_prog")

    with pytest.raises(SystemExit) as exc:
        main._parse_gui_command_line(["--help"])
    assert exc.value.code == 0
    assert "usage: tlo-main" in capsys.readouterr().out

    with pytest.raises(SystemExit) as exc:
        tag._parse_args(["--help"])
    assert exc.value.code == 0
    assert "usage: tlo-tag" in capsys.readouterr().out

    with pytest.raises(SystemExit) as exc:
        delete_dupes._parse_args(["--help"])
    assert exc.value.code == 0
    assert "usage: tlo-deleteDupes" in capsys.readouterr().out

    with pytest.raises(SystemExit) as exc:
        search.parse_cli_args(["--help"])
    assert exc.value.code == 0
    search_help = capsys.readouterr().out
    assert search_help.startswith("tlo-search\n")
    assert "python3 tlo-search" not in search_help


def test_build521_dialog_title_helper_versions_titles():
    gui = _load("tlo-main.py", "tlo_main_build521_dialog_title")
    title = gui._dialog_title("Manual Updates")
    assert title.startswith("Manual Updates v1.7 Build ")
    source = (ROOT / "tlo-main.py").read_text(encoding="utf-8")
    assert 'messagebox.showinfo("tlo-main"' not in source
    assert 'messagebox.showwarning("tlo-main"' not in source
    assert 'messagebox.showerror("tlo-main"' not in source


def test_build521_signature_value_at_or_above_modulus_is_rejected_before_pow(monkeypatch):
    n = (1 << 3071) + 643
    k = (n.bit_length() + 7) // 8
    monkeypatch.setattr(trust, "PINNED_UPDATE_SIGNING_KEY_ID", "test")
    monkeypatch.setattr(trust, "PINNED_UPDATE_SIGNING_RSA_N_B64", base64.b64encode(n.to_bytes(k, "big")).decode("ascii"))
    monkeypatch.setattr(trust, "PINNED_UPDATE_SIGNING_RSA_E_B64", base64.b64encode((65537).to_bytes(3, "big")).decode("ascii"))

    def fail_pow(*_args, **_kwargs):
        raise AssertionError("pow() must not be reached for signature >= modulus")

    monkeypatch.setattr(builtins, "pow", fail_pow)
    signature = base64.b64encode(n.to_bytes(k, "big")).decode("ascii")
    assert trust.verify_metadata_signature({"key_id": "test"}, signature) is False
