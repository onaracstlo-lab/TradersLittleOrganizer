"""Fetch and verify the exact ffmpeg binary used by TLO native builds.

The ffmpeg executable is intentionally not stored in the source bundle. Native
builders download one versioned release asset, verify its pinned SHA-256, safely
extract only the ffmpeg executable, and stage it beneath ``tlo_ffmpeg_bin``.
"""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION


import argparse
import hashlib
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

FFMPEG_VERSION = "9.0.2"
MAX_DOWNLOAD_BYTES = 512 * 1024 * 1024
PROVIDER_RELEASE = f"https://github.com/boul2gom/ffmpeg-builds/releases/download/v{FFMPEG_VERSION}"

# Exact release assets and checksums published with boul2gom/ffmpeg-builds v9.0.2.
ASSETS: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "x64"): ("ffmpeg-linux-x64.zip", "4e7dfefc28a0b49472b60564de82743a2cca8ff1463c470efc0248cfbe16189a"),
    ("linux", "arm64"): ("ffmpeg-linux-arm64.zip", "d384e79ddc4070c2bfa041685166420f720e842c4c2c6a9edb3578a46a485d07"),
    ("linux", "x86"): ("ffmpeg-linux-x86.zip", "567b468ce66a4b88d63aa97a5d91375147d44bcd0c6f7dae8a8cd57f769a55d7"),
    ("macos", "x64"): ("ffmpeg-osx-x64.zip", "91ec334ef9b6b7099d7f0b0c38a615259fb8f5cb7ad5207c1173cdb066c5fbc9"),
    ("macos", "arm64"): ("ffmpeg-osx-arm64.zip", "7c56b517931d52be68d1e27dff0069b24fbe2b3172a743c7034117c8bed8bdbd"),
    ("windows", "x64"): ("ffmpeg-windows-x64.zip", "26b26a874a77474afc18fabafb28faa055dce4306d4bd2cb5096a66a9ac15be8"),
    ("windows", "arm64"): ("ffmpeg-windows-arm64.zip", "2150d9cae4b63f70c6d4d55068a8aecafbf33b3f9e4da673d25d61d85d61ecb2"),
    ("windows", "x86"): ("ffmpeg-windows-x86.zip", "38fcf0b967bfe754d9b7e11cbcce8311705078e124c552a23953538a60e4c684"),
}


def _normalize_platform(value: str | None = None) -> str:
    raw = (value or sys.platform).lower()
    if raw.startswith("linux"):
        return "linux"
    if raw.startswith("darwin") or raw in {"mac", "macos", "osx"}:
        return "macos"
    if raw.startswith("win") or raw == "windows":
        return "windows"
    raise RuntimeError(f"Unsupported ffmpeg build platform: {raw}")


def _normalize_arch(value: str | None = None) -> str:
    raw = (value or platform.machine()).lower().replace("-", "_")
    aliases = {
        "amd64": "x64",
        "x86_64": "x64",
        "x64": "x64",
        "aarch64": "arm64",
        "arm64": "arm64",
        "i386": "x86",
        "i686": "x86",
        "x86": "x86",
        "universal2": "universal2",
    }
    if raw not in aliases:
        raise RuntimeError(f"Unsupported ffmpeg build architecture: {raw}")
    return aliases[raw]


def _download(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": f"TLO-build/{__version__.removeprefix('v')}"})
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = destination.with_name(destination.name + ".tmp")
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temp.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_DOWNLOAD_BYTES:
                    raise RuntimeError(f"ffmpeg download exceeded {MAX_DOWNLOAD_BYTES} bytes")
                handle.write(chunk)
        os.replace(temp, destination)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_member_name(name: str) -> PurePosixPath:
    if "\x00" in name:
        raise RuntimeError("ffmpeg archive contains a NUL in a member name")
    normalized = name.replace("\\", "/")
    member = PurePosixPath(normalized)
    if member.is_absolute() or any(part in {"", ".", ".."} for part in member.parts):
        raise RuntimeError(f"unsafe ffmpeg archive member: {name!r}")
    if member.parts and ":" in member.parts[0]:
        raise RuntimeError(f"unsafe ffmpeg archive member: {name!r}")
    return member


def _extract_ffmpeg(archive: Path, destination: Path, *, windows: bool) -> None:
    wanted = "ffmpeg.exe" if windows else "ffmpeg"
    matches: list[zipfile.ZipInfo] = []
    with zipfile.ZipFile(archive, "r") as zf:
        for info in zf.infolist():
            member = _safe_member_name(info.filename)
            file_type = (info.external_attr >> 16) & 0o170000
            if file_type == stat.S_IFLNK:
                raise RuntimeError(f"ffmpeg archive contains a symlink: {info.filename}")
            if not info.is_dir() and member.name.lower() == wanted.lower():
                matches.append(info)
        if len(matches) != 1:
            raise RuntimeError(f"expected exactly one {wanted} in ffmpeg archive; found {len(matches)}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temp = destination.with_name(destination.name + ".tmp")
        try:
            with zf.open(matches[0], "r") as source, temp.open("wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
            if not windows:
                temp.chmod(temp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            os.replace(temp, destination)
        finally:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass


def _prepare_single(target_platform: str, arch: str, output: Path, cache_dir: Path) -> None:
    try:
        asset_name, expected = ASSETS[(target_platform, arch)]
    except KeyError as exc:
        raise RuntimeError(f"No pinned ffmpeg asset for {target_platform}/{arch}") from exc
    archive = cache_dir / asset_name
    if not archive.exists():
        _download(f"{PROVIDER_RELEASE}/{asset_name}", archive)
    actual = _sha256(archive)
    if actual.lower() != expected.lower():
        raise RuntimeError(f"ffmpeg checksum mismatch for {asset_name}: expected {expected}, found {actual}")
    _extract_ffmpeg(archive, output, windows=(target_platform == "windows"))


def _verify_version(executable: Path) -> str:
    completed = subprocess.run(
        [str(executable), "-version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    first_line = (completed.stdout or "").splitlines()[0] if (completed.stdout or "").splitlines() else ""
    if completed.returncode != 0 or f"ffmpeg version {FFMPEG_VERSION}" not in first_line.lower():
        raise RuntimeError(f"prepared ffmpeg did not report version {FFMPEG_VERSION}: {first_line!r}")
    return first_line.strip()


def prepare(output_dir: Path, *, target_platform: str, arch: str, cache_dir: Path) -> tuple[Path, str]:
    output_dir = output_dir.resolve()
    cache_dir = cache_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)
    basename = "ffmpeg.exe" if target_platform == "windows" else "ffmpeg"
    destination = output_dir / basename

    if target_platform == "macos" and arch == "universal2":
        if shutil.which("lipo") is None:
            raise RuntimeError("macOS universal2 ffmpeg preparation requires lipo")
        with tempfile.TemporaryDirectory(prefix="tlo-ffmpeg-") as temp_dir:
            temp_root = Path(temp_dir)
            x64 = temp_root / "ffmpeg-x64"
            arm64 = temp_root / "ffmpeg-arm64"
            _prepare_single("macos", "x64", x64, cache_dir)
            _prepare_single("macos", "arm64", arm64, cache_dir)
            subprocess.run(["lipo", "-create", str(x64), str(arm64), "-output", str(destination)], check=True)
            destination.chmod(destination.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    else:
        _prepare_single(target_platform, arch, destination, cache_dir)

    version_line = _verify_version(destination)
    return destination, version_line


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, help="Directory that will contain ffmpeg[.exe]")
    parser.add_argument("--cache-dir", default="", help="Optional cache directory for verified release ZIPs")
    parser.add_argument("--platform", dest="target_platform", default="", help="linux, macos, or windows")
    parser.add_argument("--arch", default="", help="x64, arm64, x86, or macOS universal2")
    args = parser.parse_args(argv)

    target_platform = _normalize_platform(args.target_platform or None)
    arch = _normalize_arch(args.arch or None)
    if arch == "universal2" and target_platform != "macos":
        raise RuntimeError("universal2 is only valid for macOS")
    output_dir = Path(args.output_dir)
    cache_dir = Path(args.cache_dir) if args.cache_dir else output_dir.parent / ".ffmpeg-cache"
    executable, version_line = prepare(output_dir, target_platform=target_platform, arch=arch, cache_dir=cache_dir)
    print(f"Prepared {executable}")
    print(version_line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
