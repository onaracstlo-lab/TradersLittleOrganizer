#!/usr/bin/env python3
"""Check physical TLO_DBs/cities.csv inside a native TLO complete/update ZIP.

Fail if manifests omit city DB in 646+ database-inclusive packages or if the
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
except ImportError:
    from stage_city_database import validate

DBS = {'TLO_DBs/artists.sqlite','TLO_DBs/venues.txt','TLO_DBs/cities.csv'}

def verify(zip_path: Path, source_root: Path, build: int) -> dict:
    curated = (source_root/'cities.csv').read_bytes()
    validate(curated)
    expected_sha = hashlib.sha256(curated).hexdigest()
    with zipfile.ZipFile(zip_path) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP CRC check failed')
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('ZIP contains duplicate members')
        if 'manifest.json' not in names:
            raise ValueError('ZIP has no manifest.json')
        metadata = json.loads(archive.read('manifest.json'))
        included = metadata.get('databases_included')
        if not isinstance(included,bool):
            raise ValueError('databases_included must be boolean')
        declared = metadata.get('database_files')
        if not isinstance(declared,list):
            raise ValueError('database_files manifest list missing')
        present = {name for name in names if name.startswith('TLO_DBs/') and not name.endswith('/')}
        wanted = DBS if included else set()
        if present != wanted:
            raise ValueError(f'database files mismatch: expected {sorted(wanted)}, found {sorted(present)}')
        if set(declared) != {name.removeprefix('TLO_DBs/') for name in wanted} or len(declared) != len(wanted):
            raise ValueError('database_files manifest declaration mismatch')
        if metadata.get('kind') == 'complete' and not included:
            raise ValueError('complete package missing database masters')
        if int(metadata.get('build_number',-1)) != build:
            raise ValueError('package build number mismatch')
        if included:
            binary=archive.read('TLO_DBs/cities.csv')
            if hashlib.sha256(binary).hexdigest() != expected_sha:
                raise ValueError('city database contents do not match curated source')
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
