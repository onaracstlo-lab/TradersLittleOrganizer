"""GitHub release update checking for TLO GUI applications.

The update checker deliberately downloads only. It does not unzip, install, or
replace files in TLOHome. This keeps updates safe while TLO is running and
avoids overwriting user inventory, setlists, logs, or databases.
"""
from __future__ import annotations

__version__ = "v335"
# TLO-GI package version: v335
__version_summary__ = 'Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.'
# TLO-GI version summary: Suppresses visible Windows child-console windows during SHN conversion and physical-drive PowerShell checks.

import datetime as _dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tlo_version import BUNDLE_BUILD, DISPLAY_VERSION

DEFAULT_REPO_OWNER = os.environ.get("TLO_GITHUB_OWNER", "onaracstlo-lab")
DEFAULT_REPO_NAME = os.environ.get("TLO_GITHUB_REPO", "TradersLittleOrganizer")
SETTINGS_FILE_NAME = "update-settings.json"
AUTO_CHECK_INTERVAL_HOURS = 24
USER_AGENT = f"TLO-update-checker/{DISPLAY_VERSION.replace(' ', '-') }"
ALLOWED_DOWNLOAD_HOSTS = {
    "github.com",
    "objects.githubusercontent.com",
    "github-releases.githubusercontent.com",
}
ALLOWED_DOWNLOAD_HOST_SUFFIXES = (".githubusercontent.com",)


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


def _write_last_check(tlo_home: str | os.PathLike[str] | None, latest_build: int | None = None) -> None:
    if not tlo_home:
        return
    settings = load_update_settings(tlo_home)
    settings["last_check_utc"] = _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    if latest_build is not None:
        settings["last_checked_build"] = int(latest_build)
    try:
        save_update_settings(tlo_home, settings)
    except Exception:
        pass


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
        return json.loads(response.read().decode("utf-8"))


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


def _detect_platform_key() -> tuple[str, tuple[str, ...]]:
    if sys.platform.startswith("win"):
        return "windows", ("windows", "win")
    if sys.platform == "darwin":
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


def _matching_assets(release: dict[str, Any]) -> list[dict[str, Any]]:
    assets = release.get("assets")
    return [asset for asset in assets if isinstance(asset, dict)] if isinstance(assets, list) else []


def _choose_asset(release: dict[str, Any], latest_build: int) -> tuple[dict[str, Any] | None, str, str]:
    platform_key, aliases = _detect_platform_key()
    assets = _matching_assets(release)

    def normalized(name: str) -> str:
        return re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")

    update_candidates: list[dict[str, Any]] = []
    complete_candidates: list[dict[str, Any]] = []
    generic_candidates: list[dict[str, Any]] = []
    for asset in assets:
        name = _asset_name(asset)
        norm = normalized(name)
        if not norm.endswith("zip"):
            continue
        has_platform = any(alias in norm for alias in aliases)
        has_update = "update" in norm
        has_complete = "complete" in norm or "distribution" in norm
        asset_build = _extract_build_number(name)
        build_ok = asset_build is None or asset_build == latest_build
        if has_update and has_platform and build_ok:
            update_candidates.append(asset)
        elif has_complete and has_platform and build_ok:
            complete_candidates.append(asset)
        elif has_complete and build_ok and not has_platform:
            generic_candidates.append(asset)
        elif build_ok and not has_update and not has_platform:
            generic_candidates.append(asset)

    if update_candidates:
        return update_candidates[0], "update", platform_key
    if complete_candidates:
        return complete_candidates[0], "complete", platform_key
    if generic_candidates:
        return generic_candidates[0], "complete", platform_key
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
    return not digest or _sha256_file(path).lower() == digest


def _download_asset(asset: dict[str, Any], destination: Path) -> bool:
    url = _asset_download_url(asset)
    if not url:
        raise ValueError("The selected release asset does not include a download URL.")
    if not _download_host_allowed(url):
        raise ValueError("The selected release asset download URL is not hosted by GitHub.")
    if destination.exists() and _file_matches_asset(destination, asset):
        return False

    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".download", dir=str(destination.parent))
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with urllib.request.urlopen(request, timeout=60) as response, temp_path.open("wb") as handle:
            shutil.copyfileobj(response, handle)
        size = asset.get("size")
        if size is not None and int(size) > 0 and temp_path.stat().st_size != int(size):
            raise IOError(f"Downloaded size mismatch for {destination.name}.")
        digest = _expected_digest(asset)
        if digest and _sha256_file(temp_path).lower() != digest:
            raise IOError(f"Downloaded SHA-256 digest mismatch for {destination.name}.")
        temp_path.replace(destination)
        return True
    finally:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except Exception:
            pass


def _update_download_settings(tlo_home: str | os.PathLike[str] | None, latest_build: int, asset_name: str, path: Path, package_kind: str) -> None:
    if not tlo_home:
        return
    settings = load_update_settings(tlo_home)
    settings["last_check_utc"] = _utc_now().isoformat(timespec="seconds").replace("+00:00", "Z")
    settings["last_checked_build"] = int(latest_build)
    settings["last_downloaded_build"] = int(latest_build)
    settings["last_downloaded_asset"] = asset_name
    settings["last_downloaded_path"] = str(path)
    settings["last_downloaded_kind"] = package_kind
    try:
        save_update_settings(tlo_home, settings)
    except Exception:
        pass


def check_for_updates(
    tlo_home: str | os.PathLike[str] | None,
    *,
    manual: bool = True,
    owner: str = DEFAULT_REPO_OWNER,
    repo: str = DEFAULT_REPO_NAME,
) -> UpdateCheckResult:
    """Check the latest GitHub Release and download the preferred ZIP if newer.

    Manual and automatic checks share the same safe behavior: download only.
    The caller decides whether to show all statuses or suppress quiet auto-check
    statuses such as up-to-date.
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
            _write_last_check(tlo_home)
            return UpdateCheckResult(
                status="error",
                title="TLO update check failed",
                message="The latest GitHub Release did not contain a recognizable TLO build number.",
            )
        if latest_build <= BUNDLE_BUILD:
            _write_last_check(tlo_home, latest_build)
            return UpdateCheckResult(
                status="up_to_date",
                title="TLO is up to date",
                message=f"Installed: {DISPLAY_VERSION}\nLatest: v1.2 Build {latest_build}",
                latest_build=latest_build,
            )

        asset, package_kind, platform_key = _choose_asset(release, latest_build)
        if not asset:
            _write_last_check(tlo_home, latest_build)
            return UpdateCheckResult(
                status="no_asset",
                title="TLO update found, but no ZIP matched this platform",
                message=(
                    f"Installed: {DISPLAY_VERSION}\n"
                    f"Latest: v1.2 Build {latest_build}\n\n"
                    f"No update ZIP for {platform_key} and no complete ZIP were found in the latest GitHub Release."
                ),
                latest_build=latest_build,
            )

        asset_name = _asset_name(asset)
        destination = _downloads_dir() / _safe_asset_filename(asset_name)
        downloaded = _download_asset(asset, destination)
        _update_download_settings(tlo_home, latest_build, asset_name, destination, package_kind)
        if package_kind == "update":
            kind_text = "executable-only update"
            extra = "This ZIP does not contain your inventory, setlists, logs, or databases."
        else:
            kind_text = "complete distribution"
            extra = "This ZIP may include required support files. Review the release notes before replacing files in TLOHome."
        verification_note = "" if _expected_digest(asset) else "\n\nGitHub did not provide a SHA-256 digest for this asset; TLO verified the downloaded file size only."
        if downloaded:
            title = "TLO update downloaded"
            lead = f"TLO v1.2 Build {latest_build} {kind_text} was downloaded to:"
            status = "downloaded"
        else:
            title = "TLO update already downloaded"
            lead = f"TLO v1.2 Build {latest_build} {kind_text} is already available at:"
            status = "already_downloaded"
        return UpdateCheckResult(
            status=status,
            title=title,
            message=f"{lead}\n\n{destination}\n\n{extra}{verification_note}",
            latest_build=latest_build,
            path=str(destination),
            asset_name=asset_name,
            package_kind=package_kind,
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
