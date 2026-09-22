"""GitHub release update checking for TLO GUI applications.

The update checker deliberately downloads only. It does not unzip, install, or
replace files in TLOHome. This keeps the check/download action safe while TLO is
running; package contents are validated and any database inclusion is reported.
"""
from __future__ import annotations

from tlo_diagnostics import debug_suppressed_exception

__version__ = "v490"

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

DEFAULT_REPO_OWNER = OFFICIAL_GITHUB_OWNER
DEFAULT_REPO_NAME = OFFICIAL_GITHUB_REPO
SETTINGS_FILE_NAME = "update-settings.json"
AUTO_CHECK_INTERVAL_HOURS = 24
MAX_UPDATE_ASSET_BYTES = 1024 * 1024 * 1024  # 1 GiB hard safety ceiling
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
    except Exception:
        return None


def _settings_path(tlo_home: str | os.PathLike[str] | None) -> Path | None:
    if not tlo_home:
        return None
    try:
        return Path(tlo_home).expanduser().resolve() / SETTINGS_FILE_NAME
    except Exception:
        return None


def load_update_settings(tlo_home: str | os.PathLike[str] | None) -> dict[str, Any]:
    path = _settings_path(tlo_home)
    if path is None or not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_update_settings(tlo_home: str | os.PathLike[str] | None, settings: dict[str, Any]) -> None:
    path = _settings_path(tlo_home)
    if path is None:
        raise ValueError("TLOHome is required to save update settings.")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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


def _detect_platform_key() -> tuple[str, tuple[str, ...]]:
    """Backward-compatible coarse platform helper used by older callers/tests."""
    exact = _detect_installed_platform_key(None)
    if exact in {"windows", "windows_onedir"}:
        return "windows", ("windows", "win")
    if exact == "macos":
        return "macos", ("macos", "mac", "darwin", "osx", "os-x")
    return "linux", ("linux",)


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
            bad_member = archive.testzip()
            if bad_member:
                raise ValueError(f"Downloaded TLO package contains a corrupt ZIP member: {bad_member}")
            member_name = "UPDATE_MANIFEST.json" if expected_kind == "update" else "manifest.json"
            manifest = _read_zip_json_member(archive, member_name)
            names = {name.replace("\\", "/") for name in archive.namelist()}
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
        destination = _downloads_dir() / _safe_asset_filename(available.asset_name)
        downloaded = _download_asset(asset, destination)
        package_info = _inspect_downloaded_package(
            destination,
            expected_kind=available.package_kind,
            expected_platform_key=available.platform_key,
            expected_build=available.latest_build,
        )
        databases_included = bool(package_info["databases_included"])
        packaging_mode = str(package_info["packaging_mode"] or "")
        settings_warning = _update_download_settings(
            tlo_home, available.latest_build, available.asset_name, destination, available.package_kind,
            platform_key=available.platform_key, packaging_mode=packaging_mode,
            databases_included=databases_included,
        )
        kind_text, extra = _package_message(available.package_kind, databases_included)
        if downloaded:
            title = "TLO update downloaded"
            lead = f"TLO v{PUBLIC_VERSION} Build {available.latest_build} {kind_text} was downloaded to:"
            status = "downloaded"
        else:
            title = "TLO update already downloaded"
            lead = f"TLO v{PUBLIC_VERSION} Build {available.latest_build} {kind_text} is already available at:"
            status = "already_downloaded"
        return UpdateCheckResult(
            status=status,
            title=title,
            message=f"{lead}\n\n{destination}\n\n{extra}" + (f"\n\n{settings_warning}" if settings_warning else ""),
            latest_build=available.latest_build,
            path=str(destination),
            asset_name=available.asset_name,
            package_kind=available.package_kind,
            platform_key=available.platform_key,
            packaging_mode=packaging_mode,
            databases_included=databases_included,
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
        if latest_build <= BUNDLE_BUILD:
            settings_warning = _write_last_check(tlo_home, latest_build)
            message = f"Installed: {DISPLAY_VERSION}\nLatest: v{PUBLIC_VERSION} Build {latest_build}"
            if settings_warning:
                message += f"\n\n{settings_warning}"
            return UpdateCheckResult(
                status="up_to_date", title="TLO is up to date", message=message, latest_build=latest_build,
            )

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

        destination = _downloads_dir() / _safe_asset_filename(asset_name)
        downloaded = _download_asset(asset, destination)
        package_info = _inspect_downloaded_package(
            destination,
            expected_kind=package_kind,
            expected_platform_key=platform_key,
            expected_build=latest_build,
        )
        databases_included = bool(package_info["databases_included"])
        packaging_mode = str(package_info["packaging_mode"] or "")
        settings_warning = _update_download_settings(
            tlo_home, latest_build, asset_name, destination, package_kind,
            platform_key=platform_key, packaging_mode=packaging_mode,
            databases_included=databases_included,
        )
        kind_text, extra = _package_message(package_kind, databases_included)
        verification_note = ""
        if downloaded:
            title = "TLO update downloaded"
            lead = f"TLO v{PUBLIC_VERSION} Build {latest_build} {kind_text} was downloaded to:"
            status = "downloaded"
        else:
            title = "TLO update already downloaded"
            lead = f"TLO v{PUBLIC_VERSION} Build {latest_build} {kind_text} is already available at:"
            status = "already_downloaded"
        return UpdateCheckResult(
            status=status,
            title=title,
            message=f"{lead}\n\n{destination}\n\n{extra}{verification_note}" + (f"\n\n{settings_warning}" if settings_warning else ""),
            latest_build=latest_build,
            path=str(destination),
            asset_name=asset_name,
            package_kind=package_kind,
            platform_key=platform_key,
            packaging_mode=packaging_mode,
            databases_included=databases_included,
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
