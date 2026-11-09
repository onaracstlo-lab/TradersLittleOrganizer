#!/usr/bin/env python3
"""Create a high-precision, comma-delimited TLO city dictionary from the provided GeoNames excerpts.

Source: GeoNames (https://www.geonames.org/), CC BY 4.0.
This tool deliberately prefers omissions to ambiguous matches and never guesses geography.
"""
from __future__ import annotations

import argparse
import collections
import csv
import re
import unicodedata
from pathlib import Path

# Only these very familiar names may be recognized even though the supplied
# source does not establish a unique country. Their country stays BLANK.
KEEP_UNLOCATED = frozenset({
    'Amsterdam', 'Athens', 'Barcelona', 'Belfast', 'Birmingham', 'Boston',
    'Cambridge', 'Dublin', 'Florence', 'Geneva', 'Glasgow', 'Hamburg',
    'Liverpool', 'London', 'Los Angeles', 'Madrid', 'Manchester',
    'Melbourne', 'Memphis', 'Miami', 'Montreal', 'Moscow', 'New Orleans',
    'Paris', 'Philadelphia', 'Phoenix', 'Portland', 'Rome', 'San Francisco',
    'San Jose', 'Seattle', 'Sydney', 'Tokyo', 'Toronto', 'Vancouver',
    'Aberdeen', 'Albany', 'Bergen', 'Bolton', 'Brighton', 'Bristol', 'Chelmsford',
    'Cheltenham', 'Christchurch', 'Colchester', 'Coventry', 'Dundee', 'Durham',
    'Edmonton', 'Gloucester', 'Halifax', 'Hamilton', 'Kingston', 'Lancaster',
    'Limerick', 'Northampton', 'Norwich', 'Oxford', 'Perth', 'Peterborough',
    'Plymouth', 'Portsmouth', 'Preston', 'Richmond', 'Swansea', 'Wellington',
    'Windsor', 'Worcester', 'York', 'Saint Paul',
})
# Census-like neighbourhood/district descriptors were mixed into the source.
# Prefer to miss these rather than mistake a venue or label for a city.
UNSAFE_DESCRIPTOR = re.compile(
    r'(?i)(?:^downtown\b|^city of\b|\bfinancial district\b|'
    r'\bcity centre\b|\bcity center\b|\bnew town\b|'
    r'\bindustrial area\b|\bcommercial city\b|'
    r'\bkoreatown\b|\b(?:east|west) village\b|'
    r'\b(?:business|financial) bay\b|\bborough park\b)'
)


def key(s: str) -> str:
    s = ''.join(ch for ch in unicodedata.normalize('NFKD', s.casefold())
                if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]+', '', s)


def load_input(p: Path, columns: int) -> list[list[str]]:
    with p.open('r', encoding='utf-8-sig', newline='') as f:
        return [[c.strip() for c in row] for row in csv.reader(f, delimiter='^')
                if row and not row[0].startswith('#') and any(c.strip() for c in row)]


def make_csv(source: Path, candidates: Path, dest: Path) -> dict[str, int]:
    src = load_input(source, 4)
    cand = load_input(candidates, 5)
    if src[0] != ['city','region','country','aliases']:
        raise ValueError('Unexpected source header')
    if cand[0] != ['city','region','country','aliases','reason']:
        raise ValueError('Unexpected exclusions header')
    rejected = {key(r[0]) for r in cand[1:] if len(r) == 5}
    rejected.update(key(a) for r in cand[1:] if len(r) == 5
                    for a in r[3].split('|') if a.strip())
    counts = collections.Counter()
    raw: list[tuple[str, str, str, list[str]]] = []
    for row in src[1:]:
        if len(row) != 4 or not row[0]:
            counts['invalid_or_metadata'] += 1
            continue
        city, region, country, alias_text = row
        k = key(city)
        if not k or k in rejected:
            counts['excluded_common_word_or_music'] += 1
            continue
        if UNSAFE_DESCRIPTOR.search(city):
            counts['excluded_generic_district'] += 1
            continue
        if not country and city not in KEEP_UNLOCATED:
            counts['excluded_uncertain_geography'] += 1
            continue
        raw.append((city, region, country, [a.strip() for a in alias_text.split('|') if a.strip()]))
    # Normalization collisions can be homonyms in unrelated countries.
    groups: dict[str, list[tuple[str,str,str,list[str]]]] = collections.defaultdict(list)
    for row in raw:
        groups[key(row[0])].append(row)
    picked: list[tuple[str, str, str, list[str]]] = []
    for grp in groups.values():
        places = {(r[1].casefold(), r[2].casefold()) for r in grp}
        if len(places) != 1:
            # Keep a curated shortlist of distinct concert-city names as
            # name-only records. Never choose a country for a homonym.
            if grp[0][0] in KEEP_UNLOCATED:
                preferred = next((r for r in grp if r[0] == grp[0][0] and r[2] == 'United States'), grp[0])
                aliases = list(dict.fromkeys(a for r in grp for a in r[3]))
                picked.append((preferred[0], '', '', aliases))
                counts['collapsed_uncertain_homonyms'] += len(grp)
                continue
            counts['excluded_place_name_collision'] += len(grp)
            continue
        # Merge same-place spelling variants conservatively, no invented region/country.
        first = grp[0]
        alts = [a for r in grp for a in [r[0], *r[3]] if a.casefold() != first[0].casefold()]
        picked.append((first[0], first[1], first[2], alts))
        counts['merged_same_place_variants'] += len(grp) - 1
    # If an alias is ambiguous, drop the ALIAS, not the city record.
    # A risky alias may never override a different primary city name.
    primary = collections.defaultdict(set)
    for row in picked: primary[key(row[0])].add(row[0])
    aliases = collections.defaultdict(set)
    for row in picked:
        for a in row[3]: aliases[key(a)].add(row[0])
    result = []
    for city,region,country,raw_aliases in picked:
        accepted = []
        seen = set()
        for a in raw_aliases:
            ak = key(a)
            if (not ak or a.casefold() == city.casefold() or ak in rejected
                or UNSAFE_DESCRIPTOR.search(a) or a.casefold() in seen
                or len(aliases[ak]) > 1
                or (ak in primary and city not in primary[ak])):
                counts['excluded_ambiguous_alias'] += 1
                continue
            seen.add(a.casefold())
            accepted.append(a)
        result.append((city, region, country, '|'.join(accepted)))
    result.sort(key=lambda r: (r[0].casefold(), r[2].casefold(), r[1].casefold()))
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open('w', encoding='utf-8-sig', newline='') as f:
        out = csv.writer(f, dialect='excel', lineterminator='\n')
        out.writerow(['city','region','country','aliases'])
        out.writerows(result)
    counts['source_records'] = len(src)-1
    counts['common_word_candidates_screened'] = len(cand)-1
    counts['output_cities'] = len(result)
    counts['output_aliases'] = sum(len(r[3].split('|')) for r in result if r[3])
    counts['output_unknown_country'] = sum(not r[2] for r in result)
    return dict(counts)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('source', type=Path)
    ap.add_argument('candidates', type=Path)
    ap.add_argument('output', type=Path)
    args = ap.parse_args()
    for name,count in sorted(make_csv(args.source,args.candidates,args.output).items()):
        print(f'{name}: {count}')

if __name__ == '__main__':
    main()
