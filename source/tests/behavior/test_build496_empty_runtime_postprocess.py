"""Build 496 regressions for empty current-run metadata during postprocess."""

__version__ = "v497"

from pathlib import Path
from types import SimpleNamespace

import pytest

import tlo_postprocess as post
import walk_trees_lib as walk
from tlo_bootlist_volume_policy import read_bootlist_rows, write_bootlist_rows

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _write_meta(logs_dir: Path, token: str, *, show: str, path: str, volume: str = "VOL1") -> None:
    (logs_dir / f"meta{token}.log").write_text(
        f"SHOW_NAME: {show}\n"
        "SHOW_IN_CONFLICT: no\n"
        f"MAIN_DIR_PATH: {path}\n"
        "GROUP_NUMBER: 1\n"
        f"MAIN_DIR_NAME: {show}\n"
        "SETLIST_FILE: \n"
        "MUSIC_FILE_COUNT: 1\n"
        f"VOLUME_LABEL: {volume}\n"
        "ARTIST: Old Artist\n"
        "DATE: 2001-04-14\n"
        "VENUE: Old Venue\n"
        "LOCATION: Old City ST\n"
        "PARENTHETICALS: \n"
        "ALBUM_NAME: \n"
        "IS_24_BIT: no\n"
        "END_SHOW_METADATA\n",
        encoding="utf-8",
    )


def test_build496_authoritative_empty_runtime_records_do_not_reread_reused_token(tmp_path, capsys):
    logs = tmp_path / "logs"
    logs.mkdir()
    _write_meta(logs, "0", show="Historical Show", path="C:/old/show")
    write_bootlist_rows(
        str(tmp_path),
        [{"Show": "Historical Show", "VolumePath": "[VOL1] /old/show"}],
    )

    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        inventory_volume_actions={"vol1": "append"},
        inventory_path_actions=[{
            "volume": "VOL1",
            "volume_key": "vol1",
            "path": "C:/tmpTorrents",
            "action": "append",
        }],
        current_run_log_tokens=["0"],
        current_metadata_records=[],
        current_metadata_records_ready=True,
        silent=False,
    )

    post.postprocess_metadata_outputs(config)

    rows = read_bootlist_rows(str(tmp_path))
    assert len(rows) == 1
    assert rows[0]["Show"] == "Historical Show"
    out = capsys.readouterr().out
    assert "using in-memory metadata records complete: 0 record(s)" in out
    assert "reading metadata logs complete: 1 record(s)" not in out
    assert "wrote/reused 0 row(s)" in out


def test_build496_walk_trees_marks_empty_current_run_records_ready(monkeypatch, tmp_path):
    monkeypatch.setattr(walk, "prepare_inventory_items", lambda _config: [])
    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        compliant=False,
        etree_lookup=False,
        performance_mode="balanced",
        max_workers=1,
        current_corruption_removed_paths=[],
        current_metadata_records=[{"stale": "value"}],
        current_metadata_records_ready=True,
        inventory_volume_actions={},
        silent=True,
        cancel_requested=False,
    )

    records = walk.walk_trees(config)

    assert records == []
    assert config.current_metadata_records == []
    assert config.current_metadata_records_ready is True


def test_build496_log_fallback_still_works_when_runtime_records_are_not_ready(tmp_path):
    logs = tmp_path / "logs"
    logs.mkdir()
    _write_meta(logs, "N", show="Log Fallback Show", path="/new/path")
    config = SimpleNamespace(
        TLOHome=str(tmp_path),
        inventory_volume_actions={},
        inventory_path_actions=[],
        current_run_log_tokens=["N"],
        current_metadata_records=[],
        current_metadata_records_ready=False,
        silent=True,
    )

    post.postprocess_metadata_outputs(config)

    rows = read_bootlist_rows(str(tmp_path))
    assert [row["Show"] for row in rows] == ["Log Fallback Show"]


def test_build496_documentation_records_empty_runtime_postprocess_fix():
    from docx import Document

    req = "\n".join(p.text for p in Document(ROOT / "TLO_Inventory_Requirements_Working_v511.docx").paragraphs)
    manual = (ROOT / "TLO_Inventory_User_Manual_v511.rtf").read_text(encoding="utf-8", errors="ignore")
    assert "Current document version: v511 (TLO v1.7)." in req
    assert "Build 496: Empty current-run metadata must not reread reused historical logs" in req
    assert "that in-memory list is authoritative even when it is empty" in req
    assert "Version v1.7 Build 511" in manual
    assert "does not reread old metadata from that reused token" in manual
    assert "duplicate bootlist rows" in req or "duplicate existing bootlist rows" in manual
