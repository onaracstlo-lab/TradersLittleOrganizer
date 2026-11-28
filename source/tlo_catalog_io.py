"""Open SQLite reference catalogs without creating or mutating them."""
from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

from pathlib import Path, PurePath
import sqlite3

def catalog_readonly_uri(path) -> str:
    absolute = path if isinstance(path, PurePath) and path.is_absolute() else Path(path).absolute()
    uri = absolute.as_uri()
    if uri.startswith("file://") and not uri.startswith("file:///"):
        uri = "file:////" + uri[len("file://"):]
    return uri + "?mode=ro"

def open_catalog_readonly(path):
    return sqlite3.connect(catalog_readonly_uri(path), uri=True)
