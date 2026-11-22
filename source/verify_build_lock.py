"""Pre-install offline check of release build lock provenance-critical wheel pins.

This check is separate from (and must never replace) pip --require-hashes.
Pygments 2.21.0 and Ruff 0.16.10 wheel SHA-256 hashes were verified
against published PyPI release metadata; pip hashes downloaded wheel bytes.
"""

import sys

# This tool runs against the prepared source snapshot before upload. Importing
# the version module must never create __pycache__/tlo_version.*.pyc there.
# The build runner also invokes every source preflight with Python -B.
sys.dont_write_bytecode = True
from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import argparse
from pathlib import Path
import re

EXPECTED_VERSION = "2.21.0"
EXPECTED_SHA256 = "2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9"
EXPECTED_RUFF_VERSION = "0.16.10"
EXPECTED_RUFF_LINUX_X64_SHA256 = "f33f43a864a8483eebd160e713336c8bab02c934feaff0a33cf5ccb41546d09a"


def check_build_lock(path: Path) -> list[str]:
    """Fail closed on missing, duplicated or corrupted Pygments wheel pin."""
    content = path.read_text(encoding="utf-8")
    entries = list(re.finditer(r"(?im)^\s*Pygments==([^\s;]+)\s*\\\s*\n\s*--hash=sha256:([0-9a-fA-F]{64})\s*$", content))
    if len(entries) != 1:
        return [f"Pygments wheel lock must contain exactly one complete pin; found {len(entries)} in {path}"]
    version, digest = entries[0].groups()
    errors = []
    if version != EXPECTED_VERSION or digest.lower() != EXPECTED_SHA256:
        errors.append(f"Pygments wheel pin mismatch in {path}: expected {EXPECTED_VERSION} sha256:{EXPECTED_SHA256}; got {version} sha256:{digest}")

    # Ruff pins multiple OS wheel hashes; the Linux x64 pin was accidentally
    # altered by a build-number text replacement in the earlier archive.
    ruff = list(re.finditer(r"(?im)^ruff==([^\s;]+)\s*\\\s*$", content))
    if len(ruff) != 1:
        errors.append(f"Ruff wheel lock must contain exactly one version record; found {len(ruff)} in {path}")
    else:
        block = content[ruff[0].end():].split("\n\n", 1)[0]
        hashes = re.findall(r"--hash=sha256:([0-9a-fA-F]{64})", block)
        if ruff[0].group(1) != EXPECTED_RUFF_VERSION or EXPECTED_RUFF_LINUX_X64_SHA256 not in [h.lower() for h in hashes]:
            errors.append(f"Ruff Linux x64 wheel hash missing or invalid in {path}; expected {EXPECTED_RUFF_VERSION} sha256:{EXPECTED_RUFF_LINUX_X64_SHA256}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("requirements", nargs="?", type=Path, default=Path(__file__).with_name("requirements-build.txt"))
    args = parser.parse_args(argv)
    if not args.requirements.is_file():
        parser.error(f"missing requirements lock: {args.requirements}")
    errors = check_build_lock(args.requirements)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Pygments and Ruff wheel locks verified against pinned PyPI metadata; pip --require-hashes remains mandatory.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
