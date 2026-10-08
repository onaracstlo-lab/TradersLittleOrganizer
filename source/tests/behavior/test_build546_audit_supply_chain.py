from pathlib import Path
from types import SimpleNamespace
import importlib.util

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_audit_module():
    spec = importlib.util.spec_from_file_location("tlo_audit_build_546", ROOT / "audit_build_requirements.py")
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build546_audit_environment_drops_caller_pip_configuration():
    audit = _load_audit_module()
    env = audit._isolated_audit_environment({
        "PATH": "/trusted/bin",
        "PIP_INDEX_URL": "https://evil.invalid/simple",
        "pip_extra_index_url": "https://also-evil.invalid/simple",
        "PIP_CONFIG_FILE": "/tmp/host-pip.conf",
        "PIP_TRUSTED_HOST": "evil.invalid",
    })
    assert env["PATH"] == "/trusted/bin"
    assert "PIP_INDEX_URL" not in env
    assert "pip_extra_index_url" not in env
    assert "PIP_CONFIG_FILE" not in env
    assert "PIP_TRUSTED_HOST" not in env
    assert env["PIP_NO_INPUT"] == "1"
    assert env["PIP_DISABLE_PIP_VERSION_CHECK"] == "1"
    assert env["PYTHONNOUSERSITE"] == "1"


def test_build546_marker_neutral_view_keeps_hashes_and_audits_platform_pins():
    audit = _load_audit_module()
    text = audit._marker_neutral_requirements_text(ROOT / "requirements-build.txt")
    assert "sys_platform" not in text
    assert "macholib==1.16.4 \\" in text
    assert "pefile==2024.8.26 \\" in text
    assert "pywin32-ctypes==0.2.3 \\" in text
    assert "colorama==0.4.6 \\" in text
    assert "--only-binary=:all:" in text
    assert text.count("--hash=sha256:") >= 20


def test_build546_audit_helper_self_audits_and_checks_all_platform_pins(monkeypatch):
    audit = _load_audit_module()
    commands = []
    audits = []

    monkeypatch.setattr(audit.venv, "EnvBuilder", lambda **_kwargs: SimpleNamespace(create=lambda _root: None))
    monkeypatch.setattr(audit, "_venv_python", lambda _root: Path("/fake/python"))
    monkeypatch.setattr(
        audit,
        "_installed_version",
        lambda _python, distribution, **_kwargs: (
            audit.EXPECTED_BOOTSTRAP_PIP_VERSION if distribution == "pip" else audit.PIP_AUDIT_VERSION
        ),
    )
    monkeypatch.setattr(audit, "_run_checked", lambda command, **kwargs: commands.append((list(command), kwargs)) or SimpleNamespace(stdout=""))

    def record_audit(_python, requirements, *, env):
        path = Path(requirements)
        audits.append((path.name, path.read_text(encoding="utf-8"), dict(env)))

    monkeypatch.setattr(audit, "_run_pip_audit", record_audit)
    assert audit.main([str(ROOT / "requirements-build.txt")]) == 0

    assert [name for name, _text, _env in audits] == [
        "requirements-audit.txt",
        "requirements-build.txt",
        "requirements-all-platforms.txt",
    ]
    all_platforms = audits[-1][1]
    assert "sys_platform" not in all_platforms
    for package in ("macholib==1.16.4", "pefile==2024.8.26", "pywin32-ctypes==0.2.3", "colorama==0.4.6"):
        assert package in all_platforms

    pip_commands = [command for command, _kwargs in commands if command[:3] == ["/fake/python", "-m", "pip"]]
    assert any(command[3:5] == ["--isolated", "install"] for command in pip_commands)
    assert any(command[3:5] == ["--isolated", "check"] for command in pip_commands)


def assert_windows_signing_security_contract(text: str) -> None:
    """Validate common security invariants of the source and CI-generated scripts.

    The GitHub Build Process regenerates createWindowsDist.ps1 rather than
    running the source copy unchanged. Both implementations must reject PATH
    resolution and untrusted SignTool signatures, and verify every signed EXE
    before running malware scans. Do not require an obsolete local variable
    name or telemetry wording to satisfy a signing-security contract.
    """
    assert "Get-Command signtool.exe" not in text
    assert "Windows Kits\\10\\bin" in text
    assert "\\\\x64\\\\signtool\\.exe$" in text
    assert "[System.Management.Automation.SignatureStatus]::Valid" in text
    assert "Signer -notmatch '(?i)Microsoft'" in text

    # The source implementation uses a SignTool FileInfo object; the
    # CI-generated implementation validates its resolved absolute path.
    if "function Get-TrustedWindowsSignTool" in text:
        assert "Get-AuthenticodeSignature -LiteralPath $SignTool.FullName" in text
        assert "Get-FileHash -LiteralPath $SignTool.FullName -Algorithm SHA256" in text
        assert "[Diagnostics.FileVersionInfo]::GetVersionInfo($SignTool.FullName)" in text
        assert "SignTool sha256" in text and "SignTool signer" in text
        assert "& $SignToolPath verify /pa /all /v $_.FullName" in text
    else:
        # The generator validates both configured and Windows Kits fallbacks.
        assert "function Assert-TloTrustedSignTool" in text
        assert "Get-AuthenticodeSignature -LiteralPath $Path" in text
        assert "Get-FileHash -LiteralPath $Path -Algorithm SHA256" in text
        assert text.count("Assert-TloTrustedSignTool -Path $CandidatePath") >= 2
        assert "Verified Microsoft-signed x64 SignTool sha256=" in text
        assert "& $SignToolPath verify /pa /all /v $Exe.FullName" in text
        assert "if ($VerifyExitCode -ne 0)" in text

    # Signing, successful same-file verification and scanning are ordered.
    sign_at = text.find("& $SignToolPath sign")
    verify_at = text.find("& $SignToolPath verify /pa /all /v")
    scan_at = text.find("Invoke-WindowsArtifactScan -ArtifactDir")
    if scan_at < 0:
        scan_at = text.find("Invoke-Python -Runner $PythonRunner -Arguments $ScanArguments")
    assert 0 <= sign_at < verify_at < scan_at
    assert "/tr http://timestamp." in text


def test_build546_local_windows_signing_uses_trusted_windows_kits_signtool():
    assert_windows_signing_security_contract(
        (ROOT / "createWindowsDist.ps1").read_text(encoding="utf-8")
    )


def test_build570_signing_contract_rejects_removed_security_guards():
    original = (ROOT / "createWindowsDist.ps1").read_text(encoding="utf-8")
    sign_tool_ref = "$SignTool.FullName" if "function Get-TrustedWindowsSignTool" in original else "$Path"
    signed_exe_ref = "$_.FullName" if "function Get-TrustedWindowsSignTool" in original else "$Exe.FullName"
    unsafe_changes = (
        (f"Get-AuthenticodeSignature -LiteralPath {sign_tool_ref}", "Get-Command signtool.exe"),
        ("SignatureStatus]::Valid", "SignatureStatus]::Unknown"),
        ("Signer -notmatch '(?i)Microsoft'", "Signer -match '(?i)Microsoft'"),
        (f"& $SignToolPath verify /pa /all /v {signed_exe_ref}", "# verification disabled"),
    )
    for before, after in unsafe_changes:
        assert before in original
        with pytest.raises(AssertionError):
            assert_windows_signing_security_contract(original.replace(before, after))


def test_build546_audit_source_invokes_strict_self_and_marker_neutral_audits():
    text = (ROOT / "audit_build_requirements.py").read_text(encoding="utf-8")
    assert '"pip", "--isolated", "install"' in text
    assert '"pip", "--isolated", "check"' in text
    assert "_run_pip_audit(python, AUDIT_REQUIREMENTS" in text
    assert "_marker_neutral_requirements_text(requirements)" in text
    assert '"--require-hashes", "--no-deps", "--disable-pip", "--strict"' in text
