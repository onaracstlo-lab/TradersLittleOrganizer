"""Build 542 update-trust assurance and packaged-ffmpeg containment regressions."""

from __future__ import annotations

import base64
import hashlib
import io
import os
import zipfile

import pytest

import tlo_ffmpeg as FF
import tlo_github_updates as U
import tlo_update_trust as trust

pytestmark = pytest.mark.behavior

# Fixed RSA-3072 verification vector. The private key used to create this signature
# was generated once for the regression fixture and is not part of the source tree.
KEY_ID = "build542-test"
RSA_N_B64 = (
    "w48pwmuPmjj+fk8agchmqe7UJL+g7gn5JDLXILAQ5F54Wyp2QTHqpUUuBGbuQ9dv16HMDzVY2BAYsFNfDBCT9vopCQJEkSFSjtqfDTF6XLF6oDuhy3anH2OeShoggsjfvXi0OsuDuETt1VwxGUGqcpXT4pBFCFJHWqgOr/khKC+0bScavvKwEwsUHFSU3qkJDot5FyeP/vriyKDANeAg37x8CnRICDF+9QaDz3MDGOklHfGqVNlGR7juzO86IgUJjvwkaDMS7O2+MqjLiA45WTwrD2aJMV0P9lS8+u+5rW0tmsexnKGolsYmZkb2OXAv0zJBWiAe2Mo68tJ8DrOX9XVK6ADvBpOh6esVUQ224joJxQ2UBL5SgoAOiXR3BlFgtnq/FXDGLjg+uRZqcUAcDR6JXQ05FC4FQzNjEnA+ZY4hHp6xVI3M0R+cc/kcUKK0Lkv/VQFoCv5anDQvIFYQj5vUWL7bc0wGugxKxKe4kmI0cBRTeNIJ0nsdi2zj/pgJ"
)
RSA_E_B64 = "AQAB"
VALID_SIGNATURE_B64 = (
    "flnICs78u5LECpjvS9MTQTsErUskRW6g6AY+vR5vjwxgwJ6qj1cLkRHPbazgGgQKASI09KKEYg0CQqfacjAvXOJxIxhlDA+EsUvep5Ey3djGYYCbG3iG77keJ6C/xv06hammPfpudaWVzqghiOhTItfS/tFTpdzj0ef1nV8Rkb8Ib3PgZsvyaAjKLscutCNGok+vwdgyBUNAhrx8guAUpo6bx7ucyHqiRJRBwvAHXpqsIYkImlmAL186vB2rkEm/A6K23c8htqQazeELhaqWpl5hrP4I9lzPIP8T+/RpvnRSzcvLX2mVvfeB6RSPgUCWSPRB25zFfO/Dt/crW3TCEyHoEeSwhCey+zY8bNTiOUH3SMeG11heLhn72lv0N/Dr2wJq+yHWwaR+fGamKn0FiJxseNyXMhlGrv1FWzFGeh5p+CY72YL2LMB02Nynm0WwfiAltr/Yn+1SL7G6BEwQ40YnL/4ngeWuBxVI5wy6hAMtWmhVovEpPqIWqjeArXqG"
)
VALID_METADATA = {
    "schema": 1,
    "key_id": KEY_ID,
    "build": 542,
    "release_tag": "v1.7-build542-test",
    "assets": [
        {
            "name": "TLO_V1.7Build542_update_Linux.zip",
            "sha256": "3" * 64,
            "size": 12345,
            "build": 542,
            "kind": "update",
            "platform_key": "linux",
        }
    ],
}


def _install_test_public_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(trust, "PINNED_UPDATE_SIGNING_KEY_ID", KEY_ID)
    monkeypatch.setattr(trust, "PINNED_UPDATE_SIGNING_RSA_N_B64", RSA_N_B64)
    monkeypatch.setattr(trust, "PINNED_UPDATE_SIGNING_RSA_E_B64", RSA_E_B64)


def test_build542_real_rsa3072_signature_vector_and_tamper_rejection(monkeypatch):
    _install_test_public_key(monkeypatch)
    assert trust.verify_metadata_signature(VALID_METADATA, VALID_SIGNATURE_B64) is True

    signature = bytearray(base64.b64decode(VALID_SIGNATURE_B64))
    signature[-1] ^= 0x01
    assert trust.verify_metadata_signature(VALID_METADATA, base64.b64encode(signature).decode("ascii")) is False

    changed = dict(VALID_METADATA)
    changed["build"] = 543
    assert trust.verify_metadata_signature(changed, VALID_SIGNATURE_B64) is False

    wrong_key = dict(VALID_METADATA)
    wrong_key["key_id"] = "wrong-key"
    assert trust.verify_metadata_signature(wrong_key, VALID_SIGNATURE_B64) is False

    modulus = base64.b64decode(RSA_N_B64)
    assert len(modulus) == len(base64.b64decode(VALID_SIGNATURE_B64))
    assert trust.verify_metadata_signature(VALID_METADATA, base64.b64encode(modulus).decode("ascii")) is False


class _FakeResponse(io.BytesIO):
    def __init__(self, payload: bytes):
        super().__init__(payload)
        self.headers = {"Content-Length": str(len(payload))}


def test_build542_download_rejects_sha256_mismatch_without_destination(monkeypatch, tmp_path):
    expected = b"expected"
    received = b"tampered"
    assert len(expected) == len(received)
    asset = {
        "name": "TLO_V1.7Build543_update_Linux.zip",
        "browser_download_url": "https://github.com/example/update.zip",
        "size": len(received),
        "digest": "sha256:" + hashlib.sha256(expected).hexdigest(),
    }
    monkeypatch.setattr(U, "_open_download_url", lambda *_args, **_kwargs: _FakeResponse(received))
    destination = tmp_path / asset["name"]

    with pytest.raises(IOError, match="digest mismatch"):
        U._download_asset(asset, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob("*.download"))


def test_build542_check_for_updates_rejects_signed_release_tag_mismatch(monkeypatch, tmp_path):
    from tlo_version import BUNDLE_BUILD

    next_build = BUNDLE_BUILD + 1
    release = {"tag_name": f"v1.7 Build {next_build}", "name": f"TLO v1.7 Build {next_build}", "assets": []}
    monkeypatch.setattr(U, "_fetch_latest_release", lambda *_args, **_kwargs: release)
    monkeypatch.setattr(
        U,
        "_load_verified_release_metadata",
        lambda _release: {"schema": 1, "key_id": KEY_ID, "build": next_build, "release_tag": "v1.7 Build 999", "assets": []},
    )

    result = U.check_for_updates(tmp_path, download=False)
    assert result.status == "error"
    assert "release tag does not match" in result.message


@pytest.mark.parametrize("member", ["../evil.txt", "apps/../../evil.txt"])
def test_build542_zip_parent_traversal_is_rejected_for_the_right_reason(tmp_path, member):
    package = tmp_path / "traversal.zip"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(member, b"evil")
    with zipfile.ZipFile(package, "r") as archive:
        with pytest.raises(ValueError, match="parent traversal"):
            U._validate_zip_members(archive)


def test_build542_ffmpeg_symlinked_bundle_directory_cannot_escape_packaged_root(monkeypatch, tmp_path):
    root = tmp_path / "app"
    outside = tmp_path / "outside" / "tlo_ffmpeg_bin"
    root.mkdir()
    outside.mkdir(parents=True)
    binary = outside / FF._FFMPEG_BASENAME
    binary.write_bytes(b"ffmpeg")
    if os.name != "nt":
        binary.chmod(0o755)
    link = root / "tlo_ffmpeg_bin"
    try:
        link.symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"directory symlinks unavailable on this platform: {exc}")

    monkeypatch.setattr(FF, "_candidate_roots", lambda: [str(root)])
    assert FF.bundled_ffmpeg_executable() == ""
