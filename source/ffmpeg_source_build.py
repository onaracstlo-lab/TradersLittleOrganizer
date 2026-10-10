"""Reproducible, fail-closed FFmpeg 9.0.2 audio-only source build for TLO.

Native builds obtain the official source tarball with a public SHA-256 pin.
No prebuilt FFmpeg is downloaded or accepted. On Windows this module uses
MSYS2/UCRT64 Bash and a native GCC. On Linux/macOS it invokes system Bash.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import hashlib
import os
import stat
import subprocess
import tarfile
import urllib.request
from pathlib import Path

FFMPEG_VERSION = '9.0.2'
SOURCE_NAME = f'ffmpeg-{FFMPEG_VERSION}.tar.xz'
SOURCE_URL = f'https://ffmpeg.org/releases/{SOURCE_NAME}'
SOURCE_SHA256 = '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e'
MAX_SOURCE_DOWNLOAD_BYTES = 64 * 1024 * 1024
MAX_SOURCE_EXPANDED_BYTES = 512 * 1024 * 1024

# The configure component is 'shorten' (CONFIG_SHORTEN_DEMUXER),
# but ff_shorten_demuxer advertises the runtime input format name 'shn'.
AUDIO_DEMUXERS = ('shorten', 'flac', 'wav', 'aiff', 'mp3', 'ogg', 'mov', 'ape', 'wv', 'aac', 'asf', 'matroska', 'au', 'caf', 'tta', 'tak')
AUDIO_DECODERS = ('shorten', 'flac', 'mp3', 'aac', 'alac', 'ape', 'wavpack', 'opus', 'vorbis',
                  'wmav1', 'wmav2', 'tta', 'tak', 'pcm_s16le', 'pcm_s24le', 'pcm_s32le',
                  'pcm_s16be', 'pcm_s24be', 'pcm_s32be', 'pcm_u8', 'pcm_f32le', 'pcm_f64le')
AUDIO_ENCODERS = ('flac', 'pcm_s16le')
AUDIO_MUXERS = ('flac', 'null', 'framemd5')
AUDIO_PARSERS = ('aac', 'flac', 'mpegaudio', 'opus', 'vorbis')
AUDIO_FILTERS = ('abuffer', 'abuffersink', 'anull', 'aresample', 'aformat')
PROTOCOLS = ('file', 'pipe')

CONFIGURE_FLAGS = (
    '--disable-autodetect', '--disable-everything', '--enable-small',
    '--disable-network', '--disable-ffplay', '--disable-ffprobe',
    '--disable-doc', '--disable-debug', '--disable-avdevice',
    '--disable-swscale', '--disable-iconv', '--disable-bzlib', '--disable-lzma',
    '--disable-zlib', '--disable-x86asm', '--enable-ffmpeg',
    '--enable-static', '--disable-shared',
    *('--enable-demuxer=' + d for d in AUDIO_DEMUXERS),
    *('--enable-decoder=' + d for d in AUDIO_DECODERS),
    *('--enable-encoder=' + e for e in AUDIO_ENCODERS),
    *('--enable-muxer=' + m for m in AUDIO_MUXERS),
    *('--enable-parser=' + p for p in AUDIO_PARSERS),
    *('--enable-filter=' + f for f in AUDIO_FILTERS),
    *('--enable-protocol=' + p for p in PROTOCOLS),
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def get_source(cache: Path) -> Path:
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / SOURCE_NAME
    if not archive.is_file():
        temp = archive.with_suffix('.downloading')
        try:
            with urllib.request.urlopen(SOURCE_URL, timeout=90) as response, temp.open('wb') as out:
                count = 0
                for block in iter(lambda: response.read(1024 * 1024), b''):
                    count += len(block)
                    if count > MAX_SOURCE_DOWNLOAD_BYTES:
                        raise RuntimeError('FFmpeg source exceeds allowed download size')
                    out.write(block)
            os.replace(temp, archive)
        finally:
            temp.unlink(missing_ok=True)
    if sha256(archive) != SOURCE_SHA256:
        raise RuntimeError('FFmpeg upstream source SHA-256 mismatch; refusing build')
    return archive


def extract_source(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination / f'ffmpeg-{FFMPEG_VERSION}'
    if (root / 'configure').is_file():
        return root
    with tarfile.open(archive, 'r:xz') as tar:
        members = tar.getmembers()
        total = 0
        for item in members:
            parts = Path(item.name).parts
            if not parts or parts[0] != f'ffmpeg-{FFMPEG_VERSION}' or '..' in parts or item.name.startswith('/') or not (item.isfile() or item.isdir()):
                raise RuntimeError(f'FFmpeg tar member violates safe extraction policy: {item.name!r}')
            total += max(item.size, 0)
            if total > MAX_SOURCE_EXPANDED_BYTES:
                raise RuntimeError('FFmpeg source expansion budget exceeded')
        # Confirmed safe only regular files and directories with fixed top-level prefix.
        tar.extractall(destination, members=members, filter='data')
    if not (root / 'configure').is_file():
        raise RuntimeError('FFmpeg source archive did not contain configure')
    return root


def _cygpath(bash: Path, path: Path) -> str:
    """Convert one Windows path without invoking MSYS2 login/profile scripts.

    Login shells can print first-run profile setup text to stdout. Such text
    must NEVER become part of a path passed to a compiler/build script.
    """
    cygpath = bash.with_name('cygpath.exe')
    if not cygpath.is_file():
        raise RuntimeError(f'MSYS2 cygpath.exe missing: {cygpath}')
    result = subprocess.run([str(cygpath), '-u', str(path)],
                            capture_output=True, text=True, timeout=30, check=True)
    lines = result.stdout.splitlines()
    if len(lines) != 1 or not lines[0].startswith('/') or any(
        ord(c) < 32 or ord(c) == 127 for c in lines[0]
    ):
        raise RuntimeError('MSYS2 path conversion produced invalid or non-path output')
    return lines[0]


def _windows_msys2_bash(explicit: Path | None = None) -> Path:
    """Use the Bash executable belonging to the installed MSYS2 toolchain.

    setup-msys2 may install into the GitHub RUNNER_TEMP directory instead
    of C:\\msys64. Never silently substitute a different preinstalled MSYS2
    instance for the one in which the CI action installed Make and UCRT GCC.
    """
    if explicit is not None:
        return Path(explicit)
    configured = os.environ.get('TLO_MSYS2_BASH', '').strip()
    if configured:
        return Path(configured)
    if os.environ.get('GITHUB_ACTIONS', '').lower() == 'true':
        raise RuntimeError('GitHub Actions must export TLO_MSYS2_BASH from the setup-msys2 msys2-location output')
    # Local Windows builds without setup-msys2 may use the standard installation.
    return Path(r'C:\msys64\usr\bin\bash.exe')


def build(source_root: Path, output: Path, *, platform_name: str, build_root: Path,
          recipe: Path, bash: Path | None = None) -> Path:
    if not recipe.is_file():
        raise RuntimeError('Auditable FFmpeg build recipe is missing')
    if platform_name == 'windows':
        bash = _windows_msys2_bash(bash)
        if not bash.is_file():
            raise RuntimeError(f'Native Windows FFmpeg build requires installed MSYS2 UCRT64 Bash: {bash}')
        env = os.environ.copy()
        env['MSYSTEM'] = 'UCRT64'
        source_arg, output_arg, build_arg, recipe_arg = (
            _cygpath(bash, p.absolute()) for p in (source_root, output, build_root, recipe)
        )
        # Non-login shell avoids first-run skeleton-file text contaminating paths.
        # Select UCRT64 GCC explicitly without sourcing /etc/profile (which may exit
        # nonzero during MSYS2 first-use initialization). Pass argv positions
        # directly to the recipe (no shell interpolation of filesystem paths).
        command = [str(bash), '-c',
                   'set -e; export PATH=/ucrt64/bin:/usr/bin:/bin:$PATH; '
                   'command -v gcc >/dev/null || { echo "MSYS2 UCRT64 gcc unavailable" >&2; exit 127; }; '
                   'exec bash "$@"',
                   'tlo-ffmpeg-build', recipe_arg, source_arg, output_arg, build_arg]
    else:
        env = os.environ.copy()
        command = ['bash', str(recipe), str(source_root), str(output), str(build_root)]
    subprocess.run(command, env=env, check=True, timeout=3600)
    if not output.is_file():
        raise RuntimeError('FFmpeg build recipe returned without producing an executable')
    if platform_name != 'windows':
        output.chmod(output.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return output


def prepare_source_build(output: Path, cache: Path, *, platform_name: str, recipe: Path,
                         build_root: Path) -> Path:
    from ffmpeg_license_guard import verify
    archive = get_source(cache)
    src = extract_source(archive, cache / 'sources')
    output.parent.mkdir(parents=True, exist_ok=True)
    build_root.mkdir(parents=True, exist_ok=True)
    built = build(src, output, platform_name=platform_name, build_root=build_root, recipe=recipe)
    verify(built, require_audio_only=True)
    return built
