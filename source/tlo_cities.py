"""Conservative city lookup for Traders Little Organizer.

GeoNames city source: https://www.geonames.org/ (CC BY 4.0).
Use after artist and date are independently established; never classify raw
folders by city string alone. No network calls. No filesystem modifications.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

from dataclasses import dataclass
from typing import Callable
import logging
from functools import lru_cache
from pathlib import Path
import sys
import csv
import re
import unicodedata

_HEADER = ['city', 'region', 'country', 'aliases']
_DATE = re.compile(r'(?<!\d)(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2]|xx)[-/.](?:[0-2]?\d|3[01]|xx)(?!\d)', re.I)
_WORD = re.compile(r'[^\W_]+', re.UNICODE)
# There is no reliable generic way to distinguish these from musicians/ensembles
# when the folder provides no location punctuation or corroborating geography.
# The artist DB supplied by the calling application provides additional blocks.
_CONFLICTING_ARTIST_NAMES = frozenset({
    'athens', 'berlin', 'boston', 'chicago', 'dallas', 'geneva',
    'london', 'memphis', 'miami', 'moscow', 'paris', 'phoenix',
    'rome', 'toronto',
})


def normalized(value: str) -> str:
    """Fold accents, common latin extensions and punctuation for lookup only."""
    value = value.casefold().translate(str.maketrans({
        'ø':'o', 'ł':'l', 'đ':'d', 'ð':'d', 'þ':'th', 'æ':'ae', 'œ':'oe', 'ı':'i',
    }))
    value = ''.join(ch for ch in unicodedata.normalize('NFKD',value)
                    if not unicodedata.combining(ch))
    return ' '.join(re.findall(r'[a-z0-9]+',value))


def _canonical_key(value: str) -> str:
    return normalized(value)


@dataclass(frozen=True)
class City:
    city: str
    region: str
    country: str
    aliases: tuple[str,...] = ()


@dataclass(frozen=True)
class CityCandidate:
    city: str  # exact folder spelling, not the catalog preferred spelling
    region: str
    country: str
    venue_prefix: str
    evidence: str  # 'delimiter', 'date-before-city', or 'multiword-suffix'


class CityCatalog:
    def __init__(self, cities: list[City], warnings: tuple[str,...] = (), local_names: frozenset[str] = frozenset()):
        self.cities = tuple(cities)
        self.warnings = warnings
        self.local_names = local_names
        entries: dict[str,set[City]] = {}
        for city in cities:
            for name in (city.city,*city.aliases):
                k = _canonical_key(name)
                if k:
                    entries.setdefault(k,set()).add(city)
        # Ambiguous aliases/canonical names are never returned at lookup time.
        self._lookup = {key: next(iter(vals)) for key,vals in entries.items()
                        if len(vals) == 1}
        self._ambiguous = {key for key,vals in entries.items() if len(vals) > 1}
        self.max_words = max((len(k.split()) for k in self._lookup),default=0)

    @classmethod
    def from_csv(cls, path: str | Path) -> 'CityCatalog':
        """Read curated/user city rows, rejecting individual malformed records.

        Both conventional CSV and legacy caret-delimited data are supported.
        Trailing legacy comment/reason columns are ignored. Bad headers yield
        an empty catalog rather than accepting arbitrary columns as cities.
        """
        rows, issues = _read_city_rows(Path(path))
        return cls(rows, tuple(issues))

    def lookup_exact(self, text: str) -> City | None:
        """Return a uniquely represented complete city name, never a substring."""
        return self._lookup.get(_canonical_key(text))

    @property
    def lookup_keys(self) -> frozenset[str]:
        """Unambiguous normalized keys, canonical names and aliases together."""
        return frozenset(self._lookup)

    def suffix_match(self, raw: str) -> tuple[str, City] | None:
        """Longest whole-token suffix; no prefix-substring or ambiguous match."""
        words = list(_WORD.finditer(raw))
        for n in range(min(len(words), self.max_words), 0, -1):
            suffix = raw[words[-n].start():words[-1].end()]
            result = self.lookup_exact(suffix)
            if result is not None:
                return suffix, result
        return None

    def suggest_for_known_artist(
        self, folder_name: str, *, artist: str, date: str,
        artist_names: tuple[str,...] | list[str] | set[str] = (),
        artist_is_known: Callable[[str],bool] | None = None,
        existing_city: str = '', existing_region: str = '',
        existing_country: str = '',
    ) -> CityCandidate | None:
        """A non-destructive city candidate from a trusted artist/date folder.

        Requirements:
        - artist must be a verified leading prefix; date must occur as text;
        - city must be a WHOLE exact dictionary name/alias at the trailing edge
          of the pre-date or post-date segment;
        - a single-token city without delimiter needs date-before-city layout;
        - an artist/city collision without clear context cannot be accepted;
        - preexisting city/region/country fields cannot be contradicted.
        """
        # Any already-established geography is stronger evidence. Without a
        # city, a partial region/country could belong to a different place.
        if not folder_name or not artist or not date or existing_city or existing_region or existing_country:
            return None
        # Guard against an alleged artist that is not actually the folder prefix.
        prefix = re.compile(r'^\s*'+re.escape(artist)+r'(?=$|[^\w])',re.I)
        artist_hit = prefix.match(folder_name)
        if not artist_hit:
            return None
        remainder = folder_name[artist_hit.end():]
        # Take only one exact caller-provided date; no guessing from years alone.
        date_hit = re.search(r'(?<!\d)'+re.escape(date)+r'(?!\d)',remainder,re.I)
        if date_hit is None or not _DATE.fullmatch(date):
            return None
        before = remainder[:date_hit.start()]
        after = remainder[date_hit.end():]
        # If stuff appears on both sides of the date, do not make an assumption.
        if before.strip(' ,\t\r\n-–—') and after.strip(' ,\t\r\n-–—'):
            return None
        city_text = after if after.strip(' ,\t\r\n-–—') else before
        city_after_date = city_text is after
        tokens = list(_WORD.finditer(city_text))
        if not tokens or len(tokens)>40:
            return None
        # Only inspect artist collisions AFTER obtaining a city candidate.
        # A single existing ArtistDB alias lookup is preferable to normalizing
        # hundreds of thousands of artist names for every show.
        for n in range(min(len(tokens),self.max_words),0,-1):
            start = tokens[-n].start()
            suffix = city_text[start:tokens[-1].end()]
            city = self.lookup_exact(suffix)
            if city is None:
                continue
            city_key = _canonical_key(suffix)
            prefix_raw = city_text[:start]
            venue_prefix = prefix_raw.strip(' ,\t\r\n-–—')
            explicit_delimiter = bool(re.search(r'[,;:]\s*$|\s[-–—]\s*$',prefix_raw))
            # Single-word trailing place could just be artist, venue or title.
            if n == 1 and not explicit_delimiter and not (city_after_date and not venue_prefix):
                continue
            # For location-less source entries, require especially clear syntax.
            if not city.country and not explicit_delimiter and not (city_after_date and not venue_prefix):
                continue
            artist_collision = (city_key in _CONFLICTING_ARTIST_NAMES or
                                (artist_is_known is not None and
                                 (artist_is_known(suffix) or artist_is_known(city.city))) or
                                any(_canonical_key(a) == city_key for a in artist_names))
            if artist_collision and not explicit_delimiter and not (city_after_date and not venue_prefix):
                continue
            # A date following venue + city with no delimiter: require a
            # MULTI-WORD city with complete geography.
            if venue_prefix and not explicit_delimiter and (n<2 or not city.country):
                continue
            if existing_country and city.country and _canonical_key(existing_country)!=_canonical_key(city.country):
                continue
            if existing_region and city.region and _canonical_key(existing_region)!=_canonical_key(city.region):
                continue
            if city_after_date and venue_prefix:
                # "Artist Date Venue City" is ambiguous without a delimiter.
                if not explicit_delimiter:
                    continue
            evidence = ('delimiter' if explicit_delimiter else
                        'date-before-city' if city_after_date else 'multiword-suffix')
            # The combined index recognizes both canonical names and aliases,
            # but never replaces a spelling that the folder actually used.
            return CityCandidate(suffix.strip(),city.region,city.country,venue_prefix,evidence)
        return None


def refine_parsed_fields(
    *, folder_name: str, artist: str, date: str, city: str = '',
    region: str = '', country: str = '', venue: str = '',
    artist_names: tuple[str,...] | list[str] | set[str] = (),
    artist_is_known: Callable[[str],bool] | None = None,
    csv_path: str | Path,
    on_warning=None, catalog: CityCatalog | None = None,
) -> dict[str,str]:
    """Safe opt-in adapter: FILL EMPTY city only. Never rewrite venue or override metadata.

    This function does not replace TLO's existing parser or geographical
    precedence. It must be called only after that parser has confirmed the
    artist and date and only when no stronger city has been established.
    """
    fields={'city':city,'region':region,'country':country,'venue':venue}
    if city or region or country:
        return fields
    try:
        if catalog is None:
            catalog = _load_cached(str(Path(csv_path).resolve()))
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        # Missing/corrupt optional city data must NEVER abort an inventory.
        if on_warning is not None:
            on_warning(f'City catalog unavailable; old parsing preserved: {exc}')
        return fields
    candidate = catalog.suggest_for_known_artist(
        folder_name,artist=artist,date=date,artist_names=artist_names,
        artist_is_known=artist_is_known,
        existing_city=city,existing_region=region,existing_country=country)
    if candidate is None:
        return fields
    fields['city']=candidate.city
    # City-name recognition is not geographic proof. Do not silently append
    # a region or country that was absent from the folder or metadata.
    # Venue remains untouched until independently validated by existing logic.
    return fields


_HEADER_TUPLE = tuple(_HEADER)
_MAX_LOCAL_BYTES = 3 * 1024 * 1024
_REPORTED_ISSUES: set[tuple[str, str]] = set()


def _read_city_rows(path: Path) -> tuple[list[City], list[str]]:
    """Read a physical TLO_DBs/cities.csv, rejecting only malformed rows.

    There is deliberately no internal/embedded CSV or fallback. A missing
    external city database leaves TLO's preexisting parsing behavior intact.
    """
    issues: list[str] = []
    rows: list[City] = []
    label = path.name
    if path.stat().st_size > _MAX_LOCAL_BYTES:
        return [], [f"{label} ignored: file larger than 3 MB"]
    handle = path.open('r', encoding='utf-8-sig', newline='')
    with handle:
        first = handle.readline().strip('\r\n')
        handle.seek(0)
        delimiter = '^' if first.startswith('city^') else ','
        reader = csv.reader(handle, delimiter=delimiter)
        try:
            header = next(reader)
        except StopIteration:
            return [], [f"{label} ignored: empty file"]
        if tuple(h.strip() for h in header[:3]) != _HEADER_TUPLE[:3]:
            return [], [f"{label} ignored: expected city,region,country columns"]
        for lineno, values in enumerate(reader, start=2):
            if not values or values[0].lstrip().startswith('#'):
                continue
            if len(values) < 3 or not values[0].strip():
                issues.append(f"{label} line {lineno} ignored: missing required city/columns")
                continue
            city, region, country = (v.strip() for v in values[:3])
            if not city or len(city) > 120 or len(region) > 120 or len(country) > 120:
                issues.append(f"{label} line {lineno} ignored: invalid field length")
                continue
            alias_text = values[3] if len(values) >= 4 else ''
            if len(alias_text) > 4096:
                issues.append(f"{label} line {lineno} ignored: aliases too long")
                continue
            aliases = tuple(alias.strip() for alias in alias_text.split('|') if alias.strip() and len(alias.strip()) < 120)
            rows.append(City(city, region, country, aliases))
            if len(rows) >= 40000:
                issues.append(f"{label}: record limit reached; remaining entries ignored")
                break
    return rows, issues


def _bundled_path() -> Path:
    """Find a real city DB file next to TLO's other database masters.

    For source Python it lives at <source>/TLO_DBs/cities.csv. For a frozen
    executable, search next to the executable and its packaging parents. Do
    NOT look inside _MEIPASS: there must be no internal PyInstaller copy.
    """
    if getattr(sys, 'frozen', False):
        exe_dir = Path(sys.executable).resolve().parent
        candidates = (exe_dir, exe_dir.parent, exe_dir.parent.parent)
    else:
        candidates = (Path(__file__).resolve().parent,)
    for folder in candidates:
        candidate = folder / 'TLO_DBs' / 'cities.csv'
        if candidate.is_file():
            return candidate
    return candidates[0] / 'TLO_DBs' / 'cities.csv'


def _local_path(tlo_dbs_dir: str = '', tlo_home: str = '') -> Path | None:
    root = Path(tlo_dbs_dir) if tlo_dbs_dir else (Path(tlo_home) / 'TLO_DBs' if tlo_home else None)
    if root is None: return None
    path = root / 'cities.csv'
    return path if path.is_file() else None


@lru_cache(maxsize=8)
def _load_cached(path: str) -> CityCatalog:
    return CityCatalog.from_csv(path)


def catalog_path_for_tlo(tlo_dbs_dir: str = '', tlo_home: str = '') -> Path:
    """Return the external city reference, preferring the configured TLOHome DB."""
    return _local_path(tlo_dbs_dir, tlo_home) or _bundled_path()


def catalog_for_tlo(tlo_dbs_dir: str = '', tlo_home: str = '', on_warning=None) -> CityCatalog | None:
    """Combine bundled + local cities, skipping malformed/conflicting local rows.

    Cache invalidates on file mtime/size changes. The output dictionary indexes
    primary and alias spellings once, rather than probing files for each show.
    """
    bundled = _bundled_path()
    local = _local_path(tlo_dbs_dir, tlo_home)
    def signature(path):
        try:
            stat = path.stat()
            return (str(path.resolve()), stat.st_mtime_ns, stat.st_size)
        except OSError:
            return ('',0,0)
    b_sig = signature(bundled)
    l_sig = signature(local) if local is not None else ('',0,0)
    try:
        catalog = _cached_layered(b_sig, l_sig)
    except (OSError, UnicodeError, ValueError, csv.Error) as exc:
        message = f"City reference unavailable; original parsing retained: {exc}"
        if on_warning:
            on_warning(message)
        return None
    if catalog is not None and catalog.warnings:
        for issue in catalog.warnings:
            key = (l_sig[0], issue)
            if key not in _REPORTED_ISSUES:
                _REPORTED_ISSUES.add(key)
                logging.getLogger(__name__).warning('%s', issue)
                if on_warning: on_warning(issue)
    return catalog


@lru_cache(maxsize=16)
def _cached_layered(b_sig: tuple, l_sig: tuple) -> CityCatalog | None:
    rows, warnings = ([], [])
    if b_sig[0]:
        rows, warnings = _read_city_rows(Path(b_sig[0]))
    # With no packaged CSV, a configured TLOHome/TLO_DBs/cities.csv is
    # still a normal physical reference, not an embedded fallback.
    if not rows and l_sig[0]:
        rows, warnings = _read_city_rows(Path(l_sig[0]))
        l_sig = ('', 0, 0)  # already loaded as the primary physical reference
    # Build an index of names/aliases to prevent local records from overriding
    # an existing, unrelated meaning. User additions cannot suppress the base.
    keys = {normalized(name): city for city in rows for name in (city.city, *city.aliases) if normalized(name)}
    added = 0
    local_names: set[str] = set()
    if l_sig[0] and l_sig[0] != b_sig[0]:
        extras, issues = _read_city_rows(Path(l_sig[0]))
        warnings.extend(issues)
        # Build 646 ships the full bundled CSV in TLO_DBs. Those 7k+ rows
        # are not 7k explicit user confirmations. If at least 90% of the
        # canonical records are reproduced, treat duplicates as shipped
        # baseline while still allowing added, non-colliding local entries.
        bundled_ids = {(normalized(c.city), normalized(c.region), normalized(c.country)) for c in rows}
        reproduced = sum((normalized(c.city), normalized(c.region), normalized(c.country)) in bundled_ids for c in extras)
        packaged_snapshot = bool(len(rows) > 500 and reproduced >= len(rows) * .90)
        for entry in extras:
            names = [entry.city, *entry.aliases]
            collisions = [keys[normalized(n)] for n in names if normalized(n) in keys]
            # Even same-name local rows can carry conflicting geography. Reject
            # rather than replacing the bundled mapping, to avoid wrong places.
            if collisions:
                # A record affirming exactly the same city, region and country
                # is not a geographic override. Treat it as explicit user
                # corroboration (historical user-file behavior), but never
                # let a local row change bundled geography or aliases.
                def country_key(value):
                    k = normalized(value)
                    return 'united states' if k in {'usa','us','united states of america'} else k
                same = (all(normalized(old.city) == normalized(entry.city) for old in collisions)
                        and all((not old.region or old.region.casefold() == entry.region.casefold())
                                and (not old.country or country_key(old.country) == country_key(entry.country))
                                for old in collisions))
                if same:
                    if not packaged_snapshot:
                        local_names.add(normalized(entry.city))
                    continue
                warnings.append(f"cities.csv local city {entry.city!r} ignored: conflicts with packaged city/alias")
                continue
            rows.append(entry)
            for name in names:
                if normalized(name): keys[normalized(name)] = entry
            local_names.update(normalized(name) for name in names if normalized(name))
            added += 1
    if not rows:
        return None
    if l_sig[0]:
        warnings.insert(0, f"cities: {len(rows)-added} bundled + {added} local; {max(0,len(warnings))} warning(s)")
    return CityCatalog(rows, tuple(warnings), frozenset(local_names))
