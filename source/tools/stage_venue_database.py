#!/usr/bin/env python3
"""Validate and atomically stage the physical venue master, never embed it."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def validate(path: Path) -> None:
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file() or path.stat().st_size < 4096:
        raise ValueError(f'Missing or unsafe venues.sqlite: {path}')
    try:
        from tlo_catalog_io import open_catalog_readonly
        with closing(open_catalog_readonly(path)) as db:
            if db.execute('PRAGMA user_version').fetchone()[0] != 1 or db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('venues.sqlite failed schema/integrity validation')
            if not db.execute('SELECT spelling,normalized_key,display_name,anchor,strength,kind,institution FROM names LIMIT 1').fetchone():
                raise ValueError('venues.sqlite has no names')
            db.execute('SELECT normalized_key,city_key,state_key,display_name FROM locations LIMIT 1').fetchone()
    except sqlite3.Error as exc:
        raise ValueError(f'Invalid venues.sqlite schema: {path}') from exc


def stage(source_root: Path, distribution_root: Path | None = None) -> list[Path]:
    source_root = Path(source_root).resolve(strict=True)
    src = source_root / 'TLO_DBs' / 'venues.sqlite'
    if src.parent.is_symlink():
        raise ValueError(f'Unsafe venue DB parent: {src.parent}')
    validate(src)
    if distribution_root is None or Path(distribution_root).resolve(strict=True) == source_root:
        return [src]
    dest = Path(distribution_root).resolve(strict=True) / 'TLO_DBs' / 'venues.sqlite'
    if dest.parent.is_symlink() or dest.is_symlink():
        raise ValueError(f'Unsafe venue DB destination: {dest}')
    content = src.read_bytes()
    digest = hashlib.sha256(content).digest()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file() or hashlib.sha256(dest.read_bytes()).digest() != digest:
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', prefix='.venues-', suffix='.tmp', dir=dest.parent, delete=False) as handle:
                temp = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, dest)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    if hashlib.sha256(dest.read_bytes()).digest() != digest:
        raise ValueError(f'Venue DB staging verification failed: {dest}')
    return [src, dest]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--dist-root', type=Path)
    args = parser.parse_args()
    for path in stage(args.source_root, args.dist_root):
        print(f'Verified physical venue database: {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
