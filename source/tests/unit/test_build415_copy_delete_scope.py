"""Build 415 Copy/Delete destination replacement-scope regressions."""

from types import SimpleNamespace

import pytest

import inventory_list_lib as IL
import tlo_postprocess as PP
from tlo_bootlist_volume_policy import write_bootlist_rows

pytestmark = pytest.mark.unit


def test_copy_delete_destination_container_is_append_not_reinventory(monkeypatch):
    config = SimpleNamespace(TLOHome="/tmp/tlo", silent=True)
    monkeypatch.setattr(
        IL,
        "read_group_log_volume_rows",
        lambda _home: [
            {"Volume": "DESTVOL", "Path": "/mnt/d/boots", "Token": "1"},
            {"Volume": "DESTVOL", "Path": "/mnt/d/boots/Old Show", "Token": "1"},
        ],
    )
    monkeypatch.setattr(
        IL,
        "_volume_identity_for_physical_path",
        lambda path: ("DESTVOL", "dest-key"),
    )

    actions = IL._resolve_existing_volume_actions(
        config,
        [("/mnt/d/x", "", "SOURCEVOL", "source-key", "copy-delete", "/mnt/d/boots")],
    )

    assert actions[0]["copy_mode"] == "copy-delete"
    assert actions[0]["path"] == "/mnt/d/boots"
    assert actions[0]["action"] == "new"


def test_copy_delete_into_large_existing_destination_preserves_unrelated_rows(tmp_path, monkeypatch):
    home = str(tmp_path)
    existing = [
        {"Show": f"Old Show {i}", "Volume": "DESTVOL", "Path": f"/mnt/d/boots/Old Show {i}"}
        for i in range(2135)
    ]
    existing += [
        {"Show": f"Keep Elsewhere {i}", "Volume": "DESTVOL", "Path": f"/mnt/d/elsewhere/Keep {i}"}
        for i in range(7)
    ]
    write_bootlist_rows(home, existing)

    config = SimpleNamespace(
        TLOHome=home,
        inventory_path_actions=[{
            "volume": "DESTVOL",
            "path": "/mnt/d/boots",
            "action": "new",
            "copy_mode": "copy-delete",
            "copy_destination": "/mnt/d/boots",
        }],
        inventory_volume_actions={"destvol": "new"},
    )
    records = [
        SimpleNamespace(main_dir_path=f"/mnt/d/boots/New Show {i}")
        for i in range(29)
    ]

    kept, replaced = PP._existing_rows_for_postprocess(config, records=records)

    assert len(kept) == 2142
    assert replaced == []


def test_copy_delete_replaces_only_exact_current_destination_row(tmp_path):
    home = str(tmp_path)
    write_bootlist_rows(home, [
        {"Show": "Prior Exact", "Volume": "DESTVOL", "Path": "/mnt/d/boots/New Show 0"},
        {"Show": "Prior Child", "Volume": "DESTVOL", "Path": "/mnt/d/boots/New Show 0/Disc 1"},
        {"Show": "Other", "Volume": "DESTVOL", "Path": "/mnt/d/boots/Other Show"},
    ])
    config = SimpleNamespace(
        TLOHome=home,
        inventory_path_actions=[{
            "volume": "DESTVOL",
            "path": "/mnt/d/boots",
            "action": "new",
            "copy_mode": "copy-delete",
            "copy_destination": "/mnt/d/boots",
        }],
        inventory_volume_actions={"destvol": "new"},
    )

    kept, replaced = PP._existing_rows_for_postprocess(
        config,
        records=[SimpleNamespace(main_dir_path="/mnt/d/boots/New Show 0")],
    )

    assert [row["Show"] for row in replaced] == ["Prior Exact"]
    assert {row["Show"] for row in kept} == {"Prior Child", "Other"}
