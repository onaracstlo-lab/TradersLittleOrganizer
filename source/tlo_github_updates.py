"""GitHub release update checking for TLO GUI applications.

The update checker deliberately downloads only. It does not unzip, install, or
replace files in TLOHome. This keeps the check/download action safe while TLO is
running; package contents are validated and any database inclusion is reported.
"""
from __future__ import annotations

from tlo_diagnostics import debug_suppressed_exception

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import datetime as _dt
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tlo_version import BUNDLE_BUILD, DISPLAY_VERSION, OFFICIAL_GITHUB_OWNER, OFFICIAL_GITHUB_REPO, PUBLIC_VERSION
from tlo_network_io import MAX_METADATA_RESPONSE_BYTES, read_bounded_text
from tlo_update_trust import pinned_key_configured, verify_metadata_signature
from tlo_security import windows_reserved_folder_name

DEFAULT_REPO_OWNER = OFFICIAL_GITHUB_OWNER
DEFAULT_REPO_NAME = OFFICIAL_GITHUB_REPO
SETTINGS_FILE_NAME = "update-settings.json"
AUTO_CHECK_INTERVAL_HOURS = 24
MAX_UPDATE_ASSET_BYTES = 1024 * 1024 * 1024  # 1 GiB hard safety ceiling
SIGNED_METADATA_ASSET_NAME = "TLO_UPDATE_METADATA.json"
SIGNED_METADATA_SIGNATURE_ASSET_NAME = "TLO_UPDATE_METADATA.sig"
SIGNED_METADATA_SCHEMA = 1
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
USER_AGENT = f"TLO-update-checker/{DISPLAY_VERSION.replace(' ', '-') }"
ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
    "release-assets.githubusercontent.com",
}
ALLOWED_DOWNLOAD_HOST_SUFFIXES = ()


@dataclass(frozen=True)
class UpdateCheckResult:
    status: str
    title: str
    message: str
    latest_build: int | None = None
    installed_build: int = BUNDLE_BUILD
    path: str = ""
    asset_name: str = ""
    package_kind: str = ""
    platform_key: str = ""
    packaging_mode: str = ""
    databases_included: bool | None = None
    asset_url: str = ""
    asset_size: int = 0
    asset_digest: str = ""


def _utc_now() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc)


def _parse_utc(value: Any) -> _dt.datetime | None:
    if not value:
        return None
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = _dt.datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_dt.timezone.utc)
        return parsed.astimezone(_dt.timezone.utc)
    except (TypeError, ValueError, OverflowError):
        return None


def _settings_path(tlo_home: str | os.PathLike[str] | None) -> Path | None:
    if not tlo_home:
        return None
    try:
        return Path(tlo_home).expanduser().resolve() / SETTINGS_FILE_NAME
    except (OSError, RuntimeError, ValueError):
        return None


def load_update_settings(tlo_home: str | os.PathLike[str] | None) -> dict[str, Any]:
    path = _settings_path(tlo_home)
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError):
        return {}


def _write_text_atomic(path: Path, text: str) -> None:
    """Write UTF-8 text through a same-directory temporary file and atomic replace."""
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
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    finally:
        if temporary_name:
            try:
                Path(temporary_name).unlink(missing_ok=True)
            except OSError as exc:
                debug_suppressed_exception(__name__, exc)


def save_update_settings(tlo_home: str | os.PathLike[str] | None, settings: dict[str, Any]) -> None:
    path = _settings_path(tlo_home)
    if path is None:
        raise ValueError("TLOHome is required to save update settings.")
    _write_text_atomic(path, json.dumps(settings, indent=2, sort_keys=True) + "\n")


def is_auto_update_enabled(tlo_home: str | os.PathLike[str] | None) -> bool:
    return bool(load_update_settings(tlo_home).get("auto_update"))


def set_auto_update_enabled(tlo_home: str | os.PathLike[str] | None, enabled: bool) -> None:
    settings = load_update_settings(tlo_home)
    settings["auto_update"] = bool(enabled)
    settings["updated_utc"] = _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    save_update_settings(tlo_home, settings)


def should_auto_check(tlo_home: str | os.PathLike[str] | None, *, minimum_hours: int = AUTO_CHECK_INTERVAL_HOURS) -> bool:
    settings = load_update_settings(tlo_home)
    if not settings.get("auto_update"):
        return False
    last_check = _parse_utc(settings.get("last_check_utc"))
    if last_check is None:
        return True
    return (_utc_now() - last_check) >= _dt.timedelta(hours=minimum_hours)


def _write_last_check(tlo_home: str | os.PathLike[str] | None, latest_build: int | None = None) -> str:
    if not tlo_home:
        return ""
    settings = load_update_settings(tlo_home)
    settings["last_check_utc"] = _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    if latest_build is not None:
        settings["last_checked_build"] = int(latest_build)
    try:
        save_update_settings(tlo_home, settings)
    except Exception as exc:  # noqa: BLE001 - persistence error must be disclosed, not fatal
        return f"Update settings could not be saved: {exc}"
    return ""


def _fetch_latest_release(owner: str, repo: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/releases/latest"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(read_bounded_text(response, MAX_METADATA_RESPONSE_BYTES, label="GitHub release metadata"))


def _extract_build_number(*values: Any) -> int | None:
    for value in values:
        text = str(value or "")
        for pattern in (
            r"(?i)build[\s_-]*(\d{1,6})",
            r"(?i)v\d+(?:\.\d+)?[-_ ]*b(?:uild)?[\s_-]*(\d{1,6})",
            r"(?i)(?:^|[_-])v?(\d{1,6})(?:\.zip)?$",
        ):
            match = re.search(pattern, text)
            if match:
                try:
                    return int(match.group(1))
                except Exception:
                    continue
    return None


def _detect_installed_platform_key(tlo_home: str | os.PathLike[str] | None = None) -> str:
    """Return the exact release platform/layout required by this installation.

    Windows hybrid and Windows onedir distributions share the same operating
    system but are not overlay-compatible. Prefer the installed TLOHome layout
    when it is available; fall back to the running executable layout; finally
    retain the historic Windows-hybrid default for source/development runs.
    """
    if sys.platform == "darwin":
        return "macos"
    if not sys.platform.startswith("win"):
        return "linux"

    candidates: list[Path] = []
    if tlo_home:
        try:
            candidates.append(Path(tlo_home).expanduser().resolve() / "apps" / "Windows")
        except Exception:
            pass
    try:
        candidates.append(Path(sys.executable).resolve().parent)
    except Exception:
        pass

    for apps_dir in candidates:
        if (apps_dir / "_internal").is_dir():
            return "windows_onedir"
    return "windows"


def _asset_name(asset: dict[str, Any]) -> str:
    return str(asset.get("name") or "")


def _asset_download_url(asset: dict[str, Any]) -> str:
    return str(asset.get("browser_download_url") or "")


def _safe_asset_filename(asset_name: str) -> str:
    """Return a Downloads-safe basename for a GitHub asset name."""
    name = Path(str(asset_name or "")).name
    name = re.sub(r"[^A-Za-z0-9._ -]+", "_", name).strip(" .")
    return name or "TLO-update.zip"


def _download_host_allowed(url: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(str(url or ""))
    except Exception:
        return False
    if parsed.scheme.casefold() != "https":
        return False
    host = (parsed.hostname or "").casefold().strip(".")
    return host in ALLOWED_DOWNLOAD_HOSTS or any(host.endswith(suffix) for suffix in ALLOWED_DOWNLOAD_HOST_SUFFIXES)


class _GitHubOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject any download redirect that leaves the GitHub host allowlist."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        resolved = urllib.parse.urljoin(req.full_url, str(newurl or ""))
        if not _download_host_allowed(resolved):
            raise urllib.error.HTTPError(
                resolved, code, "Refusing update redirect outside the GitHub download allowlist", headers, fp
            )
        return super().redirect_request(req, fp, code, msg, headers, resolved)


def _open_download_url(request: urllib.request.Request, *, timeout: int):
    opener = urllib.request.build_opener(_GitHubOnlyRedirectHandler())
    return opener.open(request, timeout=timeout)


def _matching_assets(release: dict[str, Any]) -> list[dict[str, Any]]:
    assets = release.get("assets")
    return [asset for asset in assets if isinstance(asset, dict)] if isinstance(assets, list) else []


def _asset_release_identity(asset_name: str) -> tuple[int | None, str, str] | None:
    """Return ``(build, kind, platform_key)`` for an official release ZIP name."""
    name = Path(str(asset_name or "")).name
    match = re.fullmatch(
        r"(?i)TLO_V\d+(?:\.\d+){1,2}Build(?P<build>\d{1,6})_"
        r"(?P<kind>update|complete)_(?P<platform>Windows_onedir|Windows|Linux|macOS)\.zip",
        name,
    )
    if not match:
        return None
    platform_token = match.group("platform").casefold()
    platform_key = {
        "windows": "windows",
        "windows_onedir": "windows_onedir",
        "linux": "linux",
        "macos": "macos",
    }[platform_token]
    return int(match.group("build")), match.group("kind").casefold(), platform_key


def _choose_asset(
    release: dict[str, Any],
    latest_build: int,
    tlo_home: str | os.PathLike[str] | None = None,
) -> tuple[dict[str, Any] | None, str, str]:
    """Choose only an exact platform/layout TLO update or complete ZIP.

    Update ZIPs are preferred. A matching complete ZIP is the only fallback.
    Generic ZIPs (including the source bundle) and the other Windows packaging
    layout are never selected as substitutes.
    """
    platform_key = _detect_installed_platform_key(tlo_home)
    update_candidates: list[dict[str, Any]] = []
    complete_candidates: list[dict[str, Any]] = []
    for asset in _matching_assets(release):
        identity = _asset_release_identity(_asset_name(asset))
        if identity is None:
            continue
        asset_build, kind, asset_platform = identity
        if asset_build != latest_build or asset_platform != platform_key:
            continue
        if kind == "update":
            update_candidates.append(asset)
        elif kind == "complete":
            complete_candidates.append(asset)

    if update_candidates:
        return update_candidates[0], "update", platform_key
    if complete_candidates:
        return complete_candidates[0], "complete", platform_key
    return None, "", platform_key


def _downloads_dir() -> Path:
    candidate = Path.home() / "Downloads"
    if candidate.is_dir():
        return candidate
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except Exception:
        return Path.home()


def _release_asset_by_name(release: dict[str, Any], name: str) -> dict[str, Any] | None:
    for asset in _matching_assets(release):
        if _asset_name(asset) == name:
            return asset
    return None


def _fetch_small_release_asset(asset: dict[str, Any], *, label: str, max_bytes: int = MAX_METADATA_RESPONSE_BYTES) -> bytes:
    url = _asset_download_url(asset)
    if not url or not _download_host_allowed(url):
        raise ValueError(f"{label} does not have an allowed GitHub download URL.")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with _open_download_url(request, timeout=20) as response:
        payload = response.read(max_bytes + 1)
    if len(payload) > max_bytes:
        raise ValueError(f"{label} exceeds the metadata safety limit.")
    return payload


def _load_verified_release_metadata(release: dict[str, Any]) -> dict[str, Any]:
    if not pinned_key_configured():
        raise ValueError("This TLO build does not contain a pinned update-signing public key; secure update checks are disabled.")
    metadata_asset = _release_asset_by_name(release, SIGNED_METADATA_ASSET_NAME)
    signature_asset = _release_asset_by_name(release, SIGNED_METADATA_SIGNATURE_ASSET_NAME)
    if metadata_asset is None or signature_asset is None:
        raise ValueError("The latest TLO release is not locally signed; refusing update metadata from GitHub alone.")
    try:
        metadata = json.loads(_fetch_small_release_asset(metadata_asset, label=SIGNED_METADATA_ASSET_NAME).decode("utf-8"))
        signature_b64 = _fetch_small_release_asset(signature_asset, label=SIGNED_METADATA_SIGNATURE_ASSET_NAME, max_bytes=16384).decode("ascii").strip()
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("The signed TLO update metadata is malformed.") from exc
    if not isinstance(metadata, dict) or metadata.get("schema") != SIGNED_METADATA_SCHEMA:
        raise ValueError("The signed TLO update metadata has an unsupported schema.")
    if not verify_metadata_signature(metadata, signature_b64):
        raise ValueError("The TLO update metadata signature does not match the public key pinned in this application.")
    release_tag = metadata.get("release_tag")
    if not isinstance(release_tag, str) or not release_tag.strip():
        raise ValueError("The signed TLO update metadata is missing its required release tag binding.")
    return metadata


def _signed_asset_record(metadata: dict[str, Any], asset_name: str) -> dict[str, Any]:
    assets = metadata.get("assets")
    if not isinstance(assets, list):
        raise ValueError("The signed TLO update metadata does not contain an asset list.")
    matches = [item for item in assets if isinstance(item, dict) and str(item.get("name") or "") == asset_name]
    if len(matches) != 1:
        raise ValueError(f"The selected TLO asset is not uniquely authorized by signed metadata: {asset_name}")
    record = matches[0]
    digest = str(record.get("sha256") or "").lower()
    try:
        size = int(record.get("size") or 0)
        build = int(record.get("build") or 0)
    except (TypeError, ValueError) as exc:
        raise ValueError("The signed TLO asset record contains invalid numeric values.") from exc
    if not re.fullmatch(r"[a-f0-9]{64}", digest) or size < 1 or build < 1:
        raise ValueError("The signed TLO asset record is incomplete or invalid.")
    return record


def _apply_signed_asset_metadata(asset: dict[str, Any], metadata: dict[str, Any], *, expected_build: int, expected_kind: str, expected_platform_key: str) -> dict[str, Any]:
    record = _signed_asset_record(metadata, _asset_name(asset))
    if int(record["build"]) != int(expected_build):
        raise ValueError("Signed update metadata build does not match the selected release.")
    if str(record.get("kind") or "").casefold() != expected_kind:
        raise ValueError("Signed update metadata package kind does not match the selected release asset.")
    if str(record.get("platform_key") or "").casefold().replace("-", "_") != expected_platform_key:
        raise ValueError("Signed update metadata platform/layout does not match this TLO installation.")
    declared_size = _declared_asset_size(asset)
    if declared_size and declared_size != int(record["size"]):
        raise ValueError("GitHub release asset size disagrees with independently signed TLO metadata.")
    trusted = dict(asset)
    trusted["size"] = int(record["size"])
    trusted["digest"] = "sha256:" + str(record["sha256"])
    return trusted


def _expected_digest(asset: dict[str, Any]) -> str:
    raw = str(asset.get("digest") or asset.get("sha256") or "").strip().lower()
    if raw.startswith("sha256:"):
        raw = raw.split(":", 1)[1].strip()
    if re.fullmatch(r"[a-f0-9]{64}", raw):
        return raw
    return ""


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _file_matches_asset(path: Path, asset: dict[str, Any]) -> bool:
    if not path.is_file():
        return False
    size = asset.get("size")
    try:
        if size is not None and int(size) > 0 and path.stat().st_size != int(size):
            return False
    except Exception:
        return False
    digest = _expected_digest(asset)
    if not digest:
        return False
    return _sha256_file(path).lower() == digest


def _declared_asset_size(asset: dict[str, Any]) -> int:
    try:
        size = int(asset.get("size") or 0)
    except (TypeError, ValueError):
        return 0
    return max(0, size)


def _download_asset(asset: dict[str, Any], destination: Path) -> bool:
    url = _asset_download_url(asset)
    if not url:
        raise ValueError("The selected release asset does not include a download URL.")
    if not _download_host_allowed(url):
        raise ValueError("The selected release asset download URL is not hosted by GitHub.")
    declared_size = _declared_asset_size(asset)
    if declared_size > MAX_UPDATE_ASSET_BYTES:
        raise ValueError(
            f"Refusing implausibly large TLO update asset ({declared_size} bytes; "
            f"maximum {MAX_UPDATE_ASSET_BYTES} bytes)."
        )
    digest = _expected_digest(asset)
    if not digest:
        raise ValueError("The selected release asset does not provide a valid SHA-256 digest; refusing an unverifiable update download.")
    if destination.exists() and _file_matches_asset(destination, asset):
        return False

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".download", dir=str(destination.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        downloaded_bytes = 0
        with _open_download_url(request, timeout=60) as response, temp_path.open("wb") as handle:
            response_length = 0
            try:
                response_length = int(response.headers.get("Content-Length") or 0)
            except (AttributeError, TypeError, ValueError):
                response_length = 0
            if response_length > MAX_UPDATE_ASSET_BYTES:
                raise ValueError("Refusing update response larger than the TLO download safety ceiling.")
            while True:
                chunk = response.read(DOWNLOAD_CHUNK_BYTES)
                if not chunk:
                    break
                downloaded_bytes += len(chunk)
                if downloaded_bytes > MAX_UPDATE_ASSET_BYTES:
                    raise IOError("TLO update download exceeded the hard size ceiling.")
                if declared_size and downloaded_bytes > declared_size:
                    raise IOError(f"Downloaded data exceeded the declared size for {destination.name}.")
                handle.write(chunk)
        if declared_size and downloaded_bytes != declared_size:
            raise IOError(f"Downloaded size mismatch for {destination.name}.")
        if _sha256_file(temp_path).lower() != digest:
            raise IOError(f"Downloaded SHA-256 digest mismatch for {destination.name}.")
        temp_path.replace(destination)
        return True
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception as exc:  # noqa: BLE001 - best-effort boundary
            debug_suppressed_exception(__name__, exc)



MAX_PACKAGE_MANIFEST_BYTES = 1024 * 1024
MAX_ZIP_MEMBERS = 5000
MAX_ZIP_UNCOMPRESSED_BYTES = MAX_UPDATE_ASSET_BYTES * 4
MAX_ZIP_COMPRESSION_RATIO = 250

UPDATE_PROTECTED_PATHS = (
    "bootlist.csv",
    "toBeInventoried.txt",
    "setlists/",
    "logs/",
    "debug/",
    "dups/",
    "readyForXfer/",
    "staged/",
    "unidentifiedShows.txt",
)


def _read_zip_json_member(archive: zipfile.ZipFile, member_name: str) -> dict[str, Any]:
    try:
        info = archive.getinfo(member_name)
    except KeyError as exc:
        raise ValueError(f"Downloaded TLO package is missing {member_name}.") from exc
    if info.file_size < 1 or info.file_size > MAX_PACKAGE_MANIFEST_BYTES:
        raise ValueError(f"Downloaded TLO package has an invalid {member_name} size.")
    with archive.open(info, "r") as handle:
        payload = handle.read(MAX_PACKAGE_MANIFEST_BYTES + 1)
    if len(payload) > MAX_PACKAGE_MANIFEST_BYTES:
        raise ValueError(f"Downloaded TLO package {member_name} exceeds the safety limit.")
    try:
        data = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Downloaded TLO package has malformed {member_name}.") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Downloaded TLO package has malformed {member_name}.")
    return data


def _manifest_build_number(manifest: dict[str, Any]) -> int | None:
    raw = manifest.get("build", manifest.get("build_number"))
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _validate_zip_members(archive: zipfile.ZipFile) -> set[str]:
    """Validate member paths/types and decompression bounds before testzip()."""
    names: set[str] = set()
    folded_names: set[str] = set()
    total_uncompressed = 0
    infos = archive.infolist()
    if len(infos) > MAX_ZIP_MEMBERS:
        raise ValueError(f"Downloaded TLO package contains too many ZIP members ({len(infos)}).")
    for info in infos:
        raw_name = str(info.filename or "")
        name = raw_name.replace("\\", "/")
        if not name or "\x00" in name:
            raise ValueError("Downloaded TLO package contains an invalid ZIP member name.")
        if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
            raise ValueError(f"Downloaded TLO package contains an absolute ZIP member path: {raw_name}")
        parts = [part for part in name.split("/") if part not in {"", "."}]
        if any(part == ".." for part in parts):
            raise ValueError(f"Downloaded TLO package contains parent traversal in ZIP member: {raw_name}")
        normalized_name = "/".join(parts)
        folded_name = normalized_name.casefold()
        if folded_name in folded_names:
            raise ValueError(f"Downloaded TLO package contains a duplicate ZIP member name: {raw_name}")
        for part in parts:
            if ":" in part:
                raise ValueError(f"Downloaded TLO package contains an NTFS alternate-data-stream name: {raw_name}")
            if part.endswith((".", " ")):
                raise ValueError(f"Downloaded TLO package contains a Windows-unsafe component: {raw_name}")
            if windows_reserved_folder_name(part):
                raise ValueError(f"Downloaded TLO package contains a reserved Windows device name: {raw_name}")
        unix_mode = (int(info.external_attr) >> 16) & 0xFFFF
        if (unix_mode & 0o170000) == 0o120000:
            raise ValueError(f"Downloaded TLO package contains a symbolic-link ZIP member: {raw_name}")
        total_uncompressed += int(info.file_size or 0)
        if total_uncompressed > MAX_ZIP_UNCOMPRESSED_BYTES:
            raise ValueError("Downloaded TLO package exceeds the uncompressed-size safety limit.")
        compressed = int(info.compress_size or 0)
        if int(info.file_size or 0) > 1024 * 1024 and compressed > 0:
            ratio = int(info.file_size or 0) / compressed
            if ratio > MAX_ZIP_COMPRESSION_RATIO:
                raise ValueError(f"Downloaded TLO package contains an unsafe compression ratio: {raw_name}")
        names.add(normalized_name)
        folded_names.add(folded_name)
    return names


def _normalize_manifest_path(value: str) -> str:
    """Return a canonical relative manifest path, preserving a directory suffix."""
    raw = str(value or "")
    if not raw or "\x00" in raw:
        raise ValueError("Downloaded TLO package has an invalid protected_paths manifest value.")
    name = raw.replace("\\", "/")
    if name.startswith("/") or re.match(r"^[A-Za-z]:", name):
        raise ValueError("Downloaded TLO package has an invalid protected_paths manifest value.")
    directory = name.endswith("/")
    parts = [part for part in name.split("/") if part not in {"", "."}]
    if not parts or any(part == ".." for part in parts):
        raise ValueError("Downloaded TLO package has an invalid protected_paths manifest value.")
    normalized = "/".join(parts)
    return normalized + ("/" if directory else "")


def _validate_update_safety_manifest(
    manifest: dict[str, Any],
    names: set[str],
    *,
    databases_included: bool,
) -> None:
    """Enforce the fail-closed update-package safety contract."""
    if manifest.get("safe_update") is not True:
        raise ValueError("Downloaded TLO update is not marked safe_update=true.")
    if manifest.get("requires_complete_install") is not False:
        raise ValueError("Downloaded TLO update does not declare requires_complete_install=false.")

    declared = manifest.get("protected_paths")
    if not isinstance(declared, list) or not all(isinstance(item, str) for item in declared):
        raise ValueError("Downloaded TLO update has an invalid protected_paths manifest value.")

    expected = list(UPDATE_PROTECTED_PATHS)
    if not databases_included:
        expected.append("TLO_DBs/")
    try:
        declared_normalized = [_normalize_manifest_path(item) for item in declared]
        expected_normalized = [_normalize_manifest_path(item) for item in expected]
    except ValueError:
        raise
    declared_folded = {item.casefold() for item in declared_normalized}
    expected_folded = {item.casefold() for item in expected_normalized}
    if len(declared_normalized) != len(expected_normalized) or declared_folded != expected_folded:
        raise ValueError(
            "Downloaded TLO update protected_paths manifest does not match the required protected paths."
        )

    protected_files = {item.casefold() for item in expected_normalized if not item.endswith("/")}
    protected_dirs = {item[:-1].casefold() for item in expected_normalized if item.endswith("/")}
    for member in names:
        folded = member.casefold()
        if folded in protected_files or any(folded == directory or folded.startswith(directory + "/") for directory in protected_dirs):
            raise ValueError(f"Downloaded TLO update contains protected user-data path: {member}")


def _inspect_downloaded_package(
    path: Path,
    *,
    expected_kind: str,
    expected_platform_key: str,
    expected_build: int,
) -> dict[str, Any]:
    """Validate release-package identity without extracting any files."""
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = _validate_zip_members(archive)
            bad_member = archive.testzip()
            if bad_member:
                raise ValueError(f"Downloaded TLO package contains a corrupt ZIP member: {bad_member}")
            member_name = "UPDATE_MANIFEST.json" if expected_kind == "update" else "manifest.json"
            manifest = _read_zip_json_member(archive, member_name)
    except zipfile.BadZipFile as exc:
        raise ValueError("Downloaded TLO release asset is not a valid ZIP file.") from exc

    kind = str(manifest.get("kind") or "").casefold()
    if kind != expected_kind:
        raise ValueError(f"Downloaded TLO package kind is {kind or 'unknown'}, expected {expected_kind}.")
    platform_key = str(manifest.get("platform_key") or "").casefold().replace("-", "_")
    if platform_key != expected_platform_key:
        raise ValueError(
            f"Downloaded TLO package targets {platform_key or 'an unknown platform/layout'}, "
            f"expected {expected_platform_key}."
        )
    build = _manifest_build_number(manifest)
    if build != int(expected_build):
        raise ValueError(f"Downloaded TLO package build is {build!r}, expected Build {expected_build}.")

    required_db_names = {"TLO_DBs/artists.sqlite", "TLO_DBs/venues.txt"}
    database_members = {name for name in names if name.startswith("TLO_DBs/") and not name.endswith("/")}
    declared_databases = manifest.get("databases_included")
    if not isinstance(declared_databases, bool):
        raise ValueError("Downloaded TLO package has an invalid databases_included manifest value.")
    databases_included = declared_databases
    expected_database_members = required_db_names if databases_included else set()
    if database_members != expected_database_members:
        raise ValueError("Downloaded TLO package database manifest does not match its ZIP contents.")

    declared_database_files = manifest.get("database_files")
    if declared_database_files is not None:
        if not isinstance(declared_database_files, list) or not all(isinstance(item, str) for item in declared_database_files):
            raise ValueError("Downloaded TLO package has an invalid database_files manifest value.")
        expected_database_files = sorted(path.split("/", 1)[1] for path in expected_database_members)
        if sorted(declared_database_files) != expected_database_files:
            raise ValueError("Downloaded TLO package database_files manifest does not match its ZIP contents.")

    if expected_kind == "complete" and not databases_included:
        raise ValueError("Downloaded complete TLO package is missing the required databases.")
    if expected_kind == "update":
        _validate_update_safety_manifest(manifest, names, databases_included=databases_included)

    packaging_mode = str(manifest.get("packaging_mode") or "").strip()
    return {
        "kind": kind,
        "platform_key": platform_key,
        "packaging_mode": packaging_mode,
        "databases_included": databases_included,
    }


def _package_message(package_kind: str, databases_included: bool) -> tuple[str, str]:
    if package_kind == "update":
        kind_text = "update"
        if databases_included:
            extra = (
                "This update includes refreshed TLO_DBs/artists.sqlite and venues.txt. "
                "Applying it will replace those database master files. It does not contain "
                "your inventory, setlists, logs, or other user-created output."
            )
        else:
            extra = "This update does not contain your inventory, setlists, logs, or databases."
        return kind_text, extra
    return (
        "complete distribution",
        "This complete distribution includes the required database master files and support files. "
        "Use it for a new installation; review the release notes before replacing files in an existing TLOHome.",
    )

def _update_download_settings(
    tlo_home: str | os.PathLike[str] | None,
    latest_build: int,
    asset_name: str,
    path: Path,
    package_kind: str,
    *,
    platform_key: str = "",
    packaging_mode: str = "",
    databases_included: bool | None = None,
) -> str:
    if not tlo_home:
        return ""
    settings = load_update_settings(tlo_home)
    settings["last_check_utc"] = _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    settings["last_checked_build"] = int(latest_build)
    settings["last_downloaded_build"] = int(latest_build)
    settings["last_downloaded_asset"] = asset_name
    settings["last_downloaded_path"] = str(path)
    settings["last_downloaded_kind"] = package_kind
    settings["last_downloaded_platform_key"] = platform_key
    settings["last_downloaded_packaging_mode"] = packaging_mode
    settings["last_downloaded_databases_included"] = databases_included
    try:
        save_update_settings(tlo_home, settings)
    except Exception as exc:  # noqa: BLE001 - download succeeded; disclose persistence failure
        return f"Update settings could not be saved: {exc}"
    return ""


def _download_and_report_verified_asset(
    asset: dict[str, Any], *, tlo_home: str | os.PathLike[str] | None,
    latest_build: int, asset_name: str, package_kind: str, platform_key: str,
) -> UpdateCheckResult:
    """Single validation/persistence/reporting path for both updater entry points.

    This helper runs only after independently signed release metadata has been
    checked by the caller, or after a verified ``available`` result is passed to
    ``download_update``. The download itself retains size and digest checks.
    """
    destination = _downloads_dir() / _safe_asset_filename(asset_name)
    downloaded = _download_asset(asset, destination)
    package_info = _inspect_downloaded_package(
        destination, expected_kind=package_kind,
        expected_platform_key=platform_key, expected_build=latest_build,
    )
    databases_included = bool(package_info["databases_included"])
    packaging_mode = str(package_info["packaging_mode"] or "")
    settings_warning = _update_download_settings(
        tlo_home, latest_build, asset_name, destination, package_kind,
        platform_key=platform_key, packaging_mode=packaging_mode,
        databases_included=databases_included,
    )
    kind_text, extra = _package_message(package_kind, databases_included)
    if downloaded:
        title = "TLO update downloaded"
        lead = f"TLO v{PUBLIC_VERSION} Build {latest_build} {kind_text} was downloaded to:"
        status = "downloaded"
    else:
        title = "TLO update already downloaded"
        lead = f"TLO v{PUBLIC_VERSION} Build {latest_build} {kind_text} is already available at:"
        status = "already_downloaded"
    return UpdateCheckResult(
        status=status, title=title,
        message=f"{lead}\n\n{destination}\n\n{extra}" + (f"\n\n{settings_warning}" if settings_warning else ""),
        latest_build=latest_build, path=str(destination), asset_name=asset_name,
        package_kind=package_kind, platform_key=platform_key,
        packaging_mode=packaging_mode, databases_included=databases_included,
    )


def download_update(
    available: UpdateCheckResult,
    tlo_home: str | os.PathLike[str] | None,
) -> UpdateCheckResult:
    """Download and validate an update previously returned with status ``available``."""
    if available.status != "available" or available.latest_build is None:
        return UpdateCheckResult(
            status="error",
            title="TLO update download failed",
            message="No pending TLO update is available to download.",
        )
    try:
        asset = {
            "name": available.asset_name,
            "browser_download_url": available.asset_url,
            "size": available.asset_size,
            "digest": f"sha256:{available.asset_digest}" if available.asset_digest else "",
        }
        if not available.asset_name or not available.asset_url or not available.asset_digest:
            raise ValueError("The pending TLO update is missing required verified asset metadata.")
        return _download_and_report_verified_asset(
            asset, tlo_home=tlo_home, latest_build=available.latest_build,
            asset_name=available.asset_name, package_kind=available.package_kind,
            platform_key=available.platform_key,
        )
    except urllib.error.HTTPError as exc:
        return UpdateCheckResult(
            status="error", title="TLO update download failed",
            message=f"GitHub returned HTTP {exc.code} while downloading the update.",
            latest_build=available.latest_build,
        )
    except urllib.error.URLError as exc:
        return UpdateCheckResult(
            status="error", title="TLO update download failed",
            message=f"Could not contact GitHub while downloading the update: {exc.reason}",
            latest_build=available.latest_build,
        )
    except Exception as exc:  # noqa: BLE001 - GUI-safe boundary
        return UpdateCheckResult(
            status="error", title="TLO update download failed", message=str(exc),
            latest_build=available.latest_build,
        )


def check_for_updates(
    tlo_home: str | os.PathLike[str] | None,
    *,
    manual: bool = True,
    download: bool = True,
    owner: str = DEFAULT_REPO_OWNER,
    repo: str = DEFAULT_REPO_NAME,
) -> UpdateCheckResult:
    """Check the latest GitHub Release and optionally download the preferred ZIP.

    Manual checks retain the historic direct-download behavior. Auto Update uses
    ``download=False`` to discover a newer exact-match package without downloading
    it; the GUI then asks the user with Yes / Skip before calling
    :func:`download_update`.
    """
    try:
        release = _fetch_latest_release(owner, repo)
        assets = _matching_assets(release)
        latest_build = _extract_build_number(
            release.get("tag_name"),
            release.get("name"),
            " ".join(_asset_name(asset) for asset in assets),
        )
        if latest_build is None:
            settings_warning = _write_last_check(tlo_home)
            message = "The latest GitHub Release did not contain a recognizable TLO build number."
            if settings_warning:
                message += f"\n\n{settings_warning}"
            return UpdateCheckResult(status="error", title="TLO update check failed", message=message)

        # GitHub release metadata is sufficient to determine that a release is
        # not newer than the installed build.  Independent signature
        # verification is required only before accepting a *newer* release as
        # an update candidate.  This avoids treating older pre-signing
        # releases as update-security failures (for example, installed Build
        # 514 while GitHub /releases/latest still points at unsigned Build
        # 512).
        if latest_build <= BUNDLE_BUILD:
            settings_warning = _write_last_check(tlo_home, latest_build)
            if latest_build < BUNDLE_BUILD:
                message = (
                    f"Installed: {DISPLAY_VERSION}\n"
                    f"Latest published GitHub release: v{PUBLIC_VERSION} Build {latest_build}\n\n"
                    "No newer TLO release is available."
                )
            else:
                message = f"Installed: {DISPLAY_VERSION}\nLatest: v{PUBLIC_VERSION} Build {latest_build}"
            if settings_warning:
                message += f"\n\n{settings_warning}"
            return UpdateCheckResult(
                status="up_to_date", title="TLO is up to date", message=message, latest_build=latest_build,
            )

        signed_metadata = _load_verified_release_metadata(release)
        try:
            signed_build = int(signed_metadata.get("build") or 0)
        except (TypeError, ValueError):
            signed_build = 0
        if signed_build != latest_build:
            raise ValueError("The independently signed TLO metadata build does not match the GitHub release build.")
        signed_tag = str(signed_metadata.get("release_tag") or "").strip()
        if not signed_tag:
            raise ValueError("The independently signed TLO metadata is missing its required release tag binding.")
        if signed_tag != str(release.get("tag_name") or ""):
            raise ValueError("The independently signed TLO metadata release tag does not match the GitHub release.")

        asset, package_kind, platform_key = _choose_asset(release, latest_build, tlo_home)
        if not asset:
            settings_warning = _write_last_check(tlo_home, latest_build)
            message = (
                f"Installed: {DISPLAY_VERSION}\n"
                f"Latest: v{PUBLIC_VERSION} Build {latest_build}\n\n"
                f"No update ZIP or complete ZIP matching {platform_key} was found in the latest GitHub Release."
            )
            if settings_warning:
                message += f"\n\n{settings_warning}"
            return UpdateCheckResult(
                status="no_asset", title="TLO update found, but no ZIP matched this platform",
                message=message, latest_build=latest_build,
            )

        asset_name = _asset_name(asset)
        asset = _apply_signed_asset_metadata(
            asset, signed_metadata, expected_build=latest_build, expected_kind=package_kind, expected_platform_key=platform_key
        )
        if not download:
            settings_warning = _write_last_check(tlo_home, latest_build)
            kind_text = "update" if package_kind == "update" else "complete distribution"
            message = (
                f"Installed: {DISPLAY_VERSION}\n"
                f"Latest: v{PUBLIC_VERSION} Build {latest_build}\n\n"
                f"A matching {kind_text} is available. Download it to your Downloads folder?"
            )
            if settings_warning:
                message += f"\n\n{settings_warning}"
            return UpdateCheckResult(
                status="available",
                title="TLO update available",
                message=message,
                latest_build=latest_build,
                asset_name=asset_name,
                package_kind=package_kind,
                platform_key=platform_key,
                asset_url=_asset_download_url(asset),
                asset_size=_declared_asset_size(asset),
                asset_digest=_expected_digest(asset),
            )

        return _download_and_report_verified_asset(
            asset, tlo_home=tlo_home, latest_build=latest_build,
            asset_name=asset_name, package_kind=package_kind, platform_key=platform_key,
        )
    except urllib.error.HTTPError as exc:
        return UpdateCheckResult(
            status="error",
            title="TLO update check failed",
            message=f"GitHub returned HTTP {exc.code} while checking for updates in {owner}/{repo}.",
        )
    except urllib.error.URLError as exc:
        return UpdateCheckResult(
            status="error",
            title="TLO update check failed",
            message=f"Could not contact GitHub while checking for updates: {exc.reason}",
        )
    except Exception as exc:  # noqa: BLE001 - GUI-safe boundary
        return UpdateCheckResult(
            status="error",
            title="TLO update check failed",
            message=str(exc),
        )
