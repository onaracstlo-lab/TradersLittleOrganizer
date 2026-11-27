#!/usr/bin/env python3
"""Check physical TLO_DBs/cities.sqlite inside a native TLO complete/update ZIP.

Fail if manifests omit city DB in 725+ database-inclusive packages or if the
curated city file has been changed. Does not inspect signed executable bytes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import zipfile
try:
    from .stage_city_database import validate
    from .stage_venue_database import validate as validate_venue
except ImportError:
    from stage_city_database import validate
    from stage_venue_database import validate as validate_venue

DBS = {'TLO_DBs/artists.sqlite','TLO_DBs/venues.txt','TLO_DBs/cities.sqlite'}

def verify(zip_path: Path, source_root: Path, build: int) -> dict:
    master = source_root / 'TLO_DBs' / 'cities.sqlite'
    validate(master)
    venue_master = source_root / "TLO_DBs" / "venues.sqlite"
    if build >= 726:
        validate_venue(venue_master)
        venue_sha = hashlib.sha256(venue_master.read_bytes()).hexdigest()
    curated = master.read_bytes()
    expected_sha = hashlib.sha256(curated).hexdigest()
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC check failed')
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('ZIP contains duplicate members')
        manifests = [name for name in ('manifest.json', 'UPDATE_MANIFEST.json') if name in names]
        if len(manifests) != 1:
            raise ValueError('ZIP must have exactly one complete/update manifest')
        metadata = json.loads(archive.read(manifests[0]))
        if manifests[0] == 'UPDATE_MANIFEST.json' and metadata.get('kind') != 'update':
            raise ValueError('update manifest kind mismatch')
        included = metadata.get('databases_included')
        if not isinstance(included,bool):
            raise ValueError('databases_included must be boolean')
        declared = metadata.get('database_files')
        if not isinstance(declared,list):
            raise ValueError('database_files manifest list missing')
        present = {name for name in names if name.startswith('TLO_DBs/') and not name.endswith('/')}
        wanted = (DBS | ({"TLO_DBs/venues.sqlite"} if build >= 726 else set())) if included else set()
        if present != wanted:
            raise ValueError(f'database files mismatch: expected {sorted(wanted)}, found {sorted(present)}')
        if set(declared) != {name.removeprefix('TLO_DBs/') for name in wanted} or len(declared) != len(wanted):
            raise ValueError('database_files manifest declaration mismatch')
        if metadata.get('kind') == 'complete' and not included:
            raise ValueError('complete package missing database masters')
        if int(metadata.get('build_number', metadata.get('build', -1))) != build:
            raise ValueError('package build number mismatch')
        if included:
            binary=archive.read('TLO_DBs/cities.sqlite')
            if hashlib.sha256(binary).hexdigest() != expected_sha:
                raise ValueError('city database contents do not match curated source')
            if build >= 726 and hashlib.sha256(archive.read('TLO_DBs/venues.sqlite')).hexdigest() != venue_sha:
                raise ValueError('venue database contents do not match curated source')
    return {'build':build,'kind':metadata.get('kind'),'databases_included':included,'city_sha256': expected_sha if included else None}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('zip',type=Path)
    p.add_argument('--source-root',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--build',type=int,required=True)
    args=p.parse_args()
    print(json.dumps(verify(args.zip,args.source_root,args.build),indent=2))
    return 0
if __name__=='__main__':
    raise SystemExit(main())
