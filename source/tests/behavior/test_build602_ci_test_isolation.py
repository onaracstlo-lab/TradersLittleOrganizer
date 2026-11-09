"""Build 602: native CI shared-source override must not poison legacy upstream tests."""
from pathlib import Path
import hashlib
import re
import pytest

import ffmpeg_source_build as ff
from tests.behavior.test_build597_ffmpeg_source_download import _pin

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_legacy_upstream_test_setup_isolates_native_ci_environment(monkeypatch):
    monkeypatch.setenv('TLO_FFMPEG_SOURCE_ARCHIVE', '/missing/ffmpeg-9.0.2.tar.xz')
    _pin(monkeypatch, b'upstream fixture')
    assert 'TLO_FFMPEG_SOURCE_ARCHIVE' not in __import__('os').environ


def test_real_shared_source_override_still_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv('TLO_FFMPEG_SOURCE_ARCHIVE', str(tmp_path / ff.SOURCE_NAME))
    monkeypatch.setattr(ff, 'SOURCE_SHA256', hashlib.sha256(b'valid archive').hexdigest())
    with pytest.raises(RuntimeError, match='CI FFmpeg source artifact'):
        ff.get_source(tmp_path / 'cache')


def test_version_neutral_faq_does_not_break_legacy_contract():
    faq = (ROOT / 'TLO-FAQ.txt').read_text(encoding='utf8')
    assert 'GitHub native build-process note:' in faq
    assert 'The separately versioned TLO GitHub Build Process acquires' in faq
    assert 'TLO GitHub Build Process v122' not in faq
    assert not re.search(r'\bBuild\s+\d+\b', faq)
