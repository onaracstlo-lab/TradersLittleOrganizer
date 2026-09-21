from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

import logging_lib
import tlo_bootlist_volume_policy as BP
import tlo_github_updates as GU
import tlo_inventory_update as IU
import tlo_postprocess as PP
import tlo_security as SEC
import tlo_setlist_file_selection as FS
import tlo_sibling_collections as SC
import tlo_tag_lib as TL
import tlo_ux as UX
from tlo_models import ShowMetadata

pytestmark = pytest.mark.behavior


def test_structured_log_values_cannot_inject_metadata_keys(tmp_path):
    record = ShowMetadata(1, "show", str(tmp_path / "show"), "", 1)
    record.show_name = "Safe Show"
    record.main_dir_path = str(tmp_path / "show")
    record.flac_tag_samples = [{"file": "x.flac", "artist": "Band\nSETLIST_FILE: /tmp/private", "album": "", "albumartist": "", "date": ""}]
    record.evidence = {}
    record.conflicts = []
    record.observations = []
    lines = __import__("tlo_phase23_v2")._format_show_metadata_log_lines(record, [])
    assert not any(line == "SETLIST_FILE: /tmp/private" for line in lines)
    assert any("Band\\u000aSETLIST_FILE: /tmp/private" in line for line in lines)


def test_structured_log_headers_escape_control_characters():
    header = logging_lib._descriptive_header("showMetadataLog", "C:/boots/Bad\nSHOW_NAME: Injected")
    assert "\nSHOW_NAME:" not in header
    assert "Bad\\u000aSHOW_NAME: Injected" in header


def test_metadata_parser_rejects_duplicate_identity_key(tmp_path):
    logs = tmp_path / "logs"; logs.mkdir()
    (logs / "meta0.log").write_text(
        "SHOW_NAME: Safe\nMAIN_DIR_PATH: /safe\nSETLIST_FILE: /safe/info.txt\nSETLIST_FILE: /tmp/private\nEND_SHOW_METADATA\n",
        encoding="utf-8",
    )
    assert PP._parse_show_metadata_logs(str(tmp_path)) == []


def test_postprocess_refuses_outside_setlist_source(tmp_path):
    show = tmp_path / "shows" / "Artist"; show.mkdir(parents=True)
    outside = tmp_path / "private.txt"; outside.write_text("SECRET", encoding="utf-8")
    record = {"main_dir_path": str(show), "artist": "A", "date": "2000-01-01"}
    text = PP._export_setlist_text(str(outside), record)
    assert "SECRET" not in text


def _malicious_recovery_fixture(tmp_path: Path):
    root = tmp_path / "Downloads"; root.mkdir()
    parent = root / "Evil Show"; parent.mkdir()
    container = parent / ".tlo-collection-x"; container.mkdir()
    staged = container / "a"; staged.mkdir()
    victim = tmp_path / "victim.txt"; victim.write_text("keep", encoding="utf-8")
    payload = {
        "schema": 2,
        "temporary_path": str(container),
        "final_path": str(parent / "Final"),
        "generated_info": str(victim),
        "recovery_nonce": "0123456789abcdef0123456789abcdef",
        "members": [{"original": str(parent / "a"), "child_name": "a", "staged_name": "a"}],
    }
    (container / SC.JOURNAL_NAME).write_text(json.dumps(payload), encoding="utf-8")
    return root, container, victim, payload


def test_unregistered_recovery_journal_never_mutates(tmp_path):
    root, container, victim, payload = _malicious_recovery_fixture(tmp_path)
    home = tmp_path / "TLOHome"; home.mkdir()
    with pytest.raises(SC.SiblingCollectionRecoveryError):
        SC.recover_interrupted_sibling_consolidations(str(root), tlo_home=str(home))
    assert victim.read_text(encoding="utf-8") == "keep"
    assert container.exists()



def test_registered_recovery_journal_restores_member_and_consumes_registry(tmp_path):
    root = tmp_path / "root"; root.mkdir()
    parent = root / "Collection"; parent.mkdir()
    container = parent / ".tlo-collection-auth"; container.mkdir()
    staged = container / "part1"; staged.mkdir()
    home = tmp_path / "TLOHome"; home.mkdir()
    payload = {
        "schema": 2,
        "temporary_path": str(container),
        "final_path": str(parent / "Final"),
        "generated_info": "info.txt",
        "recovery_nonce": "abcdef0123456789abcdef0123456789",
        "members": [{"original": str(parent / "part1"), "child_name": "part1", "staged_name": "part1"}],
    }
    (container / SC.JOURNAL_NAME).write_text(json.dumps(payload), encoding="utf-8")
    SC._write_recovery_registry(str(home), payload)
    assert SC.recover_interrupted_sibling_consolidations(str(root), tlo_home=str(home)) == 1
    assert (parent / "part1").is_dir()
    assert not container.exists()
    assert not Path(SC._registry_path(str(home), payload["recovery_nonce"])).exists()

def test_generated_info_is_limited_to_info_txt(tmp_path):
    root, container, victim, payload = _malicious_recovery_fixture(tmp_path)
    assert not SC._validate_journal(str(container), payload)


def test_windows_delete_script_escapes_percent_and_disables_delayed_expansion(tmp_path):
    script = tmp_path / "deleteBackupFolders.bat"
    IU._append_delete_command(str(script), r"E:\boots\Band - 100% Live !wow!")
    text = script.read_text(encoding="utf-8")
    assert text.startswith("setlocal DisableDelayedExpansion\n")
    assert "100%% Live !wow!" in text


def test_oversized_text_is_rejected_before_selection_and_full_read(tmp_path):
    info = tmp_path / "info.txt"
    with open(info, "wb") as out:
        out.write(b"Artist\n2000-01-01\n")
        out.truncate(17 * 1024 * 1024)
    assert FS._is_disqualified_txt_file(str(info))
    assert TL._read_text(str(info)) == ""


def test_symlinked_setlist_skipped_and_tag_copy_refused(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    root = tmp_path / "show"; root.mkdir()
    private = tmp_path / "private.txt"; private.write_text("secret", encoding="utf-8")
    link = root / "info.txt"
    try:
        link.symlink_to(private)
    except OSError:
        pytest.skip("symlink creation not permitted")
    assert str(link) not in SC._candidate_setlists(str(root))
    with pytest.raises(TL.TaggerError):
        TL._copy_entire_directory_tree(str(root), str(tmp_path / "copy"))


def test_shn_conversion_rejects_dangling_flac_symlink(tmp_path):
    if not hasattr(os, "symlink"):
        pytest.skip("symlinks unavailable")
    source = tmp_path / "track.shn"; source.write_bytes(b"x")
    target = tmp_path / "track.flac"
    try:
        target.symlink_to(tmp_path / "outside.flac")
    except OSError:
        pytest.skip("symlink creation not permitted")
    with pytest.raises(TL.TaggerError, match="destination already exists"):
        TL.convert_shn_to_flac(str(source))


def test_issue_open_refuses_network_path_and_reveals_local_parent(tmp_path, monkeypatch):
    assert UX.open_path(r"\\attacker\share\x.txt") is False
    f = tmp_path / "issue.txt"; f.write_text("x", encoding="utf-8")
    calls = []
    monkeypatch.setattr(UX.shutil, "which", lambda name: "/bin/true")
    monkeypatch.setattr(UX.subprocess, "Popen", lambda argv, **kwargs: calls.append(argv) or SimpleNamespace())
    assert UX.open_path(str(f)) is True
    if os.name != "nt" and __import__("sys").platform != "darwin":
        assert calls[-1][-1] == str(tmp_path)


def test_bootlist_formula_escape_round_trip(tmp_path):
    rows = [{"Show": "=HYPERLINK(\"https://bad\")", "VolumePath": "[Vol] /boots/show"}]
    path = IU.write_bootlist(str(tmp_path), rows)
    raw = Path(path).read_text(encoding="utf-8")
    assert "'=HYPERLINK" in raw
    assert IU.read_bootlist(str(tmp_path))[0]["Show"].startswith("=HYPERLINK")


def test_reserved_windows_device_name_is_not_emitted_verbatim():
    assert TL.safe_compliant_folder_name("CON") != "CON"
    assert TL.safe_compliant_folder_name("LPT1.txt") != "LPT1.txt"


def test_github_host_allowlist_has_no_arbitrary_githubusercontent_suffix():
    assert GU.ALLOWED_DOWNLOAD_HOST_SUFFIXES == ()
    assert GU._download_host_allowed("https://release-assets.githubusercontent.com/file.zip")
    assert not GU._download_host_allowed("https://evil-user.githubusercontent.com/file.zip")
