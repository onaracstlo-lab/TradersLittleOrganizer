"""Conservative city lookup for Traders Little Organizer.

Physical city data comes from the schema-v1 SQLite city master.
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
import sqlite3
from match_city import US_STATES, CA_PROVS, GB_LABELS, normalize as compact_city_key
import re
import unicodedata

_DATE = re.compile(r'(?<!\d)(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2]|xx)[-/.](?:[0-2]?\d|3[01]|xx)(?!\d)', re.I)
_WORD = re.compile(r'[^\W_]+', re.UNICODE)
# There is no reliable generic way to distinguish these from musicians/ensembles
# when the folder provides no location punctuation or corroborating geography.
# The artist DB supplied by the calling application provides additional blocks.
# Unsafe without independent geography; scoped matcher still recognizes these.
_UNSCOPED_UNSAFE = frozenset({'nice', 'bowie', 'reading', 'woodstock', 'mobile', 'soundboard', 'matrix'})
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
        # A city spelling may be real in several regions. Recognize the
        # spelling only; never select a geographic identity from an ambiguous key.
        self._lookup = {}
        for key, vals in entries.items():
            if key in _UNSCOPED_UNSAFE:
                continue
            if len(vals) == 1:
                self._lookup[key] = next(iter(vals))
            else:
                # A spelling that is itself a canonical city can be retained
                # without asserting which city/region it refers to.
                canonical = [v for v in vals if _canonical_key(v.city) == key]
                if canonical:
                    self._lookup[key] = City(sorted(canonical, key=lambda v: v.city)[0].city, '', '')
        self.max_words = max((len(k.split()) for k in self._lookup),default=0)

    @classmethod
    def from_sqlite(cls, path: str | Path) -> 'CityCatalog':
        """Load the prototype's canonical names/aliases, not a second database."""
        from match_city import CityMatcher
        with CityMatcher(path) as matcher:
            aliases = {}
            for row in matcher.connection.execute('SELECT city_id,name FROM city_names WHERE is_canonical=0'):
                aliases.setdefault(row[0], []).append(row[1])
            cities = []
            for city_id, name, geography in matcher.connection.execute('SELECT city_id,canonical_city,region FROM cities'):
                region, country = _geography(geography)
                cities.append(City(name, region, country, tuple(aliases.get(city_id, ()))))
        return cls(cities)

    def lookup_exact(self, text: str) -> City | None:
        """Return a uniquely represented complete city name, never a substring."""
        return self._lookup.get(_canonical_key(text))

    @property
    def lookup_keys(self) -> frozenset[str]:
        """Recognized normalized spellings; ambiguous geography remains unset."""
        return frozenset(self._lookup)

    def suffix_match(self, raw: str) -> tuple[str, City] | None:
        """Longest whole-token suffix; no prefix-substring or ambiguous alias."""
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
        raw_date: str = '',
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
        # The caller has already independently parsed the complete date.  Its
        # source spelling may be dotted, slash-separated or textual, while
        # the normalized date is always YYYY-MM-DD.  Match that exact trusted
        # source span rather than guessing a new date from city text.
        date_text = raw_date or date
        date_hit = re.search(r'(?<!\d)'+re.escape(date_text)+r'(?!\d)',remainder,re.I)
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
            # New York without a delimiter may be part of a venue/title.
            if venue_prefix and not explicit_delimiter and city_key == 'new york':
                continue
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
    raw_date: str = '',
    db_path: str | Path | None = None,
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
            catalog = _load_path(Path(db_path)) if db_path is not None else catalog_for_tlo()
        if catalog is None:
            return fields
    except (OSError, ValueError, sqlite3.Error) as exc:
        # Missing/corrupt optional city data must NEVER abort an inventory.
        if on_warning is not None:
            on_warning(f'City catalog unavailable; old parsing preserved: {exc}')
        return fields
    candidate = catalog.suggest_for_known_artist(
        folder_name,artist=artist,date=date,artist_names=artist_names,
        artist_is_known=artist_is_known, raw_date=raw_date,
        existing_city=city,existing_region=region,existing_country=country)
    if candidate is None:
        return fields
    fields['city']=candidate.city
    # City-name recognition is not geographic proof. Do not silently append
    # a region or country that was absent from the folder or metadata.
    # Venue remains untouched until independently validated by existing logic.
    return fields


def _geography(value: str) -> tuple[str, str]:
    """Map the prototype's single region field to the legacy two-field API."""
    if value in US_STATES:
        return value, 'United States'
    if value in CA_PROVS:
        return value, 'Canada'
    if compact_city_key(value) in GB_LABELS | {'nireland'}:
        return '', 'UK'
    if value in {'NSW', 'QLD', 'New South Wales', 'South Australia', 'Tasmania', 'Victoria, Australia', 'Western Australia'}:
        return value, 'Australia'
    if value == 'PA - USA':
        return 'PA', 'United States'
    if value in {'Tokyo', 'Kanagawa'}:
        return value, 'Japan'
    if value == 'Tatarstan':
        return value, 'Russia'
    return '', value


def catalog_path_for_tlo(tlo_dbs_dir: str = '', tlo_home: str = '') -> Path | None:
    """Resolve only the active TLOHome/TLO_DBs; never use an application copy."""
    home = tlo_home
    root = Path(tlo_dbs_dir) if tlo_dbs_dir else (Path(home) / 'TLO_DBs' if home else None)
    return root / 'cities.sqlite' if root is not None else None


@lru_cache(maxsize=16)
def _cached_catalog(path: str, stamp: tuple[int, int]) -> CityCatalog:
    return CityCatalog.from_sqlite(path)


def _load_path(path: Path) -> CityCatalog:
    stat = path.stat()
    return _cached_catalog(str(path.resolve()), (stat.st_mtime_ns, stat.st_size))


_REPORTED_ISSUES: set[str] = set()


def catalog_for_tlo(tlo_dbs_dir: str = '', tlo_home: str = '', on_warning=None) -> CityCatalog | None:
    """Use only the active TLOHome SQLite master.

    Missing/corrupt data is not evidence against a city. Never read legacy CSV.
    """
    try:
        path = catalog_path_for_tlo(tlo_dbs_dir, tlo_home)
        if path is None:
            return None
        return _load_path(path)
    except (OSError, ValueError, sqlite3.Error) as exc:
        message = f"SQLite city reference unavailable; original parsing retained: {exc}"
        if message not in _REPORTED_ISSUES:
            _REPORTED_ISSUES.add(message)
            logging.getLogger(__name__).warning('%s', message)
        if on_warning:
            on_warning(message)
        return None
