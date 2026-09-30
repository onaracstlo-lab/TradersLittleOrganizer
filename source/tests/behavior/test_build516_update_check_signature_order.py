"""Build 516: older/equal releases do not require signed update metadata."""
from __future__ import annotations

import pytest

import tlo_github_updates as updates

pytestmark = pytest.mark.behavior


def _release(build: int) -> dict:
    return {
        "tag_name": f"v1.7-build{build}",
        "name": f"TLO v1.7 Build {build}",
        "assets": [],
    }


def test_older_unsigned_latest_release_is_not_an_update_security_error(monkeypatch, tmp_path):
    installed = updates.BUNDLE_BUILD
    older = installed - 2
    monkeypatch.setattr(updates, "_fetch_latest_release", lambda owner, repo: _release(older))

    def must_not_verify(_release_value):
        raise AssertionError("Older releases must be rejected by build comparison before signature verification")

    monkeypatch.setattr(updates, "_load_verified_release_metadata", must_not_verify)
    result = updates.check_for_updates(tmp_path / "TLOHome", manual=True, download=False)

    assert result.status == "up_to_date"
    assert result.latest_build == older
    assert f"Installed: {updates.DISPLAY_VERSION}" in result.message
    assert f"Latest published GitHub release: v{updates.PUBLIC_VERSION} Build {older}" in result.message
    assert "No newer TLO release is available." in result.message


def test_equal_unsigned_latest_release_is_not_an_update_security_error(monkeypatch, tmp_path):
    installed = updates.BUNDLE_BUILD
    monkeypatch.setattr(updates, "_fetch_latest_release", lambda owner, repo: _release(installed))

    def must_not_verify(_release_value):
        raise AssertionError("The installed release does not need update-authorization verification")

    monkeypatch.setattr(updates, "_load_verified_release_metadata", must_not_verify)
    result = updates.check_for_updates(tmp_path / "TLOHome", manual=True, download=False)

    assert result.status == "up_to_date"
    assert result.latest_build == installed


def test_newer_release_still_requires_independent_signature(monkeypatch, tmp_path):
    newer = updates.BUNDLE_BUILD + 1
    monkeypatch.setattr(updates, "_fetch_latest_release", lambda owner, repo: _release(newer))
    monkeypatch.setattr(
        updates,
        "_load_verified_release_metadata",
        lambda release: (_ for _ in ()).throw(ValueError("unsigned newer release refused")),
    )

    result = updates.check_for_updates(tmp_path / "TLOHome", manual=True, download=False)

    assert result.status == "error"
    assert result.latest_build is None
    assert "unsigned newer release refused" in result.message
