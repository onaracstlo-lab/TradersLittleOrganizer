"""Build FFmpeg 9.0.2 from pinned upstream source; reject all nonfree binaries.

FFmpeg is NOT fetched as a prebuilt release asset. All three native platforms
use the same auditable audio-only build recipe. There is no PATH fallback.
"""
from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import argparse
import platform
import sys
from pathlib import Path

from ffmpeg_source_build import FFMPEG_VERSION, prepare_source_build, SOURCE_NAME
from ffmpeg_license_guard import verify


def _normalize_platform(value=None):
    raw = (value or sys.platform).lower()
    if raw.startswith('linux'): return 'linux'
    if raw.startswith('darwin') or raw in {'macos','mac','osx'}: return 'macos'
    if raw.startswith('win') or raw == 'windows': return 'windows'
    raise RuntimeError(f'Unsupported FFmpeg platform {raw}')


def _normalize_arch(value=None):
    raw = (value or platform.machine()).lower().replace('-', '_')
    mapping = {'x86_64':'x64','amd64':'x64','x64':'x64','aarch64':'arm64',
               'arm64':'arm64','universal2':'universal2','x86':'x86'}
    if raw not in mapping: raise RuntimeError('Unsupported FFmpeg CPU architecture: ' + raw)
    return mapping[raw]


def prepare(output_dir: Path, *, target_platform: str, arch: str, cache_dir: Path):
    output_dir = Path(output_dir).resolve()
    cache_dir = Path(cache_dir).resolve()
    host = _normalize_platform()
    if target_platform != host:
        raise RuntimeError('FFmpeg source compilation requires a real native ' + target_platform + ' host')
    native_arch = _normalize_arch()
    if arch != native_arch:
        raise RuntimeError(f'FFmpeg native arch mismatch: requested {arch}, host {native_arch}')
    if arch not in {'x64', 'arm64'}:
        raise RuntimeError('FFmpeg architecture not qualified for source build: ' + arch)
    basename = 'ffmpeg.exe' if target_platform == 'windows' else 'ffmpeg'
    output = output_dir / basename
    recipe = Path(__file__).resolve().with_name('build_audio_ffmpeg.sh')
    built = prepare_source_build(output, cache_dir, platform_name=target_platform,
                                 recipe=recipe, build_root=cache_dir / 'native-compile')
    return built, verify(built, require_audio_only=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--cache-dir', default='')
    parser.add_argument('--platform', dest='target_platform', default='')
    parser.add_argument('--arch', default='')
    args = parser.parse_args(argv)
    target_platform = _normalize_platform(args.target_platform or None)
    arch = _normalize_arch(args.arch or None)
    output = Path(args.output_dir)
    cache = Path(args.cache_dir) if args.cache_dir else output.parent / '.ffmpeg-cache'
    built, line = prepare(output, target_platform=target_platform, arch=arch, cache_dir=cache)
    print('Prepared LGPL audio-only FFmpeg from verified source:', built)
    print(line)
    print('Verified FFmpeg version:', FFMPEG_VERSION)
    print('Verified source:', cache / SOURCE_NAME)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
