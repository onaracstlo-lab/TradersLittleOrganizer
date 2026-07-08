#!/usr/bin/env python3
"""
tlo_etree_lookup.py

Look up eTreeDB venue/location and setlist text for a performance given:

    artist yyyy-mm-dd

Example:
    python tlo_etree_lookup.py "Bob Dylan" 1975-11-13
    python tlo_etree_lookup.py "Bob Dylan" 1975-11-13 --debug

Important:
    This intentionally does NOT use the top-level performances(...) query,
    because that can throw an eTreeDB internal server error.

    Instead:
      1. Resolve exact artist through artistsRoot(name eq ...)
      2. Use the nested Artist.performances relationship
      3. Filter nested performances by year
      4. Retrieve set1/set2/set3 for tagging title fallback
      5. Normalize/match the returned date locally
"""

from __future__ import annotations

__version__ = "v324"
# TLO-GI package version: v324
__version_summary__ = 'Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.'
# TLO-GI version summary: Makes Add Shows honor Tag in Place for regular and duplicate incremental add workflows.


import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from console_output_lib import console_emit


GRAPHQL_URL = "https://graphql.etreedb.org"


@dataclass(frozen=True)
class PerformanceResult:
    artist_id: int
    artist: str
    performance_id: int
    raw_date: str
    normalized_date: str | None
    title: str
    venue: str
    city: str
    state: str
    year: int | None
    set1: str = ""
    set2: str = ""
    set3: str = ""

    @property
    def location(self) -> str:
        parts = [x.strip() for x in (self.city, self.state) if x and x.strip()]
        return ", ".join(parts)

    @property
    def numbered_setlists(self) -> list[tuple[int, str]]:
        numbered = [
            (1, self.set1),
            (2, self.set2),
            (3, self.set3),
        ]
        return [(number, text.strip()) for number, text in numbered if text and text.strip()]

    @property
    def setlists_in_order(self) -> list[str]:
        return [text for _number, text in self.numbered_setlists]


class ETreeDBError(RuntimeError):
    pass


def validate_yyyy_mm_dd(date_text: str) -> str:
    date_text = date_text.strip()

    if not re.fullmatch(r"(?:19|20)\d{2}-\d{2}-\d{2}", date_text):
        raise ValueError(f"Date must be yyyy-mm-dd: {date_text!r}")

    try:
        datetime.strptime(date_text, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(f"Invalid date: {date_text!r}") from e

    return date_text


def normalize_text(text: str) -> str:
    text = (text or "").casefold()
    text = text.replace("&", " and ")
    text = re.sub(r"^the\s+", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def exact_artist_name_candidates(artist_name: str) -> list[str]:
    raw = " ".join(artist_name.strip().split())
    candidates: list[str] = []

    def add(value: str) -> None:
        value = " ".join(value.strip().split())
        if value and value not in candidates:
            candidates.append(value)

    add(raw)

    if "," in raw:
        left, right = raw.split(",", 1)
        add(f"{right.strip()} {left.strip()}")
    else:
        words = raw.split()
        if len(words) >= 2:
            add(f"{words[-1]}, {' '.join(words[:-1])}")

    return candidates


def normalize_etree_date(raw_date: str) -> str | None:
    """
    Normalize common eTreeDB date strings to yyyy-mm-dd.

    Handles:
        1975-11-13
        1975/11/13
        1975.11.13
        11/13/1975
        11-13-1975
        11/13/75
        November 13, 1975
        Nov 13 1975
        13 Nov 1975
        1975-11-13 Early Show
    """
    text = (raw_date or "").strip()
    if not text:
        return None

    numeric_patterns = [
        r"(?<!\d)(?P<y>(?:19|20)\d{2})[-/.](?P<m>\d{1,2})[-/.](?P<d>\d{1,2})(?!\d)",
        r"(?<!\d)(?P<m>\d{1,2})[-/.](?P<d>\d{1,2})[-/.](?P<y>(?:(?:19|20)\d{2}|\d{2}))(?!\d)",
    ]

    for pattern in numeric_patterns:
        match = re.search(pattern, text)
        if not match:
            continue

        year = int(match.group("y"))
        month = int(match.group("m"))
        day = int(match.group("d"))

        if year < 100:
            year += 1900 if year >= 50 else 2000
        if year < 1900 or year > 2099:
            continue

        try:
            return datetime(year, month, day).strftime("%Y-%m-%d")
        except ValueError:
            pass

    month_names = {
        "jan": 1,
        "january": 1,
        "feb": 2,
        "february": 2,
        "mar": 3,
        "march": 3,
        "apr": 4,
        "april": 4,
        "may": 5,
        "jun": 6,
        "june": 6,
        "jul": 7,
        "july": 7,
        "aug": 8,
        "august": 8,
        "sep": 9,
        "sept": 9,
        "september": 9,
        "oct": 10,
        "october": 10,
        "nov": 11,
        "november": 11,
        "dec": 12,
        "december": 12,
    }

    cleaned = re.sub(r",", " ", text.casefold())
    cleaned = re.sub(r"(\d+)(?:st|nd|rd|th|ST|ND|RD|TH)\b", r"\1", cleaned)
    tokens = cleaned.split()

    for i in range(len(tokens) - 2):
        a, b, c = tokens[i], tokens[i + 1], tokens[i + 2]

        if a in month_names and b.isdigit() and c.isdigit():
            try:
                year = int(c)
                if year < 100:
                    year += 1900 if year >= 50 else 2000
                if year < 1900 or year > 2099:
                    continue
                return datetime(year, month_names[a], int(b)).strftime("%Y-%m-%d")
            except ValueError:
                pass

        if a.isdigit() and b in month_names and c.isdigit():
            try:
                year = int(c)
                if year < 100:
                    year += 1900 if year >= 50 else 2000
                if year < 1900 or year > 2099:
                    continue
                return datetime(year, month_names[b], int(a)).strftime("%Y-%m-%d")
            except ValueError:
                pass

    return None


def graphql_request(
    query: str,
    variables: dict[str, Any],
    timeout_seconds: int = 30,
) -> dict[str, Any]:
    payload = json.dumps(
        {
            "query": query,
            "variables": variables,
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "tlo-etreedb-venue-lookup/6.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            response_body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise ETreeDBError(f"HTTP {e.code} from eTreeDB GraphQL: {body}") from e
    except urllib.error.URLError as e:
        raise ETreeDBError(f"Could not reach eTreeDB GraphQL: {e}") from e

    try:
        decoded = json.loads(response_body)
    except json.JSONDecodeError as e:
        raise ETreeDBError(f"GraphQL response was not JSON: {response_body[:500]}") from e

    if decoded.get("errors"):
        raise ETreeDBError(json.dumps(decoded["errors"], indent=2, ensure_ascii=False))

    return decoded.get("data") or {}


def connection_nodes(connection: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not connection:
        return []

    nodes: list[dict[str, Any]] = []

    for edge in connection.get("edges") or []:
        if isinstance(edge, dict) and isinstance(edge.get("node"), dict):
            nodes.append(edge["node"])

    return nodes


def page_info(connection: dict[str, Any] | None) -> dict[str, Any]:
    if not connection:
        return {}

    info = connection.get("pageInfo")
    return info if isinstance(info, dict) else {}


ARTIST_PERFORMANCES_FIRST_PAGE_QUERY = """
query ArtistPerformancesFirstPage(
  $artistName: String!,
  $year: Int!,
  $first: Int!
) {
  artistsRoot(
    filter: {
      name: { eq: $artistName }
    }
    pagination: {
      first: 5
    }
  ) {
    totalCount
    edges {
      node {
        id
        name
        nameNormalized
        performances(
          filter: {
            year: { eq: $year }
          }
          pagination: {
            first: $first
          }
        ) {
          totalCount
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            node {
              id
              date
              year
              title
              venue
              city
              state
              set1
              set2
              set3
            }
          }
        }
      }
    }
  }
}
"""


ARTIST_PERFORMANCES_NEXT_PAGE_QUERY = """
query ArtistPerformancesNextPage(
  $artistName: String!,
  $year: Int!,
  $first: Int!,
  $after: String!
) {
  artistsRoot(
    filter: {
      name: { eq: $artistName }
    }
    pagination: {
      first: 5
    }
  ) {
    totalCount
    edges {
      node {
        id
        name
        nameNormalized
        performances(
          filter: {
            year: { eq: $year }
          }
          pagination: {
            first: $first
            after: $after
          }
        ) {
          totalCount
          pageInfo {
            hasNextPage
            endCursor
          }
          edges {
            node {
              id
              date
              year
              title
              venue
              city
              state
              set1
              set2
              set3
            }
          }
        }
      }
    }
  }
}
"""


def performance_from_node(
    artist_id: int,
    artist_name: str,
    node: dict[str, Any],
) -> PerformanceResult | None:
    try:
        performance_id = int(node["id"])
    except (KeyError, TypeError, ValueError):
        return None

    raw_date = str(node.get("date") or "").strip()

    try:
        year_value = int(node["year"]) if node.get("year") is not None else None
    except (TypeError, ValueError):
        year_value = None

    return PerformanceResult(
        artist_id=artist_id,
        artist=artist_name,
        performance_id=performance_id,
        raw_date=raw_date,
        normalized_date=normalize_etree_date(raw_date),
        title=str(node.get("title") or "").strip(),
        venue=str(node.get("venue") or "").strip(),
        city=str(node.get("city") or "").strip(),
        state=str(node.get("state") or "").strip(),
        year=year_value,
        set1=str(node.get("set1") or "").strip(),
        set2=str(node.get("set2") or "").strip(),
        set3=str(node.get("set3") or "").strip(),
    )


def fetch_exact_artist_year_performances(
    requested_artist: str,
    year: int,
    page_size: int = 250,
    max_pages: int = 20,
    debug: bool = False,
) -> list[PerformanceResult]:
    requested_norm = normalize_text(requested_artist)
    all_results: list[PerformanceResult] = []

    for exact_name in exact_artist_name_candidates(requested_artist):
        after: str | None = None

        for page_number in range(max_pages):
            if after:
                query = ARTIST_PERFORMANCES_NEXT_PAGE_QUERY
                variables = {
                    "artistName": exact_name,
                    "year": year,
                    "first": page_size,
                    "after": after,
                }
            else:
                query = ARTIST_PERFORMANCES_FIRST_PAGE_QUERY
                variables = {
                    "artistName": exact_name,
                    "year": year,
                    "first": page_size,
                }

            data = graphql_request(query, variables)
            artists_connection = data.get("artistsRoot")
            artist_nodes = connection_nodes(artists_connection)


            matched_any_artist = False
            next_after: str | None = None

            for artist_node in artist_nodes:
                try:
                    artist_id = int(artist_node["id"])
                except (KeyError, TypeError, ValueError):
                    continue

                returned_artist_name = str(artist_node.get("name") or "").strip()
                returned_artist_norm = normalize_text(returned_artist_name)
                returned_normalized_norm = normalize_text(
                    str(artist_node.get("nameNormalized") or "")
                )

                # Exact only. Do not allow "Bob Dylan and The Band" here.
                if requested_norm not in {returned_artist_norm, returned_normalized_norm}:
                    if debug:
                        console_emit(
                            f"DEBUG: rejecting non-exact artist "
                            f"id={artist_id}, name={returned_artist_name!r}",
                            error=True,
                        )
                    continue

                matched_any_artist = True

                performances_connection = artist_node.get("performances")
                perf_nodes = connection_nodes(performances_connection)


                for perf_node in perf_nodes:
                    result = performance_from_node(
                        artist_id=artist_id,
                        artist_name=returned_artist_name,
                        node=perf_node,
                    )
                    if result is not None:
                        all_results.append(result)

                info = page_info(performances_connection)
                if info.get("hasNextPage") and info.get("endCursor"):
                    next_after = str(info["endCursor"])

            if not matched_any_artist:
                break

            if not next_after:
                break

            after = next_after

        if all_results:
            break

    return all_results


def lookup_venue_location_and_setlists(
    artist: str,
    date_yyyy_mm_dd: str,
    debug: bool = False,
) -> list[PerformanceResult]:
    wanted_date = validate_yyyy_mm_dd(date_yyyy_mm_dd)
    wanted_year = int(wanted_date[:4])

    year_results = fetch_exact_artist_year_performances(
        requested_artist=artist,
        year=wanted_year,
        debug=debug,
    )

    # Debug output intentionally avoids dumping every returned performance.
    # Routine matches are normal; callers should report only anomalies.

    return [
        result
        for result in year_results
        if result.normalized_date == wanted_date
    ]



def lookup_venue_and_location(
    artist: str,
    date_yyyy_mm_dd: str,
    debug: bool = False,
) -> list[PerformanceResult]:
    """Backward-compatible venue/location lookup wrapper."""
    return lookup_venue_location_and_setlists(
        artist=artist,
        date_yyyy_mm_dd=date_yyyy_mm_dd,
        debug=debug,
    )


LEADING_TRACK_NUMBER_RE = re.compile(
    r"^\s*(?P<number>\d{1,3})(?:\s*[\.\)\]\:;\-–—]+\s*|\s+)(?P<title>\S.*)$"
)


def decode_etree_text(text: str) -> str:
    """Convert eTreeDB's escaped greater-than marker to a plain > character."""
    return (text or "").replace("&gt;", ">").replace("&gt", ">")


def is_encore_only_line(line: str) -> bool:
    """Return True for lines that are only an encore marker."""
    match = re.match(r"^\s*encore\b(?P<suffix>.*)$", line or "", flags=re.IGNORECASE)
    if not match:
        return False
    return re.search(r"[A-Za-z0-9]", match.group("suffix")) is None


def normalize_or_assign_track_number(line: str, next_number: int) -> tuple[str, int]:
    """Normalize an existing leading track number or assign the next continuous number."""
    stripped = line.strip()
    match = LEADING_TRACK_NUMBER_RE.match(stripped)
    if match:
        number = int(match.group("number"))
        title = match.group("title").strip()
        return f"{number:02d} {title}", max(next_number, number + 1)
    return f"{next_number:02d} {stripped}", next_number + 1


def split_single_line_comma_song_list(text: str) -> list[str] | None:
    """Split a single-line comma-delimited eTreeDB setlist into song-title items."""
    non_empty_lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if len(non_empty_lines) != 1:
        return None
    line = non_empty_lines[0]
    if "," not in line:
        return None
    raw_items = [item.strip() for item in line.split(",")]
    if len(raw_items) < 2 or any(not item for item in raw_items):
        return None
    items = [item for item in raw_items if not is_encore_only_line(item)]
    if len(items) < 2:
        return None
    return items


def normalize_setlists_for_output(raw_setlists: list[str]) -> list[str]:
    """Normalize returned eTreeDB setlist text into numbered song-title lines."""
    normalized_setlists: list[str] = []
    next_number = 1
    for raw_setlist in raw_setlists:
        output_lines: list[str] = []
        decoded = decode_etree_text(raw_setlist)
        comma_items = split_single_line_comma_song_list(decoded)
        candidate_lines = comma_items if comma_items is not None else decoded.splitlines()
        for raw_line in candidate_lines:
            line = raw_line.strip()
            if not line:
                continue
            if is_encore_only_line(line):
                continue
            normalized_line, next_number = normalize_or_assign_track_number(
                line=line,
                next_number=next_number,
            )
            output_lines.append(normalized_line)
        if output_lines:
            normalized_setlists.append("\n".join(output_lines))
    return normalized_setlists


def collect_setlists_in_order(results: list[PerformanceResult]) -> list[str]:
    """Collect normalized non-empty setlists in result order, then set1/set2/set3 order."""
    raw_setlists: list[str] = []
    for result in results:
        raw_setlists.extend(result.setlists_in_order)
    return normalize_setlists_for_output(raw_setlists)


def collect_setlists_by_performance(
    results: list[PerformanceResult],
) -> list[tuple[PerformanceResult, list[str]]]:
    """Return one combined normalized setlist candidate per performance.

    set1/set2/set3 are combined inside a single performance, but separate
    matching performances remain separate candidates so callers can choose the
    best performance instead of flattening unrelated shows together.
    """
    candidates: list[tuple[PerformanceResult, list[str]]] = []
    for result in results:
        normalized_setlists = normalize_setlists_for_output(result.setlists_in_order)
        if normalized_setlists:
            candidates.append((result, normalized_setlists))
    return candidates


def lookup_setlists_by_performance(
    artist: str,
    date_yyyy_mm_dd: str,
    debug: bool = False,
) -> list[tuple[PerformanceResult, list[str]]]:
    """Return normalized eTreeDB setlist candidates for each exact artist/date performance."""
    return collect_setlists_by_performance(
        lookup_venue_location_and_setlists(artist=artist, date_yyyy_mm_dd=date_yyyy_mm_dd, debug=debug)
    )


def lookup_setlists_for_performance(artist: str, date_yyyy_mm_dd: str, debug: bool = False) -> list[str]:
    """Return normalized eTreeDB setlist text for exact artist/date, or an empty list.

    Backward-compatible wrapper. New tagging code should prefer
    lookup_setlists_by_performance() so multiple matching performances do not
    get flattened into one synthetic setlist.
    """
    return collect_setlists_in_order(
        lookup_venue_location_and_setlists(artist=artist, date_yyyy_mm_dd=date_yyyy_mm_dd, debug=debug)
    )

def print_results(results: list[PerformanceResult], silent: bool = False) -> None:
    for result in results:
        console_emit(f"ARTIST: {result.artist}", silent=silent)
        console_emit(f"DATE: {result.raw_date}", silent=silent)
        console_emit(f"NORMALIZED_DATE: {result.normalized_date or ''}", silent=silent)
        console_emit(f"TITLE: {result.title}", silent=silent)
        console_emit(f"VENUE: {result.venue}", silent=silent)
        console_emit(f"LOCATION: {result.location}", silent=silent)
        console_emit(f"CITY: {result.city}", silent=silent)
        console_emit(f"STATE: {result.state}", silent=silent)
        console_emit(f"YEAR: {result.year if result.year is not None else ''}", silent=silent)
        console_emit(f"SETLIST_COUNT: {len(result.numbered_setlists)}", silent=silent)
        console_emit(f"ARTIST_ID: {result.artist_id}", silent=silent)
        console_emit(f"PERFORMANCE_ID: {result.performance_id}", silent=silent)
        console_emit("", silent=silent)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Look up eTreeDB venue/location by exact artist and yyyy-mm-dd date."
    )

    parser.add_argument(
        "artist",
        help='Exact artist name. Example: "Bob Dylan"',
    )

    parser.add_argument(
        "date",
        help="Performance date in yyyy-mm-dd format. Example: 1975-11-13",
    )

    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print exact artist/year performances and raw date strings to stderr.",
    )

    parser.add_argument(
        "--silent",
        action="store_true",
        help="Suppress non-error console output.",
    )

    args = parser.parse_args()

    try:
        results = lookup_venue_and_location(
            artist=args.artist,
            date_yyyy_mm_dd=args.date,
            debug=args.debug,
        )
    except Exception as e:
        console_emit(f"ERROR: {e}", error=True)
        return 2

    if not results:
        console_emit(f"No matching performance found for exact artist {args.artist} on {args.date}.", silent=args.silent)
        console_emit("Run with --debug to see the raw returned dates for that exact artist/year.", silent=args.silent)
        return 1

    print_results(results, silent=args.silent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
