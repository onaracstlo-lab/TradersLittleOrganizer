#!/usr/bin/env python3
"""
setlistFM.py

Look up venue and location for a setlist.fm performance by artist and date.

Usage:
    setlistFM.py "Bob Dylan" 1997-12-12

Requires a setlist.fm API key in the environment:
    export SETLISTFM_API_KEY="your-api-key-here"

Windows PowerShell:
    $env:SETLISTFM_API_KEY="your-api-key-here"

The input date is yyyy-mm-dd. The setlist.fm API search date is dd-MM-yyyy.
"""

from __future__ import annotations

__version__ = "v324"
# TLO-GI package version: v324
__version_summary__ = 'Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.'
# TLO-GI version summary: Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.


import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from console_output_lib import console_emit

VERSION = "1.0"
API_BASE = "https://api.setlist.fm/rest/1.0"
ENV_API_KEY = "SETLISTFM_API_KEY"


@dataclass(frozen=True)
class PerformanceResult:
    artist: str
    event_date: str
    venue: str
    location: str
    city: str
    state: str
    state_code: str
    country: str
    country_code: str
    setlist_url: str
    venue_url: str


def normalize_name(value: str) -> str:
    """Normalize an artist name for loose exact matching."""
    value = value.casefold().strip()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def convert_date_for_api(date_text: str) -> str:
    """Convert yyyy-mm-dd to setlist.fm API format dd-MM-yyyy."""
    try:
        parsed = datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"date must be yyyy-mm-dd, got: {date_text!r}") from exc
    return parsed.strftime("%d-%m-%Y")


def get_api_key() -> str:
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if not api_key:
        raise RuntimeError(
            f"Missing API key. Set {ENV_API_KEY} first.\n"
            f"Example: export {ENV_API_KEY}=\"your-api-key-here\""
        )
    return api_key


def api_get(path: str, params: Dict[str, str], api_key: str) -> Dict[str, Any]:
    query = urllib.parse.urlencode(params)
    url = f"{API_BASE}{path}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "en",
            "x-api-key": api_key,
            "User-Agent": f"setlistFM.py/{VERSION}",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"setlist.fm API request failed: HTTP {exc.code} {exc.reason}\n{detail}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"setlist.fm API request failed: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"setlist.fm returned non-JSON response:\n{body[:1000]}") from exc


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def compact_join(parts: Iterable[str], separator: str = ", ") -> str:
    return separator.join(part for part in parts if part)


def parse_result(setlist: Dict[str, Any]) -> PerformanceResult:
    artist = setlist.get("artist") or {}
    venue = setlist.get("venue") or {}
    city = venue.get("city") or {}
    country = city.get("country") or {}

    city_name = str(city.get("name") or "").strip()
    state = str(city.get("state") or "").strip()
    state_code = str(city.get("stateCode") or "").strip()
    country_name = str(country.get("name") or "").strip()
    country_code = str(country.get("code") or "").strip()

    region = state_code or state
    location = compact_join([city_name, region, country_name])

    return PerformanceResult(
        artist=str(artist.get("name") or "").strip(),
        event_date=str(setlist.get("eventDate") or "").strip(),
        venue=str(venue.get("name") or "").strip(),
        location=location,
        city=city_name,
        state=state,
        state_code=state_code,
        country=country_name,
        country_code=country_code,
        setlist_url=str(setlist.get("url") or "").strip(),
        venue_url=str(venue.get("url") or "").strip(),
    )


def search_setlists(artist: str, date_yyyy_mm_dd: str, api_key: str) -> List[PerformanceResult]:
    api_date = convert_date_for_api(date_yyyy_mm_dd)
    payload = api_get(
        "/search/setlists",
        {
            "artistName": artist,
            "date": api_date,
            "p": "1",
        },
        api_key,
    )

    raw_setlists = ensure_list(payload.get("setlist"))
    results = [parse_result(item) for item in raw_setlists if isinstance(item, dict)]

    wanted = normalize_name(artist)
    exact_artist_results = [result for result in results if normalize_name(result.artist) == wanted]

    # setlist.fm artistName search can be broad. Prefer exact artist-name matches,
    # but return broader matches when no exact result is found.
    return exact_artist_results or results


def print_result(result: PerformanceResult, index: Optional[int] = None, silent: bool = False) -> None:
    prefix = f"MATCH {index}: " if index is not None else ""
    console_emit(f"{prefix}ARTIST: {result.artist}", silent=silent)
    console_emit(f"EVENT_DATE: {result.event_date}", silent=silent)
    console_emit(f"VENUE: {result.venue}", silent=silent)
    console_emit(f"LOCATION: {result.location}", silent=silent)
    console_emit(f"CITY: {result.city}", silent=silent)
    console_emit(f"STATE: {result.state}", silent=silent)
    console_emit(f"STATE_CODE: {result.state_code}", silent=silent)
    console_emit(f"COUNTRY: {result.country}", silent=silent)
    console_emit(f"COUNTRY_CODE: {result.country_code}", silent=silent)
    console_emit(f"SETLIST_URL: {result.setlist_url}", silent=silent)
    console_emit(f"VENUE_URL: {result.venue_url}", silent=silent)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setlistFM.py",
        description="Look up venue and location at setlist.fm for an artist and yyyy-mm-dd date.",
    )
    parser.add_argument("artist", help='artist name, e.g. "Bob Dylan"')
    parser.add_argument("date", help="performance date in yyyy-mm-dd format")
    parser.add_argument("--silent", action="store_true", help="Suppress non-error console output.")
    parser.add_argument("--version", action="version", version=f"setlistFM.py v{VERSION}")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        api_key = get_api_key()
        results = search_setlists(args.artist, args.date, api_key)
    except Exception as exc:
        console_emit(f"ERROR: {exc}", error=True)
        return 1

    if not results:
        console_emit(f"No matching performance found for {args.artist} on {args.date}", silent=args.silent)
        return 2

    if len(results) == 1:
        print_result(results[0], silent=args.silent)
    else:
        console_emit(f"Multiple matching performances found: {len(results)}", silent=args.silent)
        for index, result in enumerate(results, start=1):
            if index > 1:
                console_emit("", silent=args.silent)
            print_result(result, index=index, silent=args.silent)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
