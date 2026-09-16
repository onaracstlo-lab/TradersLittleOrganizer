"""Build 459 standalone/GUI Tag parity for lookup and corruption controls."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_tag_lib as taglib

pytestmark = pytest.mark.behavior


ROOT = Path(__file__).resolve().parents[2]


def _load_cli():
    spec = spec_from_file_location("tlo_tag_build459", ROOT / "tlo-tag.py")
    module = module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_cli_exposes_lookup_thorough_and_corruption_controls():
    cli = _load_cli()
    args = cli._parse_args([
        "--etree-lookup",
        "--setlistfm-lookup",
        "--setlistfm-upgrade",
        "--thorough-setlist-matching",
        "--corrupt-files", "keep",
        "--corrupt-folders", "threshold",
        "--corrupt-folder-threshold", "35",
    ])
    assert args.etree_lookup is True
    assert args.setlistfm_lookup is True
    assert args.setlistfm_upgrade is True
    assert args.thorough_setlist_matching is True
    assert args.corrupt_files == "keep"
    assert args.corrupt_folders == "threshold"
    assert args.corrupt_folder_threshold == 35


def test_cli_preserves_setlistfm_dependency_and_corruption_validation():
    cli = _load_cli()
    with pytest.raises(SystemExit):
        cli._parse_args(["--setlistfm-lookup"])
    with pytest.raises(SystemExit):
        cli._parse_args(["--corrupt-folders", "threshold"])
    with pytest.raises(SystemExit):
        cli._parse_args(["--corrupt-folders", "all", "--corrupt-folder-threshold", "50"])


def test_build_tagger_config_carries_lookup_limits_thorough_and_corruption(tmp_path):
    (tmp_path / "readyForXfer").mkdir()
    cfg = taglib.build_tagger_config(
        tlo_home=str(tmp_path),
        etree_lookup=True,
        setlistfm_lookup=True,
        setlistfm_upgrade=True,
        thorough_setlist_matching=True,
        corrupt_files="keep",
        corrupt_folders="threshold",
        corrupt_folder_threshold=40,
    )
    assert cfg.setlistfm_lookup is True
    assert cfg.setlistfm_upgrade is True
    assert cfg.thorough_setlist_matching is True
    assert cfg.setlistfm_min_interval_seconds == pytest.approx(1.0 / 14.0)
    assert cfg.setlistfm_max_calls == 0
    assert cfg.setlistfm_max_calls_per_day == 48000
    assert cfg.corrupt_files == "keep"
    assert cfg.corrupt_folders == "threshold"
    assert cfg.corrupt_folder_threshold == 40


def test_process_tagging_group_applies_corruption_before_tag_mutation(monkeypatch):
    record = SimpleNamespace(artist="Artist", show_name="Artist 1970-01-01", main_dir_path="/shows/a")
    group = {"main_dir_path": "/shows/a", "music_files": ["/shows/a/01.flac"]}
    config = SimpleNamespace(corrupt_files="keep", corrupt_folders="threshold", corrupt_folder_threshold=25, standalone_tagger_corruption_enabled=True)

    monkeypatch.setattr(taglib, "_extract_metadata_for_group", lambda *a, **k: (record, [], []))
    monkeypatch.setattr(taglib, "_album_for_record", lambda *a, **k: "Album")

    calls = []
    import tlo_corruption
    monkeypatch.setattr(
        tlo_corruption,
        "handle_group_corruption",
        lambda cfg, grp, rec, corrupt_files, corrupt_folders, folder_threshold: (
            calls.append((corrupt_files, corrupt_folders, folder_threshold))
            or SimpleNamespace(show_removed=False, unverifiable=False, assessment=SimpleNamespace(unverifiable_details=[]))
        ),
    )
    monkeypatch.setattr(taglib, "tag_group_with_record", lambda *a, **k: {"groups": 1, "tagged": 1, "skipped": 0, "errors": 0})

    result = taglib.process_tagging_group(config, group, artist_matcher=None)
    assert calls == [("keep", "threshold", 25)]
    assert result["tagged"] == 1


def test_process_tagging_group_skips_when_corruption_is_unverifiable(monkeypatch):
    record = SimpleNamespace(artist="Artist", show_name="Artist 1970-01-01", main_dir_path="/shows/a")
    group = {"main_dir_path": "/shows/a", "music_files": ["/shows/a/01.flac"]}
    config = SimpleNamespace(corrupt_files="delete", corrupt_folders="all", corrupt_folder_threshold=100, standalone_tagger_corruption_enabled=True)
    monkeypatch.setattr(taglib, "_extract_metadata_for_group", lambda *a, **k: (record, [], []))

    import tlo_corruption
    monkeypatch.setattr(
        tlo_corruption,
        "handle_group_corruption",
        lambda *a, **k: SimpleNamespace(
            show_removed=False,
            unverifiable=True,
            assessment=SimpleNamespace(unverifiable_details=[("/shows/a/01.flac", "validator unavailable")]),
        ),
    )
    monkeypatch.setattr(taglib, "tag_group_with_record", lambda *a, **k: pytest.fail("must not tag unverifiable group"))

    output = []
    result = taglib.process_tagging_group(config, group, artist_matcher=None, emit=output.append)
    assert result["skipped"] == 1
    assert any("corruption status unverifiable" in line for line in output)


def test_embedded_tag_window_passes_all_four_control_families_to_run_tagger():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("totals = run_tagger(")
    block = source[start:source.index("emit=self.queue.put", start)]
    for token in (
        "setlistfm_lookup=",
        "setlistfm_upgrade=",
        "thorough_setlist_matching=",
        "corrupt_files=",
        "corrupt_folders=",
        "corrupt_folder_threshold=",
    ):
        assert token in block


def test_build459_documentation_covers_standalone_tag_option_parity():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / "TLO_Inventory_Requirements_Working_v469.docx").paragraphs)
    manual = (ROOT / "TLO_Inventory_User_Manual_v469.rtf").read_text(encoding="utf-8", errors="ignore")
    faq = (ROOT / "TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "Current document version: v469 (v1.6 Build 469)." in req
    assert "--setlistfm-upgrade" in req and "--corrupt-folder-threshold PERCENT" in req
    assert "Corruption is assessed before mutation with the same fail-closed rules as Inventory" in manual
    assert "Does standalone tlo-tag use the same setlist.fm" in faq
