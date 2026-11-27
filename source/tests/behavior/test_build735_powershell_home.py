"""Build 734 signed successfully, then its MSI smoke test collided with $HOME."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]
MSI_SCRIPT = ROOT / "msi" / "Build-TLO-MSI.ps1"
ACCEPTANCE_SCRIPT = ROOT / "tools" / "Test-TLO-Windows-Acceptance.ps1"
POWERSHELL = shutil.which("pwsh") or shutil.which("powershell")


@pytest.mark.parametrize("script", [MSI_SCRIPT, ACCEPTANCE_SCRIPT])
def test_data_home_does_not_alias_automatic_home(script):
    source = script.read_text(encoding="utf-8-sig")
    # PowerShell names are case-insensitive. Neither script needs to access
    # the user's shell home: both operate on explicit, separate data paths.
    assert not re.search(r"\$(?:\{)?(?:(?:script|global|local|private):)?HOME\b", source, re.I)


def test_native_msi_gate_keeps_install_and_uninstall_checks():
    source = MSI_SCRIPT.read_text(encoding="utf-8-sig")
    assert '$smokeTestDataHome = Join-Path $working \'native test data\'' in source
    assert "'TLODATAFOLDER=\"' + $smokeTestDataHome" in source
    assert "$configured.TrimEnd" in source
    for token in (
        "Native MSI direct-install gate passed",
        "Native MSI uninstall gate passed",
        "MSI uninstall did not remove owned database",
        "Native MSI uninstall retained the auxiliary database executable or shortcut",
        "MSI Authenticode verification failed",
    ):
        assert token in source


def _powershell(script, *args):
    assert POWERSHELL, "Native Windows acceptance requires PowerShell"
    command = [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive"]
    command += ["-ExecutionPolicy", "Bypass", "-File", str(script), *map(str, args)]
    result = subprocess.run(command, capture_output=True, text=True, errors="replace", timeout=60, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows PowerShell acceptance")
def test_msi_smoke_fixture_runs_before_signing_or_installing(tmp_path):
    # Execute the real fixture preparation statements in a fresh interpreter
    # without registry checks, WiX, signing, msiexec or application installation.
    source = MSI_SCRIPT.read_text(encoding="utf-8-sig")
    fixture = source[source.index("    $smokeTestDataHome ="):source.index("    $engine =")]
    wrapper = tmp_path / "prepare-fixture.ps1"
    wrapper.write_text(
        "param([string]$working)\n"
        "$ErrorActionPreference = 'Stop'\n"
        "Set-StrictMode -Version Latest\n"
        "$originalShellHome = $HOME\n"
        + fixture
        + "\nif ($HOME -ne $originalShellHome) { throw 'Shell HOME changed' }\n",
        encoding="utf-8",
    )
    directory = tmp_path / "fixture with spaces"
    directory.mkdir()
    _powershell(wrapper, directory)
    data = directory / "native test data"
    for name in ("artists.sqlite", "venues.txt", "cities.sqlite", "venues.sqlite"):
        assert (data / "TLO_DBs" / name).read_text(encoding="utf-8-sig").strip() == "old user-modified master"
    for name in ("bootlist.csv", "tlo-preferences.ini", "TLO_DBs/unmanaged.txt", "logs/preserve.txt", "setlists/preserve.txt"):
        assert (data / name).read_text(encoding="utf-8-sig").strip() == "preserve user data"


@pytest.mark.skipif(sys.platform != "win32", reason="Native Windows PowerShell acceptance")
def test_windows_acceptance_can_read_and_write_explicit_data_home(tmp_path):
    home = tmp_path / "diagnostic data"
    home.mkdir()
    sentinel = home / "user.txt"
    sentinel.write_text("must survive", encoding="utf-8")
    output = _powershell(ACCEPTANCE_SCRIPT, "-TLOHome", home)
    assert "PASS: TLOHome exists" in output
    assert "PASS: Standard-user TLOHome write/read" in output
    assert sentinel.read_text(encoding="utf-8") == "must survive"
    assert list(home.iterdir()) == [sentinel]
