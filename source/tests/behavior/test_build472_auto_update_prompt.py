"""Build 472: Auto Update discovers first and downloads only after Yes."""

__version__ = "v472"

from pathlib import Path

import pytest

import tlo_github_updates as updates

pytestmark = pytest.mark.behavior


def _asset(build: int) -> dict:
    return {
        "name": f"TLO_V1.7Build{build}_update_Linux.zip",
        "browser_download_url": "https://github.com/example/TLO/releases/download/test/update.zip",
        "size": 123,
        "digest": "sha256:" + ("a" * 64),
    }


def test_auto_discovery_returns_available_without_downloading(monkeypatch, tmp_path):
    build = updates.BUNDLE_BUILD + 1
    release = {
        "tag_name": f"v1.7-build{build}",
        "name": f"TLO v1.7 Build {build}",
        "assets": [_asset(build)],
    }
    monkeypatch.setattr(updates.sys, "platform", "linux")
    monkeypatch.setattr(updates, "_fetch_latest_release", lambda owner, repo: release)

    def must_not_download(*args, **kwargs):
        raise AssertionError("Auto Update discovery must not download before the user says Yes")

    monkeypatch.setattr(updates, "_download_asset", must_not_download)
    result = updates.check_for_updates(tmp_path / "TLOHome", manual=False, download=False)

    assert result.status == "available"
    assert result.latest_build == build
    assert result.asset_name.endswith("_update_Linux.zip")
    assert result.asset_url.startswith("https://github.com/")
    assert result.asset_digest == "a" * 64
    assert "Download it to your Downloads folder?" in result.message
    settings = updates.load_update_settings(tmp_path / "TLOHome")
    assert settings["last_checked_build"] == build
    assert "last_downloaded_build" not in settings


def test_yes_path_downloads_pending_verified_asset(monkeypatch, tmp_path):
    build = updates.BUNDLE_BUILD + 1
    pending = updates.UpdateCheckResult(
        status="available",
        title="TLO update available",
        message="available",
        latest_build=build,
        asset_name=f"TLO_V1.7Build{build}_update_Linux.zip",
        package_kind="update",
        platform_key="linux",
        asset_url="https://github.com/example/TLO/releases/download/test/update.zip",
        asset_size=123,
        asset_digest="b" * 64,
    )
    monkeypatch.setattr(updates, "_downloads_dir", lambda: tmp_path / "Downloads")
    calls = []

    def fake_download(asset, destination):
        calls.append((asset, destination))
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"fake package")
        return True

    monkeypatch.setattr(updates, "_download_asset", fake_download)
    monkeypatch.setattr(
        updates,
        "_inspect_downloaded_package",
        lambda path, **kwargs: {
            "kind": "update",
            "platform_key": "linux",
            "packaging_mode": "native",
            "databases_included": False,
        },
    )

    result = updates.download_update(pending, tmp_path / "TLOHome")

    assert result.status == "downloaded"
    assert len(calls) == 1
    asset, destination = calls[0]
    assert destination.parent == tmp_path / "Downloads"
    assert asset["digest"] == "sha256:" + ("b" * 64)
    assert result.path == str(destination)


def test_gui_auto_update_contract_uses_yes_skip_and_discovery_only():
    root = Path(__file__).resolve().parents[2]
    for name in ("tlo-ggi.py", "tlo-gsi.py"):
        text = (root / name).read_text(encoding="utf-8")
        assert 'text="Yes"' in text
        assert 'text="Skip"' in text
        assert "download=manual" in text
        assert "download_update(" in text
        assert "ask before downloading a newer release ZIP" in text
