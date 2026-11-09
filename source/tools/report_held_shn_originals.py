#!/usr/bin/env python3
"""Read-only audit of original SHN audio held when native Trash failed.

Usage: python tools/report_held_shn_originals.py PATH
This command does not move, remove, or restore files.
"""
from __future__ import annotations
import argparse
import os
from pathlib import Path

HOLDER = '.tlo-shn-originals'


def scan(root: Path):
    """Yield safe regular originals, skipping symlinks and unreadable paths."""
    root = root.resolve(strict=True)
    for current, directories, _ in os.walk(root, followlinks=False):
        held = [name for name in directories if name.casefold() == HOLDER]
        directories[:] = [name for name in directories if name.casefold() != HOLDER
                          and not Path(current, name).is_symlink()]
        for name in held:
            holder = Path(current, name)
            if holder.is_symlink() or not holder.is_dir():
                continue
            for base, nested_dirs, filenames in os.walk(holder, followlinks=False):
                nested_dirs[:] = [n for n in nested_dirs if not Path(base, n).is_symlink()]
                for filename in filenames:
                    candidate = Path(base, filename)
                    if candidate.is_symlink() or not candidate.is_file():
                        continue
                    try:
                        size = candidate.stat().st_size
                    except OSError:
                        continue
                    yield candidate, size


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('path',type=Path,help='Collection or show folder to inspect')
    args=parser.parse_args()
    if not args.path.is_dir():
        parser.error('Path must be an existing directory')
    total=0
    count=0
    for original, size in scan(args.path):
        print(f'{size:>12}  {original}')
        total+=size
        count+=1
    print(f'HELD SHN ORIGINALS: {count} file(s), {total} bytes (read-only report)')

if __name__ == '__main__':
    main()
