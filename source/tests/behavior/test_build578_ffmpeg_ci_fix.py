"""Build 578: evidence-driven GitHub host and Shorten component regressions."""
from pathlib import Path
import pytest

import ffmpeg_source_build as build
import ffmpeg_license_guard as guard
import tlo_version as version
from tests import _release_artifacts as RA

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_shorten_configure_symbol_and_runtime_name_are_both_preserved():
    assert 'shorten' in build.AUDIO_DEMUXERS
    assert 'shn' not in build.AUDIO_DEMUXERS
    assert 'shorten' in build.AUDIO_DECODERS
    assert '--enable-demuxer=shorten' in build.CONFIGURE_FLAGS
    assert 'shn' in guard.REQUIRED_DEMUXERS
    assert 'shorten' in guard.REQUIRED_DECODERS
    recipe = (ROOT / 'build_audio_ffmpeg.sh').read_text(encoding='utf-8')
    assert '--enable-demuxer=shorten,flac' in recipe
    assert '--enable-decoder=shorten,flac' in recipe
    assert '--enable-demuxer=shn' not in recipe


def test_msys2_shell_avoids_first_use_login_profile():
    source = (ROOT / 'ffmpeg_source_build.py').read_text(encoding='utf-8')
    assert "'/ucrt64/bin:/usr/bin:/bin'" not in source  # must be part of explicit PATH
    assert 'export PATH=/ucrt64/bin:/usr/bin:/bin:$PATH' in source
    assert '. /etc/profile' not in source
    assert 'command -v gcc' in source
    assert 'exec bash "$@"' in source  # paths remain distinct arguments


def test_versioned_manual_title_and_lint_evidence():
    rtf = (ROOT / RA.MANUAL_FILENAME).read_text(encoding='utf-8')
    assert rf'\title TLO Inventory User Manual {version.VERSION}' in rtf
    assert rf'\subject TLO {version.DISPLAY_VERSION} end-user manual' in rtf
    report = (ROOT / RA.BUILD_VERIFICATION_FILENAME).read_text(encoding='utf-8')
    assert 'Ruff lint:' in report
    assert 'lint not attested' in report
    assert 'NOT RELEASE-ATTESTED' in report
