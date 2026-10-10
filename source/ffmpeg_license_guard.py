"""Build-time, fail-closed FFmpeg redistribution policy for TLO.

This checks the exact executable bytes selected for bundling. It is not legal
advice or a substitute for a corresponding-source distribution review.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import argparse
import re
import subprocess
from pathlib import Path

FORBIDDEN = ('--enable-nonfree', '--enable-gpl', '--enable-version3')
REQUIRED = ('--disable-autodetect', '--disable-network', '--disable-ffplay', '--disable-ffprobe')
REQUIRED_DEMUXERS = ('shn', 'flac', 'wav', 'aiff', 'mp3', 'ogg', 'mov', 'ape', 'wv')
REQUIRED_DECODERS = ('shorten', 'flac', 'mp3', 'aac', 'alac', 'ape', 'wavpack', 'opus', 'vorbis')
REQUIRED_MUXERS = ('flac', 'null', 'framemd5')
REQUIRED_ENCODERS = ('flac', 'pcm_s16le')


def validate_version_output(output: str, *, require_audio_only: bool = False) -> None:
    lines = output.splitlines()
    if not lines or 'ffmpeg version 9.0.2' not in lines[0].lower():
        raise RuntimeError('Unapproved FFmpeg version (expected 9.0.2)')
    config = next((line for line in lines if line.strip().startswith('configuration:')), '')
    if not config:
        raise RuntimeError('FFmpeg configuration missing: reject unverifiable binary')
    flags = set(config.partition(':')[2].strip().split())
    for forbidden in FORBIDDEN:
        if forbidden in flags:
            raise RuntimeError('FFmpeg redistribution prohibited by flag ' + forbidden)
    if require_audio_only:
        missing = set(REQUIRED) - flags
        if missing:
            raise RuntimeError('FFmpeg missing audio-only restriction(s): ' + ', '.join(sorted(missing)))
        if '--disable-everything' not in flags:
            raise RuntimeError('FFmpeg is not an explicitly selected audio-only build')


def parse_component_names(output: str) -> set[str]:
    result = set()
    for line in output.splitlines():
        match = re.match(r'^\s*[ DAEVFS.]{1,8}\s+([a-z0-9_,]+)\s', line)
        if match:
            result.update(match.group(1).split(','))
    return result


def run_ffmpeg(executable: Path, *args: str) -> str:
    try:
        finished = subprocess.run(
            [str(executable), *args], stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
            timeout=35, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError('FFmpeg could not be independently executed') from exc
    if finished.returncode != 0:
        raise RuntimeError(f'FFmpeg check failed {args}: {finished.stdout[-700:]}')
    return finished.stdout


def verify(executable: Path, *, require_audio_only: bool = True) -> str:
    executable = Path(executable)
    if not executable.is_file():
        raise RuntimeError('FFmpeg executable not found: ' + str(executable))
    version = run_ffmpeg(executable, '-version')
    validate_version_output(version, require_audio_only=require_audio_only)
    license_out = run_ffmpeg(executable, '-L')
    if 'lesser general public license' not in license_out.lower():
        raise RuntimeError('FFmpeg -L did not establish LGPL terms')
    if 'not legally redistributable' in (version + license_out).lower():
        raise RuntimeError('FFmpeg explicitly reports unredistributable')
    if require_audio_only:
        for selector, required in (('-demuxers', REQUIRED_DEMUXERS), ('-decoders', REQUIRED_DECODERS),
                                   ('-muxers', REQUIRED_MUXERS), ('-encoders', REQUIRED_ENCODERS)):
            actual = parse_component_names(run_ffmpeg(executable, '-hide_banner', selector))
            missing = sorted(set(required) - actual)
            if missing:
                raise RuntimeError(f'FFmpeg {selector} omits required audio components: {missing}')
    return version.splitlines()[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('executable', type=Path)
    parser.add_argument('--allow-generic', action='store_true', help='Build 571 legacy inspection only, never for release')
    args = parser.parse_args()
    print(verify(args.executable, require_audio_only=not args.allow_generic))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
