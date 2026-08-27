"""Literal-directory file enumeration helpers.

Patterns apply only to basenames, never to the user-supplied directory path.
This prevents legal path characters such as ``[`` and ``]`` from becoming glob
metacharacters and silently changing which directory is searched.
"""
from __future__ import annotations

__version__ = "v413"

import fnmatch
import os
import re
from typing import List


def scandir_matching_files(directory: str, pattern: str) -> List[str]:
    """Return files in *directory* whose basenames match *pattern*.

    The directory is always opened literally with os.scandir().  Only
    ``entry.name`` is interpreted with fnmatch semantics.
    """
    if not directory:
        return []
    try:
        with os.scandir(directory) as entries:
            result = [
                os.path.normpath(entry.path)
                for entry in entries
                if fnmatch.fnmatch(entry.name, pattern) and entry.is_file()
            ]
    except OSError:
        return []
    return sorted(result, key=lambda value: os.path.basename(value).casefold())


def is_setlist_family_name(filename: str, base: str, extension: str = ".txt") -> bool:
    """Return True for exactly ``base.txt`` or TLO's ``base(altN).txt`` variants.

    A longer show name that merely starts with *base* is not part of the family.
    """
    name = str(filename or "")
    base_text = str(base or "")
    if not name or not base_text:
        return False
    pattern = rf"^{re.escape(base_text)}(?:\(alt\d+\))?{re.escape(extension)}$"
    return re.fullmatch(pattern, name, flags=re.IGNORECASE) is not None
