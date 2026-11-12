"""Build 653: only GitHub-approved full releases may enter the updater."""
from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import tlo_github_updates as U
from tests import _release_artifacts as RA

pytestmark = pytest.mark.behavior


def _release(build: int, *, prerelease: object = False, draft: object = False) -> dict:
    return {
        "tag_name": f"v1.7-build{build}",
        "name": f"TLO v1.7 Build {build}",
        "prerelease": prerelease,
        "draft": draft,
        "assets": [{
            "name": f"TLO_V1.7Build{build}_update_Linux.zip",
            "browser_download_url": "https://github.com/onaracstlo-lab/TradersLittleOrganizer/releases/download/test/package.zip",
            "size": 123,
            "digest": "sha256:" + "a" * 64,
        }],
    }


@pytest.mark.parametrize("manual,download", [(True, True), (True, False), (False, False)])
@pytest.mark.parametrize("release_overrides", [
    {"prerelease": True},
    {"draft": True},
    {"prerelease": "false"},
    {"draft": "false"},
    {"missing_prerelease": True},
    {"missing_draft": True},
])
def test_unapproved_release_cannot_be_downloaded_or_offered(monkeypatch, tmp_path, manual, download, release_overrides):
    release = _release(U.BUNDLE_BUILD + 10)
    release_overrides = release_overrides.copy()
    if release_overrides.pop("missing_prerelease", False):
        release.pop("prerelease")
    if release_overrides.pop("missing_draft", False):
        release.pop("draft")
    release.update(release_overrides)
    monkeypatch.setattr(U, "_fetch_latest_release", lambda *_args: release)

    def forbidden(*args, **kwargs):
        raise AssertionError("Pre-release must be blocked BEFORE processing signed metadata/assets/downloads")

    monkeypatch.setattr(U, "_load_verified_release_metadata", forbidden)
    monkeypatch.setattr(U, "_matching_assets", forbidden)
    monkeypatch.setattr(U, "_download_and_report_verified_asset", forbidden)
    result = U.check_for_updates(tmp_path, manual=manual, download=download)
    assert result.status == "up_to_date"
    assert result.latest_build is None
    assert "not available" in result.message
    assert U.load_update_settings(tmp_path).get("last_checked_build") is None


def test_unapproved_lower_build_does_not_sneak_through_version_short_circuit(monkeypatch, tmp_path):
    monkeypatch.setattr(U, "_fetch_latest_release", lambda *_args: _release(U.BUNDLE_BUILD - 1, prerelease=True))
    result = U.check_for_updates(tmp_path, download=False)
    assert result.status == "up_to_date"
    assert result.latest_build is None
    assert "pre-releases" in result.message


def test_promoted_release_is_still_available_with_signed_verification(monkeypatch, tmp_path):
    build = U.BUNDLE_BUILD + 1
    release = _release(build)
    monkeypatch.setattr(U.sys, "platform", "linux")
    monkeypatch.setattr(U, "_fetch_latest_release", lambda *_args: release)
    monkeypatch.setattr(U, "_load_verified_release_metadata", lambda _release: {
        "schema": 1,
        "build": build,
        "release_tag": release["tag_name"],
        "assets": [{
            "name": release["assets"][0]["name"],
            "sha256": "a" * 64,
            "size": 123,
            "build": build,
            "kind": "update",
            "platform_key": "linux",
        }],
    })
    result = U.check_for_updates(tmp_path, manual=False, download=False)
    assert result.status == "available"
    assert result.latest_build == build
    assert result.asset_digest == "a" * 64


def test_latest_api_is_used_not_ordinal_or_highest_prerelease(monkeypatch):
    requested = []

    class FakeResponse(io.BytesIO):
        pass

    def fake_urlopen(request, timeout):
        requested.append((request.full_url, timeout))
        return FakeResponse(json.dumps(_release(U.BUNDLE_BUILD)).encode("utf-8"))

    monkeypatch.setattr(U.urllib.request, "urlopen", fake_urlopen)
    response = U._fetch_latest_release("onaracstlo-lab", "TradersLittleOrganizer")
    assert response["prerelease"] is False
    assert requested == [(
        "https://api.github.com/repos/onaracstlo-lab/TradersLittleOrganizer/releases/latest", 20,
    )]


def test_app_release_documentation_mentions_approval_gate():
    root = Path(__file__).resolve().parents[2]
    text = (root / RA.CHANGES_FILENAME).read_text(encoding="utf-8")
    assert "pre-release" in text.lower()
    assert "promot" in text.lower()
    assert "Build Process v126" in (root / RA.SOURCE_README_FILENAME).read_text(encoding="utf-8")
