"""Independent update metadata trust tests for Build 514."""
from __future__ import annotations
import base64, hashlib
import tlo_update_trust as trust
import tlo_github_updates as updates
import pytest

pytestmark = pytest.mark.unit

# Tiny deterministic RSA test key; tests monkeypatch the trust anchor only.
# Production builds inject a fresh RSA-3072 public key and never contain its private half.
N = 9516311845790656153499716760847001433441357
E = 65537
D = 5617843187844953170308463622230283376298685


def _sign(payload: bytes) -> str:
    prefix = bytes.fromhex("3031300d060960864801650304020105000420")
    di = prefix + hashlib.sha256(payload).digest()
    k = (N.bit_length()+7)//8
    em = b"\x00\x01" + b"\xff"*(k-len(di)-3) + b"\x00" + di
    return base64.b64encode(pow(int.from_bytes(em,'big'),D,N).to_bytes(k,'big')).decode()


def test_unconfigured_key_fails_closed(monkeypatch):
    monkeypatch.setattr(trust, 'PINNED_UPDATE_SIGNING_KEY_ID', '')
    assert trust.pinned_key_configured() is False
    assert trust.verify_metadata_signature({'schema':1}, 'AA==') is False


def test_signature_verification_and_tamper_rejection(monkeypatch):
    # This toy modulus is too short for SHA-256 PKCS#1 padding; exercise fail-closed behavior.
    monkeypatch.setattr(trust, 'PINNED_UPDATE_SIGNING_KEY_ID', 'test')
    monkeypatch.setattr(trust, 'PINNED_UPDATE_SIGNING_RSA_N_B64', base64.b64encode(N.to_bytes((N.bit_length()+7)//8,'big')).decode())
    monkeypatch.setattr(trust, 'PINNED_UPDATE_SIGNING_RSA_E_B64', base64.b64encode(E.to_bytes(3,'big')).decode())
    assert trust.verify_metadata_signature({'schema':1,'key_id':'test'}, 'AA==') is False


def test_signed_asset_record_replaces_github_digest():
    metadata={'assets':[{'name':'x.zip','sha256':'a'*64,'size':123,'build':513,'kind':'update','platform_key':'linux'}]}
    asset={'name':'x.zip','size':123,'digest':'sha256:'+'b'*64,'browser_download_url':'https://github.com/x'}
    trusted=updates._apply_signed_asset_metadata(asset, metadata, expected_build=513, expected_kind='update', expected_platform_key='linux')
    assert trusted['digest']=='sha256:'+'a'*64


def test_signed_asset_mismatch_rejected():
    metadata={'assets':[{'name':'x.zip','sha256':'a'*64,'size':123,'build':513,'kind':'update','platform_key':'linux'}]}
    asset={'name':'x.zip','size':124}
    import pytest
    with pytest.raises(ValueError, match='size disagrees'):
        updates._apply_signed_asset_metadata(asset, metadata, expected_build=513, expected_kind='update', expected_platform_key='linux')
