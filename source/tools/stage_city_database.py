#!/usr/bin/env python3
"""Validate and stage the external SQLite city master, without embedding it."""
from __future__ import annotations
import argparse
from contextlib import closing
import hashlib
import os
from pathlib import Path
import sqlite3
import tempfile


def validate(path: Path) -> None:
    path = Path(path).absolute()
    if path.is_symlink() or not path.is_file() or path.stat().st_size < 4096:
        raise ValueError(f'Missing or unsafe cities.sqlite: {path}')
    try:
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            version = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            if not version or version[0] != '1' or db.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
                raise ValueError('cities.sqlite failed schema/integrity validation')
            for query in ('SELECT city_id,canonical_city,region,city_norm,region_norm FROM cities',
                          'SELECT city_id,name,name_norm,name_length,is_canonical FROM city_names',
                          'SELECT city_id,region_name,region_norm,is_canonical FROM region_names',
                          'SELECT city_norm,region_norm,reason FROM fuzzy_review_guards'):
                db.execute(query + ' LIMIT 1').fetchone()
            if not db.execute('SELECT 1 FROM cities LIMIT 1').fetchone():
                raise ValueError('cities.sqlite has no cities')
    except sqlite3.Error as exc:
        raise ValueError(f'Invalid cities.sqlite schema: {path}') from exc


def stage(source_root: Path, distribution_root: Path | None = None) -> list[Path]:
    source_root = Path(source_root).resolve(strict=True)
    src = source_root / 'TLO_DBs' / 'cities.sqlite'
    if src.parent.is_symlink():
        raise ValueError(f'Unsafe city DB parent: {src.parent}')
    validate(src)
    if distribution_root is None or Path(distribution_root).resolve(strict=True) == source_root:
        return [src]
    dest = Path(distribution_root).resolve(strict=True) / 'TLO_DBs' / 'cities.sqlite'
    if dest.parent.is_symlink() or dest.is_symlink():
        raise ValueError(f'Unsafe city DB destination: {dest}')
    content = src.read_bytes()
    digest = hashlib.sha256(content).digest()
    dest.parent.mkdir(parents=True, exist_ok=True)
    if not dest.is_file() or hashlib.sha256(dest.read_bytes()).digest() != digest:
        temp = None
        try:
            with tempfile.NamedTemporaryFile(mode='wb', prefix='.cities-', suffix='.tmp', dir=dest.parent, delete=False) as handle:
                temp = Path(handle.name)
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, dest)
        finally:
            if temp is not None:
                temp.unlink(missing_ok=True)
    if hashlib.sha256(dest.read_bytes()).digest() != digest:
        raise ValueError(f'City DB staging verification failed: {dest}')
    return [src, dest]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--dist-root', type=Path)
    args = parser.parse_args()
    for path in stage(args.source_root, args.dist_root):
        print(f'Verified physical city database: {path}')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
