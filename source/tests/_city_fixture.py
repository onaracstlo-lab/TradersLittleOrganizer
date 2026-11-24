"""Small synthetic schema-v1 city reference for parser tests."""
from contextlib import closing
from pathlib import Path
import sqlite3
from match_city import normalize


def city_db(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with closing(sqlite3.connect(path)) as db:
        db.executescript("""
        CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT);
        INSERT INTO metadata VALUES ('schema_version','1');
        CREATE TABLE cities(city_id INTEGER PRIMARY KEY,canonical_city TEXT,region TEXT,city_norm TEXT,region_norm TEXT);
        CREATE TABLE city_names(city_id INTEGER,name TEXT,name_norm TEXT,name_length INTEGER,is_canonical INTEGER);
        CREATE TABLE region_names(city_id INTEGER,region_name TEXT,region_norm TEXT,is_canonical INTEGER);
        CREATE TABLE fuzzy_review_guards(city_norm TEXT,region_norm TEXT,reason TEXT);
        """)
        for i,(city,region,aliases) in enumerate(rows,1):
            db.execute('INSERT INTO cities VALUES (?,?,?,?,?)',(i,city,region,normalize(city),normalize(region)))
            db.execute('INSERT INTO region_names VALUES (?,?,?,1)',(i,region,normalize(region)))
            for name in (city,*aliases):
                db.execute('INSERT INTO city_names VALUES (?,?,?,?,?)',(i,name,normalize(name),len(normalize(name)),int(name==city)))
        db.commit()
    return path
