"""Shared helpers for exact-case folder renames."""

__version__ = "v471"

import os
import uuid


def folder_name_write_needed(source_root: str, target_leaf: str) -> bool:
    """Return True when the intended folder path differs byte-for-byte in name.

    Do not use os.path.normcase() here.  On Windows it lowercases both paths and
    would incorrectly suppress capitalization-only compliant renames.
    """
    source = os.path.normpath(str(source_root or ""))
    target = str(target_leaf or "").strip()
    if not source or not target:
        return False
    intended = os.path.normpath(os.path.join(os.path.dirname(source), target))
    return intended != source


def same_existing_entry(left: str, right: str) -> bool:
    """Return True when two existing spellings identify the same filesystem entry."""
    left_path = os.path.normpath(str(left or ""))
    right_path = os.path.normpath(str(right or ""))
    if not left_path or not right_path:
        return False
    if not os.path.lexists(left_path) or not os.path.lexists(right_path):
        return False
    try:
        return os.path.samefile(left_path, right_path)
    except (OSError, ValueError):
        return False


def _temporary_case_rename_path(source_root: str) -> str:
    parent = os.path.dirname(source_root)
    leaf = os.path.basename(source_root) or "TLO"
    for _ in range(50):
        candidate = os.path.join(parent, f".{leaf}.tlo-case-rename-{uuid.uuid4().hex}")
        if not os.path.lexists(candidate):
            return candidate
    raise OSError(f"Could not allocate temporary folder name beside {source_root}")


def rename_folder_exact_case(source_root: str, destination_root: str) -> str:
    """Rename a folder while reliably applying capitalization-only changes.

    On case-insensitive filesystems the differently-cased destination spelling
    can resolve to the source itself.  In that situation use a temporary sibling
    as an intermediate hop so the filesystem records the exact requested case.
    If the final hop fails, make a best-effort rollback to the original path.
    """
    source = os.path.normpath(str(source_root or ""))
    destination = os.path.normpath(str(destination_root or ""))
    if not source or not destination:
        raise OSError("Source and destination folder paths are required")
    if source == destination:
        return destination

    if same_existing_entry(source, destination):
        temporary = _temporary_case_rename_path(source)
        os.rename(source, temporary)
        try:
            os.rename(temporary, destination)
        except Exception:
            try:
                os.rename(temporary, source)
            except Exception:
                pass
            raise
    else:
        os.rename(source, destination)
    return destination
