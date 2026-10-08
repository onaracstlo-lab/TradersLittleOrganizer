from __future__ import annotations

import base64
import builtins
import importlib.util
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

import logging_lib as LL
import scan_release_artifacts as S
import tlo_github_updates as GU
import tlo_security as SEC
import tlo_tag_lib as TL
import tlo_update_trust as TRUST
import tlo_version as VERSION

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_script(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def test_build528_rsa_modulus_floor_rejects_small_key_before_modular_exponentiation(monkeypatch):
    n = (1 << 2047) + 1
    monkeypatch.setattr(TRUST, "PINNED_UPDATE_SIGNING_KEY_ID", "small")
    monkeypatch.setattr(TRUST, "PINNED_UPDATE_SIGNING_RSA_N_B64", base64.b64encode(n.to_bytes(256, "big")).decode())
    monkeypatch.setattr(TRUST, "PINNED_UPDATE_SIGNING_RSA_E_B64", base64.b64encode((65537).to_bytes(3, "big")).decode())
    monkeypatch.setattr(builtins, "pow", lambda *_a, **_k: pytest.fail("small RSA key must fail before pow()"))

    assert TRUST.MIN_RSA_MODULUS_BITS == 3072
    assert TRUST.verify_metadata_signature({"schema": 1, "key_id": "small"}, base64.b64encode(b"\0" * 256).decode()) is False


def test_build528_signed_metadata_requires_release_tag_binding(monkeypatch):
    metadata = {"schema": 1, "key_id": "test", "build": 528, "assets": []}
    metadata_asset = {"name": GU.SIGNED_METADATA_ASSET_NAME, "browser_download_url": "https://github.com/a"}
    signature_asset = {"name": GU.SIGNED_METADATA_SIGNATURE_ASSET_NAME, "browser_download_url": "https://github.com/b"}

    monkeypatch.setattr(GU, "pinned_key_configured", lambda: True)
    monkeypatch.setattr(GU, "_release_asset_by_name", lambda _release, name: metadata_asset if name == GU.SIGNED_METADATA_ASSET_NAME else signature_asset)
    monkeypatch.setattr(GU, "_fetch_small_release_asset", lambda asset, **_k: json.dumps(metadata).encode() if asset is metadata_asset else b"sig")
    monkeypatch.setattr(GU, "verify_metadata_signature", lambda _m, _s: True)

    with pytest.raises(ValueError, match="required release tag"):
        GU._load_verified_release_metadata({"tag_name": "v1.7-build528"})


def test_build528_csv_formula_escape_round_trips_existing_apostrophes():
    samples = ["=x", "+x", "-1", "@x", "'=x", "''=x", "'plain", "plain", ""]
    for value in samples:
        escaped = SEC.csv_formula_escape(value)
        assert SEC.csv_formula_unescape(escaped) == value
    assert SEC.csv_formula_escape("'=x") == "''=x"
    assert SEC.csv_formula_escape("'plain") == "''plain"


def test_build528_shn_conversion_uses_absolute_input_and_refuses_race_overwrite(tmp_path, monkeypatch):
    source = tmp_path / "track.shn"
    source.write_bytes(b"shn")
    target = tmp_path / "track.flac"
    commands = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(TL, "_bundled_ffmpeg_executable", lambda: "/app/ffmpeg")

    def fake_run(command, **_kwargs):
        commands.append(command)
        Path(command[-1]).write_bytes(b"converted")
        target.write_bytes(b"user-created-during-conversion")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(TL.subprocess, "run", fake_run)
    with pytest.raises(TL.TaggerError, match="appeared during conversion"):
        TL.convert_shn_to_flac("track.shn")

    assert commands[0][commands[0].index("-i") + 1] == str(source.resolve())
    assert target.read_bytes() == b"user-created-during-conversion"
    assert source.exists()


def test_build528_update_settings_failed_commit_leaves_previous_json_intact(tmp_path, monkeypatch):
    path = tmp_path / GU.SETTINGS_FILE_NAME
    path.write_text('{"auto_update": true}\n', encoding="utf-8")
    before = path.read_bytes()
    monkeypatch.setattr(GU.os, "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("injected")))

    with pytest.raises(OSError, match="injected"):
        GU.save_update_settings(tmp_path, {"auto_update": False})

    assert path.read_bytes() == before
    assert not list(tmp_path.glob(f".{GU.SETTINGS_FILE_NAME}.*.tmp"))


def test_build528_log_pruning_preserves_undecodable_bytes(tmp_path):
    root = tmp_path / "shows"
    root.mkdir()
    log = tmp_path / "dead0.log"
    log.write_bytes(b"NOTE: keep-\xff-byte\nPATH: " + str(root / "remove").encode() + b"\n")

    assert LL._prune_line_log(str(log), [str(root)]) is True
    data = log.read_bytes()
    assert b"\xff" in data
    assert b"remove" not in data


def test_build528_log_pruning_failed_atomic_replace_leaves_original_bytes(tmp_path, monkeypatch):
    root = tmp_path / "shows"
    root.mkdir()
    log = tmp_path / "dead0.log"
    original = b"NOTE: keep\nPATH: " + str(root / "remove").encode() + b"\n"
    log.write_bytes(original)
    monkeypatch.setattr(LL.os, "replace", lambda *_a, **_k: (_ for _ in ()).throw(OSError("injected")))

    with pytest.raises(OSError, match="injected"):
        LL._prune_line_log(str(log), [str(root)])
    assert log.read_bytes() == original


def test_build528_search_requires_real_tlohome_and_uses_central_version(monkeypatch):
    search = _load_script("tlo-search.py", "tlo_search_build528")
    monkeypatch.delenv(search.TLOHOME_ENV_VAR, raising=False)

    with pytest.raises(search.AppConfigError, match="TLOHome is required"):
        search.parse_cli_args([])
    assert search.APP_INTERNAL_VERSION == VERSION.VERSION
    assert "/mnt/c/b" not in (ROOT / "tlo-search.py").read_text(encoding="utf-8")


def test_build528_gui_opener_never_executes_rtf_as_program(tmp_path, monkeypatch):
    import tlo_ux as UX
    rtf = tmp_path / "manual.rtf"
    rtf.write_text(r"{\rtf1 test}", encoding="utf-8")
    calls = []
    monkeypatch.setattr(UX.os, "name", "nt")
    monkeypatch.setattr(UX, "windows_directory_from_api", lambda: r"C:\Windows")
    monkeypatch.setattr(UX.subprocess, "Popen", lambda argv, **_kwargs: calls.append(argv) or SimpleNamespace())
    # The live opener opens Explorer selecting the file; it does not execute its handler.
    assert UX.open_path(str(rtf)) is True
    assert calls == [[os.path.join(r"C:\Windows", "explorer.exe"), "/select,", os.path.normpath(str(rtf))]]


def test_build528_scanner_requires_approved_custom_identity_and_portable_receipt(tmp_path, monkeypatch):
    with pytest.raises(ValueError, match="APPROVED_ID::COMMAND"):
        S._parse_custom_scanner_spec("true {path}")
    with pytest.raises(ValueError, match="recognized Norton"):
        S._parse_custom_scanner_spec("norton::true {path}")
    assert S._parse_custom_scanner_spec("norton::nscan.exe /scan {path}")[0] == "norton"

    artifact = tmp_path / "private-user" / "artifacts"
    artifact.mkdir(parents=True)
    (artifact / "app.bin").write_bytes(b"app")
    report = tmp_path / "reports" / "scan.json"
    monkeypatch.setattr(
        S,
        "builtin_scanner_command",
        lambda _platform, _artifact: ("clamav", "ClamAV", [sys.executable, "-c", "raise SystemExit(0)"]),
    )
    S.scan(platform_name="linux", artifact_dir=artifact, report_path=report, custom_scanners=[], timeout_seconds=10, settle_seconds=0)
    data = json.loads(report.read_text(encoding="utf-8"))
    assert data["report_version"] == 2
    assert not os.path.isabs(data["artifact_root"])
    assert "private-user" not in data["artifact_root"]
    assert data["scanners"][0]["scanner_id"] == "clamav"


def test_build528_native_build_scripts_pin_bundle_and_collect_cli_dependencies():
    windows = (ROOT / "createWindowsDist.ps1").read_text(encoding="utf-8")
    linux = (ROOT / "createLinuxDist.sh").read_text(encoding="utf-8")
    mac = (ROOT / "createMacOSDist.sh").read_text(encoding="utf-8")

    for text in (windows, linux, mac):
        assert "BUNDLE_BUILD" in text
        assert "Bundle number mismatch" in text
        assert "TLO_PACKAGING_SMOKE_TEST" in text
    assert "$CliArgs = @('--collect-all', 'mutagen', '--add-binary', $FfmpegAddBinary)" in windows
    assert 'build_one "$(find_script tlo-gi.py)"' in linux
    assert '--add-binary "$FFMPEG_ADD_BINARY"' in linux
    assert 'build_one "$(find_script tlo-gi.py)" no' in mac
    assert '--add-binary "$FFMPEG_ADD_BINARY"' in mac
    assert "$env:USERPROFILE" in windows
    assert '"C:\\tloDist-V' not in windows
