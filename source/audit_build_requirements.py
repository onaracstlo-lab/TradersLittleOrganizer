"""Run pip-audit 2.10.1 from TLO's hash-locked audit tool environment."""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import argparse
import os
import subprocess
import tempfile
import venv
from pathlib import Path

PIP_AUDIT_VERSION = "2.10.1"
EXPECTED_BOOTSTRAP_PIP_VERSION = "26.2.1"
AUDIT_REQUIREMENTS = Path(__file__).with_name("requirements-audit.txt")


def _venv_python(root: Path) -> Path:
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def _run_checked(command, *, env, capture_output=False):
    return subprocess.run(command, check=True, env=env, text=True, capture_output=capture_output)


def _installed_version(python: Path, distribution: str, *, env: dict[str, str]) -> str:
    code = "from importlib.metadata import version; " + f"print(version({distribution!r}))"
    return _run_checked([str(python), "-c", code], env=env, capture_output=True).stdout.strip()


def _isolated_audit_environment(source: dict[str, str] | None = None) -> dict[str, str]:
    """Return a subprocess environment that cannot inherit caller pip configuration."""
    original = os.environ if source is None else source
    env = {key: value for key, value in original.items() if not key.upper().startswith("PIP_")}
    env["PIP_NO_INPUT"] = "1"
    env["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _marker_neutral_requirements_text(path: Path) -> str:
    """Remove environment markers from exact pins while preserving hashes/options.

    pip-audit evaluates PEP 508 markers for the host platform.  The normal audit still
    runs against the original lock.  A second audit uses this marker-neutral view so
    Windows/macOS-only exact pins are also checked when the audit runs on Linux.
    """
    output: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        stripped = raw.lstrip()
        if stripped and not stripped.startswith("#") and "==" in stripped and ";" in raw:
            before_marker = raw.split(";", 1)[0].rstrip()
            if raw.rstrip().endswith("\\"):
                before_marker += " \\"
            output.append(before_marker)
        else:
            output.append(raw)
    return "\n".join(output) + "\n"


def _run_pip_audit(python: Path, requirements: Path, *, env: dict[str, str]) -> None:
    _run_checked([
        str(python), "-m", "pip_audit", "-r", str(requirements),
        "--require-hashes", "--no-deps", "--disable-pip", "--strict",
    ], env=env)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements", nargs="?", default="requirements-build.txt")
    args = parser.parse_args(argv)
    requirements = Path(args.requirements).resolve()
    if not requirements.is_file():
        raise SystemExit(f"Requirements file not found: {requirements}")
    if not AUDIT_REQUIREMENTS.is_file():
        raise SystemExit(f"Audit tool lock not found: {AUDIT_REQUIREMENTS}")

    audit_env = _isolated_audit_environment()
    with tempfile.TemporaryDirectory(prefix="tlo-pip-audit-") as tmp:
        root = Path(tmp)
        venv.EnvBuilder(with_pip=True, clear=True).create(root)
        python = _venv_python(root)
        bootstrap_pip = _installed_version(python, "pip", env=audit_env)
        if bootstrap_pip != EXPECTED_BOOTSTRAP_PIP_VERSION:
            raise SystemExit(f"Unexpected CPython ensurepip bootstrap: pip {bootstrap_pip!r}; expected {EXPECTED_BOOTSTRAP_PIP_VERSION!r}.")
        _run_checked([
            str(python), "-m", "pip", "--isolated", "install", "--disable-pip-version-check",
            "--no-deps", "--require-hashes", "--only-binary=:all:", "-r", str(AUDIT_REQUIREMENTS),
        ], env=audit_env)
        _run_checked([str(python), "-m", "pip", "--isolated", "check"], env=audit_env)
        installed_audit = _installed_version(python, "pip-audit", env=audit_env)
        if installed_audit != PIP_AUDIT_VERSION:
            raise SystemExit(f"Unexpected pip-audit version {installed_audit!r}; expected {PIP_AUDIT_VERSION!r}.")

        # Audit the audit toolchain itself before trusting it to approve the build lock.
        _run_pip_audit(python, AUDIT_REQUIREMENTS, env=audit_env)

        # Audit the caller-supplied lock in its normal host-platform interpretation.
        _run_pip_audit(python, requirements, env=audit_env)

        # Also audit an exact marker-neutral view so platform-gated Windows/macOS pins
        # are checked even when this helper runs on a different operating system.
        all_platforms = root / "requirements-all-platforms.txt"
        all_platforms.write_text(_marker_neutral_requirements_text(requirements), encoding="utf-8")
        _run_pip_audit(python, all_platforms, env=audit_env)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
