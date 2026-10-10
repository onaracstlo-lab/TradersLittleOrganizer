"""Independent FFmpeg redistribution policy regressions."""
import pytest

pytestmark = pytest.mark.behavior
from ffmpeg_license_guard import validate_version_output, parse_component_names


def _version(*flags):
    return 'ffmpeg version 9.0.2 Copyright (c) FFmpeg\nconfiguration: ' + ' '.join(flags) + '\n'


def test_reject_nonfree_and_gpl():
    for flag in ('--enable-nonfree', '--enable-gpl', '--enable-version3'):
        with pytest.raises(RuntimeError, match='prohibited'):
            validate_version_output(_version(flag))


def test_reject_missing_configuration():
    with pytest.raises(RuntimeError, match='configuration'):
        validate_version_output('ffmpeg version 9.0.2\n')


def test_reject_other_versions():
    with pytest.raises(RuntimeError, match='version'):
        validate_version_output('ffmpeg version 9.0.1\nconfiguration: --disable-network\n')


def test_only_full_explicit_restriction_allowed():
    flags = ('--disable-autodetect', '--disable-network', '--disable-ffplay',
             '--disable-ffprobe', '--disable-everything')
    validate_version_output(_version(*flags), require_audio_only=True)
    for flag in flags:
        with pytest.raises(RuntimeError):
            validate_version_output(_version(*(x for x in flags if x != flag)), require_audio_only=True)


def test_components_parse():
    found = parse_component_names(' D  shn        Shorten\n A....D flac      FLAC\n D  mov,mp4,m4a QuickTime\n')
    assert {'shn', 'flac', 'mov', 'mp4', 'm4a'} <= found
