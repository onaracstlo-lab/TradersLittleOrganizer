"""Move structurally identical TLO copy directories to the platform Trash/Recycle Bin."""

__version__ = "v363"
# TLO-GI package version: v363
__version_summary__ = 'Adds tlo-deleteDupes for safe recursive cleanup of copy-suffixed duplicate folders via the platform Trash/Recycle Bin.'
# TLO-GI version summary: Adds tlo-deleteDupes for safe recursive cleanup of copy-suffixed duplicate folders via the platform Trash/Recycle Bin.

import argparse
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, Iterable, List, Set, Tuple

from send2trash import send2trash

from console_output_lib import console_emit
from tlo_path_inputs import normalize_platform_input_path, resolve_tlo_home, strip_optional_quotes


_COPY_SUFFIX_RE = re.compile(r"^(?P<base>.+?)\s+\(copy\s*(?P<number>\d+)\)$", re.IGNORECASE)


class DeleteDupesError(RuntimeError):
    """Raised for invalid paths or an unsafe/unverifiable duplicate comparison."""


@dataclass(frozen=True)
class TreeManifest:
    directories: frozenset[str]
    files: Tuple[Tuple[str, int], ...]
    symlinks: Tuple[Tuple[str, str], ...]


def _relative_key(path_name: str, root: str) -> str:
    """Return a normalized relative path key without resolving symlinks."""
    return os.path.normcase(os.path.normpath(os.path.relpath(path_name, root)))


def _scan_tree(root: str) -> TreeManifest:
    """Return recursive structure plus file names/sizes for one directory tree.

    Directory identity for this utility intentionally does not compare file bytes,
    timestamps, ownership, permissions, or other filesystem metadata.  It requires
    the same relative directory structure, the same relative file names, and the
    same file sizes.  Symlinks are not followed; corresponding symlinks must have
    the same relative name and link target.
    """
    directories: Set[str] = set()
    files: Dict[str, int] = {}
    symlinks: Dict[str, str] = {}

    def visit(current: str) -> None:
        try:
            entries = list(os.scandir(current))
        except OSError as exc:
            raise DeleteDupesError(f"Unable to read directory during comparison: {current}: {exc}") from exc

        for entry in entries:
            full_path = entry.path
            relative = _relative_key(full_path, root)
            try:
                if entry.is_symlink():
                    symlinks[relative] = os.readlink(full_path)
                    continue
                if entry.is_dir(follow_symlinks=False):
                    directories.add(relative)
                    visit(full_path)
                    continue
                if entry.is_file(follow_symlinks=False):
                    files[relative] = entry.stat(follow_symlinks=False).st_size
                    continue
            except OSError as exc:
                raise DeleteDupesError(f"Unable to inspect path during comparison: {full_path}: {exc}") from exc

            raise DeleteDupesError(f"Unsupported filesystem object during comparison: {full_path}")

    visit(root)
    return TreeManifest(
        directories=frozenset(directories),
        files=tuple(sorted(files.items())),
        symlinks=tuple(sorted(symlinks.items())),
    )


def directory_trees_match_for_duplicate_deletion(original: str, copy_path: str) -> bool:
    """Return True when trees have identical names/structure and file sizes.

    This deliberately implements the cleanup rule requested for tlo-deleteDupes:
    equal relative folder structure, equal relative file names, and equal file
    sizes.  It does not hash file bytes.
    """
    original = os.path.normpath(str(original or ""))
    copy_path = os.path.normpath(str(copy_path or ""))
    if not os.path.isdir(original) or not os.path.isdir(copy_path):
        return False
    try:
        if os.path.samefile(original, copy_path):
            return False
    except OSError:
        pass
    return _scan_tree(original) == _scan_tree(copy_path)


def _copy_base_name(directory_name: str) -> str:
    match = _COPY_SUFFIX_RE.match(str(directory_name or "").strip())
    return match.group("base").strip() if match else ""


def _candidate_pairs(search_root: str) -> List[Tuple[str, str]]:
    """Return (copy_path, original_path) pairs found recursively under search_root."""
    pairs: List[Tuple[str, str]] = []
    for current_dir, dir_names, _file_names in os.walk(search_root, topdown=True, followlinks=False):
        for dir_name in list(dir_names):
            base = _copy_base_name(dir_name)
            if not base:
                continue
            copy_path = os.path.normpath(os.path.join(current_dir, dir_name))
            original_path = os.path.normpath(os.path.join(current_dir, base))
            if os.path.isdir(original_path) and not os.path.islink(original_path):
                pairs.append((copy_path, original_path))
    # Process parent candidates before nested candidates.  If a parent copy is
    # trashed, nested candidates beneath it simply no longer exist and are skipped.
    pairs.sort(key=lambda pair: (pair[0].count(os.sep), os.path.normcase(pair[0])))
    return pairs


def validate_input_path(path_text: str) -> str:
    """Validate and normalize the required fully qualified directory input."""
    cleaned = strip_optional_quotes(path_text).strip()
    if not cleaned:
        raise DeleteDupesError("Input Path must be supplied.")
    normalized = normalize_platform_input_path(cleaned)
    if not os.path.isabs(normalized):
        raise DeleteDupesError(f"Input Path must be a fully qualified path: {cleaned}")
    if not os.path.exists(normalized):
        raise DeleteDupesError(f"Input Path does not exist: {normalized}")
    if not os.path.isdir(normalized):
        raise DeleteDupesError(f"Input Path is not a directory: {normalized}")
    if not os.access(normalized, os.R_OK):
        raise DeleteDupesError(f"Input Path is not readable: {normalized}")
    return os.path.normpath(normalized)


def delete_duplicate_copy_directories(
    search_root: str,
    tlo_home: str,
    *,
    trash_func=send2trash,
    emit=console_emit,
) -> int:
    """Trash matching copy-suffixed folders and append their full paths to the log."""
    search_root = validate_input_path(search_root)
    log_path = os.path.join(tlo_home, "deletedDirs.txt")
    deleted_count = 0

    # Keep the log open during the operation so a Ctrl-C unwind closes it through
    # the context manager before main() returns 130.
    with open(log_path, "a", encoding="utf-8", buffering=1) as log_file:
        pairs = _candidate_pairs(search_root)
        for copy_path, original_path in pairs:
            if not os.path.isdir(copy_path):
                continue
            if not os.path.isdir(original_path):
                continue
            try:
                matches = directory_trees_match_for_duplicate_deletion(original_path, copy_path)
            except DeleteDupesError as exc:
                emit(f"Skipped unverifiable copy folder: {copy_path} ({exc})", error=True)
                continue
            if not matches:
                continue

            full_copy_path = os.path.abspath(copy_path)
            trash_func(full_copy_path)
            log_file.write(full_copy_path + "\n")
            log_file.flush()
            deleted_count += 1
            emit(f"Moved duplicate folder to Recycle Bin/Trash: {full_copy_path}")

    return deleted_count


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="tlo-deleteDupes.py",
        description=(
            "Recursively find directories ending in (copyN) or (copy N) whose unsuffixed sibling "
            "has the same directory structure, file names, and file sizes, then move only the copy "
            "directory to the platform Recycle Bin/Trash."
        ),
    )
    parser.add_argument(
        "--TLOHome",
        dest="TLOHome",
        default="",
        metavar="DIR",
        help="TLOHome directory. Defaults from the TLOHome environment variable when present.",
    )
    parser.add_argument("--myTLO", dest="myTLO", default="", metavar="DIR", help=argparse.SUPPRESS)
    parser.add_argument("path", metavar="PATH", help="Fully qualified directory path to search recursively.")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    try:
        args = _parse_args(argv)
        tlo_home = resolve_tlo_home(args.TLOHome, args.myTLO, error_type=DeleteDupesError)
        search_root = validate_input_path(args.path)
        deleted_count = delete_duplicate_copy_directories(search_root, tlo_home)
        console_emit(f"Complete: duplicate_folders_trashed={deleted_count}")
        return 0
    except KeyboardInterrupt:
        console_emit("Duplicate-folder cleanup cancelled.", error=True)
        return 130
    except Exception as exc:
        console_emit(f"ERROR: {exc}", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
