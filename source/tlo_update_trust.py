"""Independent trust anchor and RSA-SHA256 verification for TLO release metadata.

The public key is injected into this file by the trusted local release build.
The private key never belongs in source control, GitHub Actions, or release assets.
"""
from __future__ import annotations

import base64
import hashlib
import json
from typing import Any

__version__ = "v514"

# Replaced by Run-TLO-GitHub-Build.ps1 from a locally generated public-key JSON.
# Empty values deliberately fail closed: unsigned/unpinned updates are never accepted.
PINNED_UPDATE_SIGNING_KEY_ID = ""
PINNED_UPDATE_SIGNING_RSA_N_B64 = ""
PINNED_UPDATE_SIGNING_RSA_E_B64 = ""

_SHA256_DIGESTINFO_PREFIX = bytes.fromhex("3031300d060960864801650304020105000420")


def pinned_key_configured() -> bool:
    return bool(PINNED_UPDATE_SIGNING_KEY_ID and PINNED_UPDATE_SIGNING_RSA_N_B64 and PINNED_UPDATE_SIGNING_RSA_E_B64)


def canonical_metadata_bytes(metadata: dict[str, Any]) -> bytes:
    """Return the exact deterministic UTF-8 representation used for signatures."""
    return (json.dumps(metadata, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def verify_metadata_signature(metadata: dict[str, Any], signature_b64: str) -> bool:
    """Verify RSA PKCS#1 v1.5 / SHA-256 using only the pinned public key."""
    if not pinned_key_configured() or str(metadata.get("key_id") or "") != PINNED_UPDATE_SIGNING_KEY_ID:
        return False
    try:
        n = int.from_bytes(base64.b64decode(PINNED_UPDATE_SIGNING_RSA_N_B64, validate=True), "big")
        e = int.from_bytes(base64.b64decode(PINNED_UPDATE_SIGNING_RSA_E_B64, validate=True), "big")
        signature = base64.b64decode(str(signature_b64 or ""), validate=True)
    except Exception:
        return False
    if n <= 0 or e <= 1:
        return False
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    encoded = pow(int.from_bytes(signature, "big"), e, n).to_bytes(k, "big")
    digest_info = _SHA256_DIGESTINFO_PREFIX + hashlib.sha256(canonical_metadata_bytes(metadata)).digest()
    padding_len = k - len(digest_info) - 3
    if padding_len < 8:
        return False
    expected = b"\x00\x01" + (b"\xff" * padding_len) + b"\x00" + digest_info
    return encoded == expected
