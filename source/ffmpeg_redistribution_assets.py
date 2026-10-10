"""Place corresponding upstream FFmpeg source and legal notices in native dist.

FFmpeg is a separate LGPL-licensed executable, not linked to TLO. The exact
upstream tarball (SHA256-pinned) and compilation recipe accompany each package.
This does not remove the need for counsel to review all LGPL obligations.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION
import argparse
import hashlib
import shutil
from pathlib import Path
from ffmpeg_source_build import SOURCE_NAME, SOURCE_SHA256, get_source
from ffmpeg_license_guard import verify


def attach(dist: Path, binary: Path, cache: Path, *, build_recipe: Path) -> None:
    verify(binary, require_audio_only=True)
    tar = get_source(cache)
    if not build_recipe.is_file():
        raise RuntimeError('FFmpeg corresponding build recipe missing')
    root = dist / 'THIRD_PARTY' / 'FFmpeg'
    root.mkdir(parents=True, exist_ok=True)
    shutil.copy2(tar, root / SOURCE_NAME)
    shutil.copy2(build_recipe, root / build_recipe.name)
    notice = (Path(__file__).resolve().parent / 'FFMPEG_LGPL_NOTICE.txt')
    license_file = (Path(__file__).resolve().parent / 'COPYING.LGPLv2.1')
    for source in (notice, license_file):
        if not source.is_file():
            raise RuntimeError('Required FFmpeg legal notice is missing: ' + str(source))
        shutil.copy2(source, root / source.name)
    binary_hash = hashlib.sha256(binary.read_bytes()).hexdigest()
    (root / 'BUILD_PROVENANCE.txt').write_text(
        'TLO FFmpeg 9.0.2 source build\n'
        'Upstream source: https://ffmpeg.org/releases/' + SOURCE_NAME + '\n'
        'Source SHA-256: ' + SOURCE_SHA256 + '\n'
        'Pre-sign native FFmpeg binary SHA-256: ' + binary_hash + '\n'
        'License: LGPL v2.1 or later (no --enable-gpl/nonfree/version3)\n'
        'Exact configure flags: see build_audio_ffmpeg.sh and ffmpeg -version\n'
        'Source and build instructions in this THIRD_PARTY directory.\n', encoding='utf-8')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--dist', required=True, type=Path)
    p.add_argument('--binary', required=True, type=Path)
    p.add_argument('--cache', required=True, type=Path)
    p.add_argument('--recipe', type=Path, default=Path(__file__).with_name('build_audio_ffmpeg.sh'))
    args = p.parse_args()
    attach(args.dist, args.binary, args.cache, build_recipe=args.recipe)


if __name__ == '__main__':
    main()
