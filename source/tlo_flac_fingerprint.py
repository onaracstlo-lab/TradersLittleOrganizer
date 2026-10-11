"""FLAC STREAMINFO fingerprint verification using only the bundled LGPL FFmpeg.

Read raw decoded PCM continuously, preserving the original number of significant
sample bits, and compare the whole decoded audio with STREAMINFO's MD5.  This
uses no GPL CLI or new native library and does not write decoded audio to disk.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import hashlib
import os
import subprocess
import tempfile
import threading
import time

from mutagen.flac import FLAC

from tlo_ffmpeg import bundled_ffmpeg_executable
from tlo_runtime_control import is_cancel_requested

DECODE_TIMEOUT_SECONDS = 1800.0
_CHUNK = 256 * 1024
_MAX_DIAGNOSTIC = 128 * 1024


class FingerprintCorrupt(ValueError):
    """Proven missing/mismatched fingerprint or wrong/incomplete decoded samples."""


class FingerprintUnverifiable(RuntimeError):
    """Infrastructure failure, cancellation, or unresolved decoder result."""


def _streaminfo(path):
    """Return (sample rate, channels, depth, total samples, MD5) from STREAMINFO.

    Parsing STREAMINFO is not sufficient to establish validity.  Every FLAC
    still needs a successful end-to-end decode and MD5 comparison.
    """
    try:
        info = FLAC(path).info
        rate, channels, depth = (int(info.sample_rate), int(info.channels), int(info.bits_per_sample))
        total = int(info.total_samples)
        digest = int(info.md5_signature).to_bytes(16, 'big')
    except (OSError, MemoryError):
        raise
    except Exception as exc:
        raise FingerprintCorrupt(f'invalid FLAC STREAMINFO: {exc}') from exc
    if not (rate > 0 and 1 <= channels <= 8 and 4 <= depth <= 32):
        raise FingerprintCorrupt('invalid FLAC sample rate, channel count, or sample depth')
    if digest == bytes(16):
        raise FingerprintCorrupt('FLAC STREAMINFO fingerprint is missing (all zeroes)')
    # Zero is permitted by the specification for streams of unknown length.
    # When zero, exact EOF plus the complete audio MD5 still validates the data.
    if total < 0:
        raise FingerprintCorrupt('negative FLAC total sample count')
    return rate, channels, depth, total, digest


def _pcm_format(bit_depth):
    container_bits = 8 if bit_depth <= 8 else (16 if bit_depth <= 16 else (24 if bit_depth <= 24 else 32))
    fmt = {8: 's8', 16: 's16le', 24: 's24le', 32: 's32le'}[container_bits]
    codec = {8: 'pcm_s8', 16: 'pcm_s16le', 24: 'pcm_s24le', 32: 'pcm_s32le'}[container_bits]
    return codec, fmt, container_bits


def _fingerprint_from_pcm(source, depth, container_bits, channels):
    """Convert sign-extended/aligned decoded PCM into the FLAC MD5 byte layout.

    FFmpeg right-justifies signed PCM in its integer sample formats. When a
    stream uses e.g. 20 significant bits, s24le contains 20-bit values left
    shifted by four, so shift back before hashing the three-byte signed sample.
    Samples remain in native interleaved order, not a WAVE container.
    """
    source_bytes = container_bits // 8
    target_bytes = (depth + 7) // 8
    shift = container_bits - depth
    hasher = hashlib.md5(usedforsecurity=False)
    count = 0
    leftover = b''
    while True:
        data = source.read(_CHUNK)
        if not data:
            break
        data = leftover + data
        usable = len(data) - (len(data) % source_bytes)
        leftover = data[usable:]
        values = memoryview(data)[:usable]
        if shift == 0 and source_bytes == target_bytes:
            hasher.update(values)
        else:
            transformed = bytearray()
            for offset in range(0, usable, source_bytes):
                value = int.from_bytes(values[offset:offset + source_bytes], 'little', signed=True)
                value >>= shift
                transformed.extend(value.to_bytes(target_bytes, 'little', signed=True))
            hasher.update(transformed)
        count += usable
    if leftover or count == 0 or count % (source_bytes * channels):
        raise FingerprintCorrupt('decoded PCM output contains incomplete or no audio samples')
    return hasher.digest(), count // (source_bytes * channels)


def verify_flac_fingerprint(
    path, *, ffmpeg_executable=None, popen_factory=subprocess.Popen,
    timeout_seconds=DECODE_TIMEOUT_SECONDS, cancel_check=is_cancel_requested,
    hidden_subprocess_kwargs=None,
):
    """True only when the complete FFmpeg decode agrees with STREAMINFO MD5.

    Raises FingerprintCorrupt for verifiable bad files, or FingerprintUnverifiable
    for cancellation, timeouts, missing binary, races, filesystem or process
    failures. This distinction prevents a damaged environment causing deletions.
    """
    normalized = os.path.abspath(os.path.normpath(str(path)))
    executable = str(ffmpeg_executable or bundled_ffmpeg_executable() or '')
    if not executable:
        raise FingerprintUnverifiable('bundled FFmpeg missing')
    try:
        before = os.stat(normalized)
        rate, channels, depth, total, expected_md5 = _streaminfo(normalized)
    except (OSError, MemoryError) as exc:
        raise FingerprintUnverifiable(f'cannot read file: {exc}') from exc
    codec, fmt, container_bits = _pcm_format(depth)
    command = [
        executable, '-nostdin', '-hide_banner', '-loglevel', 'error', '-xerror',
        '-protocol_whitelist', 'file', '-i', normalized,
        '-map', '0:a:0', '-vn', '-sn', '-dn', '-c:a', codec,
        '-f', fmt, 'pipe:1',
    ]
    result = {}
    process = None
    try:
        with tempfile.TemporaryFile(mode='w+b') as stderr_file:
            process = popen_factory(
                command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                stderr=stderr_file, env={**os.environ, 'LC_ALL': 'C'},
                **(hidden_subprocess_kwargs or {}),
            )
            def consume():
                try:
                    result['value'] = _fingerprint_from_pcm(process.stdout, depth, container_bits, channels)
                except Exception as exc:
                    result['error'] = exc
                finally:
                    process.stdout.close()
            thread = threading.Thread(target=consume, daemon=True)
            thread.start()
            deadline = time.monotonic() + max(1., float(timeout_seconds))
            while process.poll() is None or thread.is_alive():
                if cancel_check and cancel_check():
                    raise FingerprintUnverifiable('FLAC fingerprint check cancelled')
                if time.monotonic() > deadline:
                    raise FingerprintUnverifiable('FLAC fingerprint check timed out')
                time.sleep(.025)
            thread.join(timeout=1)
            if thread.is_alive():
                raise FingerprintUnverifiable('FLAC PCM reader did not finish')
            stderr_file.seek(0)
            details = stderr_file.read(_MAX_DIAGNOSTIC).decode('utf-8', 'replace').lower()
            if process.returncode:
                # Filesystem and resource failures do not prove corrupt audio.
                from tlo_corruption import _ffmpeg_failure_is_unverifiable
                if _ffmpeg_failure_is_unverifiable(details):
                    raise FingerprintUnverifiable(f'FFmpeg file access failure: {details[:250]}')
                raise FingerprintCorrupt(f'FFmpeg full-stream decode failed (exit {process.returncode}): {details[:250]}')
            if 'error' in result:
                raise result['error']
            if 'value' not in result:
                raise FingerprintUnverifiable('FFmpeg produced no complete PCM digest')
            actual_md5, decoded_samples = result['value']
            try:
                after = os.stat(normalized)
            except OSError as exc:
                raise FingerprintUnverifiable(f'FLAC disappeared during decoding: {exc}') from exc
            if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
                raise FingerprintUnverifiable('FLAC changed during fingerprint verification')
            if total and decoded_samples != total:
                raise FingerprintCorrupt(f'FLAC sample count mismatch: STREAMINFO={total}, decoded={decoded_samples}')
            if actual_md5 != expected_md5:
                raise FingerprintCorrupt(f'FLAC audio fingerprint mismatch: expected={expected_md5.hex()}, decoded={actual_md5.hex()}')
            return True
    except (FingerprintCorrupt, FingerprintUnverifiable):
        raise
    except (OSError, MemoryError) as exc:
        raise FingerprintUnverifiable(f'FLAC checking infrastructure error: {exc}') from exc
    except Exception as exc:
        raise FingerprintUnverifiable(f'FLAC fingerprint validator error: {exc}') from exc
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
