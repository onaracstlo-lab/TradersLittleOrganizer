"""Exact recursive directory-tree comparison and copy/alternate collision helpers."""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import hashlib
import os
import re
from typing import Dict, List, Optional, Set, Tuple

COLLISION_SUFFIX_RE = re.compile(
    r"^(?P<base>.+?)\s+\((?P<kind>copy|alt)(?P<num>\d*)\)$",
    re.IGNORECASE,
)


def split_collision_suffix(name: str) -> Optional[Tuple[str, str, str]]:
    """Return (base, kind, number_text) for a trailing copy/alt folder suffix."""
    match = COLLISION_SUFFIX_RE.match(str(name or "").strip())
    if not match:
        return None
    return match.group("base").strip(), match.group("kind").casefold(), match.group("num") or ""


def _normalized_relative(path_name: str, root: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.relpath(path_name, root)))


def _raise_walk_error(error: OSError) -> None:
    raise error


def _tree_manifest(
    root: str, *, ignore_root_names: Set[str] | None = None
) -> Tuple[Set[str], Dict[str, int], Dict[str, str]]:
    """Return directories, regular files, and symlinks without following links."""
    directories: Set[str] = set()
    files: Dict[str, int] = {}
    links: Dict[str, str] = {}
    ignored = {str(name).casefold() for name in (ignore_root_names or set())}
    root_norm = os.path.normcase(os.path.abspath(os.path.normpath(root)))
    for current_dir, dir_names, file_names in os.walk(
        root, topdown=True, followlinks=False, onerror=_raise_walk_error
    ):
        if os.path.normcase(os.path.abspath(os.path.normpath(current_dir))) == root_norm and ignored:
            dir_names[:] = [name for name in dir_names if name.casefold() not in ignored]
            file_names = [name for name in file_names if name.casefold() not in ignored]

        retained_dirs = []
        for dir_name in dir_names:
            full_path = os.path.join(current_dir, dir_name)
            relative = _normalized_relative(full_path, root)
            if os.path.islink(full_path):
                links[relative] = os.readlink(full_path)
            else:
                directories.add(relative)
                retained_dirs.append(dir_name)
        dir_names[:] = retained_dirs

        for file_name in file_names:
            full_path = os.path.join(current_dir, file_name)
            relative = _normalized_relative(full_path, root)
            if os.path.islink(full_path):
                links[relative] = os.readlink(full_path)
            else:
                files[relative] = os.path.getsize(full_path)
    return directories, files, links


def _sha256(path_name: str) -> str:
    digest = hashlib.sha256()
    with open(path_name, "rb") as infile:
        while True:
            block = infile.read(1024 * 1024)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def directory_trees_exactly_match(left_root: str, right_root: str, *, ignore_root_names: Set[str] | None = None) -> bool:
    """Return True only for identical recursive structure and byte contents.

    Exact identity requires the same relative descendant folders (including
    empty folders), the same relative regular files, identical file sizes and
    SHA-256 content for every regular file, and the same symbolic links with the
    same readlink() target text. Links are compared as links and are never
    dereferenced for content. Filesystem timestamps/attributes are intentionally
    ignored. Any comparison error is a safe non-match so an unverified collision
    is never labeled a copy.
    """
    left_root = os.path.normpath(str(left_root or ""))
    right_root = os.path.normpath(str(right_root or ""))
    if not left_root or not right_root or not os.path.isdir(left_root) or not os.path.isdir(right_root):
        return False
    try:
        if os.path.samefile(left_root, right_root):
            return True
    except OSError:
        pass

    try:
        left_dirs, left_files, left_links = _tree_manifest(left_root, ignore_root_names=ignore_root_names)
        right_dirs, right_files, right_links = _tree_manifest(right_root, ignore_root_names=ignore_root_names)
        if left_dirs != right_dirs or left_files != right_files or left_links != right_links:
            return False
        for relative in sorted(left_files):
            left_path = os.path.join(left_root, relative)
            right_path = os.path.join(right_root, relative)
            if _sha256(left_path) != _sha256(right_path):
                return False
        return True
    except (OSError, PermissionError):
        return False


def collision_family_directories(parent_dir: str, base: str) -> List[str]:
    """Return existing base/copy/alt directories belonging to one show-name family."""
    result: List[str] = []
    base = str(base or "").strip()
    if not parent_dir or not base:
        return result
    try:
        with os.scandir(parent_dir) as entries:
            for entry in entries:
                try:
                    if not entry.is_dir(follow_symlinks=False):
                        continue
                except OSError:
                    continue
                split = split_collision_suffix(entry.name)
                if entry.name.casefold() == base.casefold() or (split and split[0].casefold() == base.casefold()):
                    result.append(os.path.normpath(entry.path))
    except OSError:
        pass
    return result


def has_exact_tree_match_in_family(source_root: str, parent_dir: str, base: str, *, exclude_source: bool = False) -> bool:
    """Return whether source exactly matches another member of the name family."""
    source_root = os.path.normpath(str(source_root or ""))
    for existing in collision_family_directories(parent_dir, base):
        if exclude_source:
            try:
                if os.path.samefile(source_root, existing):
                    continue
            except OSError:
                if os.path.normcase(source_root) == os.path.normcase(existing):
                    continue
        if directory_trees_exactly_match(source_root, existing):
            return True
    return False
