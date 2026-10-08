#!/usr/bin/env python3
"""Scan TLO release artifacts and write a hash-bound clean-scan receipt.

The utility is intended for native build machines and the final packaging job.
It fails closed: a clean receipt is written only when at least one configured
scanner completes successfully, every configured scanner returns success, and
the artifact bytes remain unchanged throughout scanning.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

REPORT_VERSION = 2
PLATFORMS = ("windows", "macos", "linux", "final")
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_SETTLE_SECONDS = 2.0
OUTPUT_TAIL_LIMIT = 12000
APPROVED_SCANNER_IDS = {"microsoft-defender", "clamav", "norton"}
CUSTOM_SCANNER_IDS = {"norton"}
NORTON_EXECUTABLE_NAMES = {"nscan.exe", "navw32.exe", "nortonsecurity.exe", "norton.exe"}
NORTON_SIGNER_FRAGMENTS = ("norton", "gen digital", "symantec")


@dataclass(frozen=True)
class FileState:
    path: str
    size: int
    sha256: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def iter_artifacts(root: Path, excluded_paths: Iterable[Path] = ()) -> list[Path]:
    excluded = {path.resolve(strict=False) for path in excluded_paths}
    files: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.resolve(strict=False) in excluded:
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(root).as_posix().casefold())


def snapshot(root: Path, excluded_paths: Iterable[Path] = ()) -> dict[str, FileState]:
    result: dict[str, FileState] = {}
    for path in iter_artifacts(root, excluded_paths):
        relative = path.relative_to(root).as_posix()
        stat_result = path.stat()
        result[relative] = FileState(
            path=relative,
            size=stat_result.st_size,
            sha256=sha256_file(path),
        )
    return result


def describe_snapshot_change(
    before: dict[str, FileState],
    after: dict[str, FileState],
) -> str:
    before_names = set(before)
    after_names = set(after)
    missing = sorted(before_names - after_names)
    added = sorted(after_names - before_names)
    changed = sorted(
        name
        for name in before_names & after_names
        if before[name].size != after[name].size
        or before[name].sha256 != after[name].sha256
    )
    return f"missing={missing}; added={added}; changed={changed}"


def locate_defender() -> Path | None:
    candidates: list[Path] = []

    program_data = os.environ.get("ProgramData")
    if program_data:
        platform_root = Path(program_data) / "Microsoft" / "Windows Defender" / "Platform"
        if platform_root.is_dir():
            candidates.extend(
                sorted(
                    platform_root.glob("*/MpCmdRun.exe"),
                    key=lambda path: path.parent.name,
                    reverse=True,
                )
            )

    program_files = os.environ.get("ProgramFiles")
    if program_files:
        candidates.append(Path(program_files) / "Windows Defender" / "MpCmdRun.exe")

    command = shutil.which("MpCmdRun.exe") or shutil.which("MpCmdRun")
    if command:
        candidates.insert(0, Path(command))

    return next((candidate for candidate in candidates if candidate.is_file()), None)


def builtin_scanner_command(
    platform_name: str,
    artifact_dir: Path,
) -> tuple[str, str, list[str]] | None:
    if platform_name == "windows" or (platform_name == "final" and os.name == "nt"):
        defender = locate_defender()
        if defender is None:
            return None
        return (
            "microsoft-defender",
            "Microsoft Defender",
            [
                str(defender),
                "-Scan",
                "-ScanType",
                "3",
                "-File",
                str(artifact_dir),
                "-DisableRemediation",
            ],
        )

    clamscan = shutil.which("clamscan")
    if clamscan:
        return (
            "clamav",
            "ClamAV",
            [
                clamscan,
                "--recursive=yes",
                "--infected",
                "--no-summary",
                str(artifact_dir),
            ],
        )

    return None


def quote_for_shell(value: str) -> str:
    """Quote a value for a POSIX shell command string.

    Windows custom scanner paths are not interpolated into cmd.exe text; they
    are supplied through an environment variable by _custom_scanner_command.
    """
    return shlex.quote(value)


def _custom_scanner_command(template: str, artifact_dir: Path, *, windows: bool | None = None):
    """Legacy command materializer retained for the Build 404 injection contract.

    Build 550 custom Norton execution no longer uses this shell-oriented helper;
    it resolves the executable and executes argv directly through
    _prepare_custom_scanner().
    """
    use_windows = os.name == "nt" if windows is None else bool(windows)
    if use_windows:
        env = os.environ.copy()
        env["TLO_SCAN_ARTIFACT_PATH"] = str(artifact_dir)
        return template.replace("{path}", '"%TLO_SCAN_ARTIFACT_PATH%"'), env
    return template.replace("{path}", quote_for_shell(str(artifact_dir))), None


def _parse_custom_scanner_spec(spec: str) -> tuple[str, str]:
    """Return an approved scanner identity and command template."""
    identity, separator, template = str(spec or "").partition("::")
    identity = identity.strip().casefold()
    template = template.strip()
    if not separator or not identity or not template:
        raise ValueError("Custom scanners must use APPROVED_ID::COMMAND syntax.")
    if identity not in CUSTOM_SCANNER_IDS:
        raise ValueError(f"Custom scanner identity is not approved for official TLO receipts: {identity or '<blank>'}")
    argv = _split_custom_scanner_template(template)
    invoked_name = re.split(r"[\\/]", argv[0])[-1].casefold()
    if identity == "norton" and invoked_name not in NORTON_EXECUTABLE_NAMES:
        raise ValueError("The Norton scanner command must invoke a recognized Norton scanner executable first.")
    return identity, template


def _split_custom_scanner_template(template: str, *, windows: bool | None = None) -> list[str]:
    """Split a custom scanner template into argv without invoking a shell."""
    use_windows = os.name == "nt" if windows is None else bool(windows)
    try:
        parts = shlex.split(template, posix=not use_windows)
    except ValueError as exc:
        raise ValueError(f"Invalid custom scanner command: {exc}") from exc
    cleaned = [part[1:-1] if use_windows and len(part) >= 2 and part[0] == part[-1] == '"' else part for part in parts]
    if not cleaned:
        raise ValueError("Custom scanner command is empty.")
    if "{path}" not in cleaned:
        raise ValueError("Custom scanner command must contain {path} as its own argument.")
    if any("{path}" in part and part != "{path}" for part in cleaned):
        raise ValueError("Custom scanner {path} placeholder must be a separate argument.")
    return cleaned


def _resolve_executable(token: str) -> Path:
    expanded = os.path.expandvars(os.path.expanduser(token))
    candidate = Path(expanded)
    if candidate.parent != Path(".") or candidate.is_absolute():
        resolved = candidate.resolve(strict=False)
        if not resolved.is_file():
            raise ValueError(f"Custom scanner executable not found: {token}")
        return resolved
    located = shutil.which(expanded)
    if not located:
        raise ValueError(f"Custom scanner executable not found on PATH: {token}")
    return Path(located).resolve()


def _norton_trusted_install_root(path: Path) -> bool:
    """Require Norton to resolve under a standard Program Files tree on Windows."""
    if os.name != "nt":
        return True
    roots = []
    for name in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        value = os.environ.get(name)
        if value:
            roots.append(Path(value).resolve(strict=False))
    return any(_is_relative_to(path, root) for root in roots)


def _windows_authenticode_identity(path: Path) -> dict[str, object]:
    """Return Authenticode status and signer identity for a Windows executable."""
    if os.name != "nt":
        return {"status": "not-applicable", "signer_subject": None}
    powershell = shutil.which("powershell.exe") or shutil.which("powershell")
    if not powershell:
        raise RuntimeError("PowerShell is required to validate the Norton Authenticode signature.")
    script = (
        "$s=Get-AuthenticodeSignature -LiteralPath $args[0];"
        "$o=[pscustomobject]@{Status=$s.Status.ToString();Subject=if($s.SignerCertificate){$s.SignerCertificate.Subject}else{$null}};"
        "$o|ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            [powershell, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script, str(path)],
            shell=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"Could not validate Norton Authenticode signature: {exc}") from exc
    if completed.returncode != 0:
        raise RuntimeError(f"Could not validate Norton Authenticode signature: {completed.stderr[-2000:]}")
    try:
        payload = json.loads(completed.stdout.strip())
    except json.JSONDecodeError as exc:
        raise RuntimeError("PowerShell returned invalid Authenticode status data.") from exc
    status = str(payload.get("Status") or "")
    subject = payload.get("Subject")
    if status.casefold() != "valid":
        raise ValueError(f"Norton executable does not have a valid Authenticode signature: {status or 'unknown'}")
    if not subject or not any(fragment in str(subject).casefold() for fragment in NORTON_SIGNER_FRAGMENTS):
        raise ValueError(f"Norton executable signer is not recognized as an approved Norton signer: {subject or '<missing>'}")
    return {"status": status, "signer_subject": str(subject)}


def _prepare_custom_scanner(
    scanner_id: str,
    template: str,
    artifact_dir: Path,
) -> tuple[list[str], dict[str, object]]:
    """Resolve, validate and materialize a custom scanner command."""
    argv = _split_custom_scanner_template(template)
    executable = _resolve_executable(argv[0])
    if scanner_id == "norton":
        if executable.name.casefold() not in NORTON_EXECUTABLE_NAMES:
            raise ValueError(
                "The executable actually invoked for a Norton receipt must be a recognized Norton scanner executable."
            )
        if not _norton_trusted_install_root(executable):
            raise ValueError("Norton executable must resolve inside a standard Program Files directory.")
        authenticode = _windows_authenticode_identity(executable)
    else:
        raise ValueError(f"Unsupported custom scanner identity: {scanner_id}")

    command = [str(executable)] + [str(artifact_dir) if part == "{path}" else part for part in argv[1:]]
    identity = {
        "executable_path": str(executable),
        "executable_sha256": sha256_file(executable),
        "authenticode_status": authenticode["status"],
        "authenticode_signer_subject": authenticode["signer_subject"],
    }
    return command, identity


def run_scanner(
    scanner_id: str,
    name: str,
    command: list[str] | str,
    *,
    shell: bool,
    timeout_seconds: int,
    env: dict[str, str] | None = None,
    scanner_identity: dict[str, object] | None = None,
) -> dict[str, object]:
    started = dt.datetime.now(dt.timezone.utc)
    started_monotonic = time.monotonic()

    try:
        completed = subprocess.run(
            command,
            shell=shell,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout_seconds,
            check=False,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        captured = exc.stdout or ""
        if isinstance(captured, bytes):
            captured = captured.decode(errors="replace")
        raise RuntimeError(
            f"{name} exceeded the {timeout_seconds}-second timeout.\n"
            f"{captured[-4000:]}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start {name}: {exc}") from exc

    duration = round(time.monotonic() - started_monotonic, 3)
    output = completed.stdout or ""
    display_command = command if isinstance(command, str) else shlex.join(command)

    if scanner_id not in APPROVED_SCANNER_IDS:
        raise ValueError(f"Scanner identity is not approved: {scanner_id}")
    record: dict[str, object] = {
        "scanner_id": scanner_id,
        "name": name,
        "command": display_command,
        "started_utc": started.isoformat(timespec="seconds"),
        "duration_seconds": duration,
        "return_code": completed.returncode,
        "output_tail": output[-OUTPUT_TAIL_LIMIT:],
    }
    if scanner_identity:
        record.update(scanner_identity)

    if completed.returncode != 0:
        raise RuntimeError(
            f"{name} did not return a clean result "
            f"(exit {completed.returncode}).\n{output[-4000:]}"
        )

    return record


def write_json_atomic(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            json.dump(data, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)


def scan(
    *,
    platform_name: str,
    artifact_dir: Path,
    report_path: Path,
    custom_scanners: Sequence[str],
    timeout_seconds: int,
    settle_seconds: float,
) -> None:
    artifact_dir = artifact_dir.expanduser().resolve()
    report_path = report_path.expanduser().resolve(strict=False)

    if not artifact_dir.is_dir():
        raise ValueError(f"Artifact directory not found: {artifact_dir}")
    if timeout_seconds < 1:
        raise ValueError("Scanner timeout must be at least one second.")
    if settle_seconds < 0:
        raise ValueError("Settle time cannot be negative.")

    # Never allow a stale clean receipt to survive a failed rescan.
    report_path.unlink(missing_ok=True)

    excluded_paths: set[Path] = set()
    if _is_relative_to(report_path, artifact_dir):
        excluded_paths.add(report_path)

    before = snapshot(artifact_dir, excluded_paths)
    if not before:
        raise ValueError(f"No artifacts found under: {artifact_dir}")

    scanner_records: list[dict[str, object]] = []

    builtin = builtin_scanner_command(platform_name, artifact_dir)
    if builtin is not None:
        scanner_records.append(
            run_scanner(
                builtin[0],
                builtin[1],
                builtin[2],
                shell=False,
                timeout_seconds=timeout_seconds,
            )
        )

    for index, scanner_spec in enumerate(custom_scanners, start=1):
        scanner_id, template = _parse_custom_scanner_spec(scanner_spec)
        command, scanner_identity = _prepare_custom_scanner(scanner_id, template, artifact_dir)
        scanner_records.append(
            run_scanner(
                scanner_id,
                f"Norton scanner {index}",
                command,
                shell=False,
                timeout_seconds=timeout_seconds,
                scanner_identity=scanner_identity,
            )
        )

    if not scanner_records:
        raise RuntimeError(
            "No supported malware scanner was found. Enable Microsoft Defender "
            "on Windows, install ClamAV/clamscan on macOS or Linux, or supply "
            "one or more --custom-scanner commands."
        )

    if settle_seconds:
        time.sleep(settle_seconds)

    after = snapshot(artifact_dir, excluded_paths)
    if before != after:
        raise RuntimeError(
            "Artifacts changed during or immediately after scanning: "
            + describe_snapshot_change(before, after)
        )

    report: dict[str, object] = {
        "report_version": REPORT_VERSION,
        "status": "clean",
        "platform": platform_name,
        "artifact_root": artifact_dir.name,
        "generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "scanner_timeout_seconds": timeout_seconds,
        "post_scan_settle_seconds": settle_seconds,
        "scanners": scanner_records,
        "files": [
            {
                "path": state.path,
                "size": state.size,
                "sha256": state.sha256,
            }
            for state in after.values()
        ],
    }

    write_json_atomic(report_path, report)
    print(f"Clean scan receipt written: {report_path}")


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", required=True, choices=PLATFORMS)
    parser.add_argument("--artifact-dir", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument(
        "--custom-scanner",
        action="append",
        default=[],
        help=(
            "Approved custom scanner in APPROVED_ID::COMMAND form. Only Norton is accepted "
            "as a custom identity; use {path} where the artifact directory belongs. May be repeated."
        ),
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"Maximum time allowed for each scanner (default: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=DEFAULT_SETTLE_SECONDS,
        help=(
            "Seconds to wait after scanners finish before re-hashing artifacts "
            f"(default: {DEFAULT_SETTLE_SECONDS})."
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        scan(
            platform_name=args.platform,
            artifact_dir=Path(args.artifact_dir),
            report_path=Path(args.report),
            custom_scanners=args.custom_scanner,
            timeout_seconds=args.timeout_seconds,
            settle_seconds=args.settle_seconds,
        )
    except Exception as exc:  # noqa: BLE001 - build gate must report all failures
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
