"""Fail closed when a native TLO build uses an unapproved toolchain."""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION


import argparse
import importlib.metadata
import platform
import sys

EXPECTED_PYTHON = (3, 13, 16)
EXPECTED_PACKAGES = {
    "PyInstaller": "6.22.3",
    "pyinstaller-hooks-contrib": "2026.8",
    "altgraph": "0.17.5",
    "packaging": "26.3",
    "setuptools": "84.0.0",
    "mutagen": "1.48.1",
    "tkinterdnd2": "0.6.3",
}
PLATFORM_PACKAGES = {
    "Windows": {"pefile": "2024.8.26", "pywin32-ctypes": "0.2.3"},
    "Darwin": {"macholib": "1.16.4"},
}
RELEASE_CHECK_PACKAGES = {
    "pytest": "9.1.1",
    "python-docx": "1.2.0",
    "lxml": "6.1.3",
    "typing_extensions": "4.16.0",
    "ruff": "0.16.10",
}


def _installed(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "<missing>"


def verify(*, release: bool = False) -> list[str]:
    errors: list[str] = []
    actual_python = tuple(sys.version_info[:3])
    if actual_python != EXPECTED_PYTHON:
        errors.append(f"Python must be {'.'.join(map(str, EXPECTED_PYTHON))}; found {platform.python_version()}")

    expected = dict(EXPECTED_PACKAGES)
    expected.update(PLATFORM_PACKAGES.get(platform.system(), {}))
    if release:
        expected.update(RELEASE_CHECK_PACKAGES)
    for name, wanted in expected.items():
        found = _installed(name)
        if found != wanted:
            errors.append(f"{name} must be {wanted}; found {found}")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", action="store_true", help="also verify test/lint/document release-gate packages")
    args = parser.parse_args(argv)
    errors = verify(release=args.release)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print(f"Verified Python {platform.python_version()} and pinned TLO {'release' if args.release else 'native build'} dependencies.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
