#!/usr/bin/env python3
"""Install the curated physical cities.csv beside TLO's Artist DB masters.

Use after the ArtistDB master copy, before complete/update package creation.
No embedded Python copy of the city catalog is produced or retained.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import os
from pathlib import Path
import tempfile


def validate(data: bytes) -> None:
    if len(data) > 3 * 1024 * 1024 or len(data) < 80:
        raise ValueError('city CSV unexpectedly small or large')
    try:
        text = data.decode('utf-8-sig')
    except UnicodeError as exc:
        raise ValueError('city CSV is not UTF-8') from exc
    import io
    reader = csv.reader(io.StringIO(text, newline=''))
    first = next(reader, None)
    if first is None or [str(c).strip().casefold() for c in first[:4]] != ['city','region','country','aliases']:
        raise ValueError('city CSV is missing the expected four-column header')
    count = 0
    for n, row in enumerate(reader, 2):
        if len(row) != 4 or not row[0].strip():
            raise ValueError(f'city CSV malformed row {n}')
        count += 1
    if count < 1000:
        raise ValueError('curated city catalog unexpectedly small')


def stage(source_root: Path, distribution_root: Path | None = None) -> list[Path]:
    source_root = Path(source_root).resolve(strict=True)
    src = source_root / 'cities.csv'
    if not src.is_file() or src.is_symlink():
        raise ValueError(f'curated cities.csv missing or unsafe: {src}')
    content = src.read_bytes()
    validate(content)
    source_digest = hashlib.sha256(content).hexdigest()
    destinations = [source_root / 'TLO_DBs' / 'cities.csv']
    if distribution_root is not None:
        dist = Path(distribution_root).resolve(strict=True)
        if dist != source_root:
            destinations.append(dist / 'TLO_DBs' / 'cities.csv')
    staged = []
    for dest in destinations:
        if dest.parent.is_symlink() or dest.is_symlink():
            raise ValueError(f'refusing to write city database through symlink: {dest}')
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.is_file() or hashlib.sha256(dest.read_bytes()).hexdigest() != source_digest:
            temp = None
            try:
                with tempfile.NamedTemporaryFile(mode='wb', prefix='.cities-', suffix='.tmp', dir=dest.parent, delete=False) as handle:
                    temp=Path(handle.name)
                    handle.write(content)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, dest)  # disposable build staging, never user TLOHome
            finally:
                if temp is not None:
                    temp.unlink(missing_ok=True)
        if hashlib.sha256(dest.read_bytes()).hexdigest() != source_digest:
            raise ValueError(f'city database staging verification failed: {dest}')
        staged.append(dest)
    return staged


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
