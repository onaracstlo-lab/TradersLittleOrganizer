"""Build 550: Norton custom-scanner receipt identity hardening."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

import scan_release_artifacts as S

pytestmark = pytest.mark.behavior


def _make_fake_norton(path: Path) -> None:
    path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    path.chmod(path.stat().st_mode | 0o111)


def test_build550_rejects_token_only_norton_claim():
    with pytest.raises(ValueError, match="invoke a recognized Norton scanner executable first"):
        S._parse_custom_scanner_spec("norton::true norton.exe {path}")


def test_build550_resolves_actual_norton_executable_and_hash(tmp_path, monkeypatch):
    executable = tmp_path / "nscan.exe"
    _make_fake_norton(executable)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()

    monkeypatch.setattr(S.shutil, "which", lambda name: str(executable) if name == "nscan.exe" else None)
    monkeypatch.setattr(S, "_norton_trusted_install_root", lambda _path: True)
    monkeypatch.setattr(
        S,
        "_windows_authenticode_identity",
        lambda _path: {"status": "Valid", "signer_subject": "CN=NortonLifeLock Inc."},
    )

    scanner_id, template = S._parse_custom_scanner_spec("norton::nscan.exe /scan {path}")
    command, identity = S._prepare_custom_scanner(scanner_id, template, artifact_dir)

    assert command == [str(executable.resolve()), "/scan", str(artifact_dir)]
    assert identity["executable_path"] == str(executable.resolve())
    assert identity["executable_sha256"] == hashlib.sha256(executable.read_bytes()).hexdigest()
    assert identity["authenticode_status"] == "Valid"
    assert "Norton" in identity["authenticode_signer_subject"]


def test_build550_custom_scanner_executes_without_shell_and_receipt_binds_identity(tmp_path, monkeypatch):
    executable = tmp_path / "nscan.exe"
    _make_fake_norton(executable)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    (artifact_dir / "payload.bin").write_bytes(b"payload")
    report = tmp_path / "scan.json"

    monkeypatch.setattr(S, "builtin_scanner_command", lambda *_args: None)
    monkeypatch.setattr(S.shutil, "which", lambda name: str(executable) if name == "nscan.exe" else None)
    monkeypatch.setattr(S, "_norton_trusted_install_root", lambda _path: True)
    monkeypatch.setattr(
        S,
        "_windows_authenticode_identity",
        lambda _path: {"status": "Valid", "signer_subject": "CN=NortonLifeLock Inc."},
    )

    seen = {}
    real_run = S.subprocess.run

    def recording_run(command, **kwargs):
        seen["command"] = command
        seen["shell"] = kwargs.get("shell")
        return real_run(command, **kwargs)

    monkeypatch.setattr(S.subprocess, "run", recording_run)
    S.scan(
        platform_name="final",
        artifact_dir=artifact_dir,
        report_path=report,
        custom_scanners=["norton::nscan.exe {path}"],
        timeout_seconds=10,
        settle_seconds=0,
    )

    assert seen["shell"] is False
    assert isinstance(seen["command"], list)
    assert seen["command"][0] == str(executable.resolve())

    data = json.loads(report.read_text(encoding="utf-8"))
    scanner = data["scanners"][0]
    assert data["report_version"] == 2
    assert scanner["scanner_id"] == "norton"
    assert scanner["executable_path"] == str(executable.resolve())
    assert scanner["executable_sha256"] == hashlib.sha256(executable.read_bytes()).hexdigest()
    assert scanner["authenticode_status"] == "Valid"
    assert scanner["authenticode_signer_subject"] == "CN=NortonLifeLock Inc."


def test_build550_rejects_wrong_resolved_basename_even_if_template_is_approved(tmp_path, monkeypatch):
    imposter = tmp_path / "true"
    _make_fake_norton(imposter)
    monkeypatch.setattr(S.shutil, "which", lambda _name: str(imposter))

    with pytest.raises(ValueError, match="actually invoked"):
        S._prepare_custom_scanner("norton", "nscan.exe {path}", tmp_path)
