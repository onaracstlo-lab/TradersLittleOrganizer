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
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

__version__ = "v334"

REPORT_VERSION = 1
PLATFORMS = ("windows", "macos", "linux", "final")
DEFAULT_TIMEOUT_SECONDS = 3600
DEFAULT_SETTLE_SECONDS = 2.0
OUTPUT_TAIL_LIMIT = 12000


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
) -> tuple[str, list[str]] | None:
    if platform_name == "windows" or (platform_name == "final" and os.name == "nt"):
        defender = locate_defender()
        if defender is None:
            return None
        return (
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
    if os.name == "nt":
        return subprocess.list2cmdline([value])
    return shlex.quote(value)


def run_scanner(
    name: str,
    command: list[str] | str,
    *,
    shell: bool,
    timeout_seconds: int,
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

    record: dict[str, object] = {
        "name": name,
        "command": display_command,
        "started_utc": started.isoformat(timespec="seconds"),
        "duration_seconds": duration,
        "return_code": completed.returncode,
        "output_tail": output[-OUTPUT_TAIL_LIMIT:],
    }

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
                shell=False,
                timeout_seconds=timeout_seconds,
            )
        )

    quoted_path = quote_for_shell(str(artifact_dir))
    for index, template in enumerate(custom_scanners, start=1):
        if not template.strip():
            raise ValueError(f"Custom scanner {index} is empty.")
        command = template.replace("{path}", quoted_path)
        scanner_records.append(
            run_scanner(
                f"Custom scanner {index}",
                command,
                shell=True,
                timeout_seconds=timeout_seconds,
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
        "artifact_root": str(artifact_dir),
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
            "Additional scanner command. Use {path} where the shell-quoted "
            "artifact directory belongs. May be repeated."
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
