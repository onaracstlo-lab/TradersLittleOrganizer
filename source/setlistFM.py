#!/usr/bin/env python3
"""Compatibility CLI wrapper over the production setlist.fm lookup module."""
from __future__ import annotations

__version__ = "v415"

import argparse
from typing import Optional, List

from console_output_lib import console_emit
from tlo_path_inputs import resolve_tlo_home
from tlo_setlistfm_lookup import SetlistFMError, search_setlists
from tlo_version import DISPLAY_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="setlistFM.py",
        description="Rate-limited setlist.fm venue/location lookup for an artist and yyyy-mm-dd date.",
    )
    parser.add_argument("artist")
    parser.add_argument("date")
    parser.add_argument("--TLOHome", dest="TLOHome", default="")
    parser.add_argument("--myTLO", dest="myTLO", default="", help=argparse.SUPPRESS)
    parser.add_argument("--silent", action="store_true")
    parser.add_argument("--version", action="version", version=f"setlistFM.py {DISPLAY_VERSION}")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        tlo_home = resolve_tlo_home(args.TLOHome, args.myTLO, error_type=SetlistFMError)
        results = search_setlists(args.artist, args.date, tlo_home=tlo_home, run_id="setlistFM-cli")
    except Exception as exc:  # noqa: BLE001 - CLI-safe boundary
        console_emit(f"ERROR: {exc}", error=True)
        return 1
    if not results:
        console_emit(f"No matching performance found for {args.artist} on {args.date}", silent=args.silent)
        return 2
    for index, result in enumerate(results, start=1):
        if len(results) > 1:
            console_emit(f"MATCH {index}", silent=args.silent)
        console_emit(f"ARTIST: {result.artist}", silent=args.silent)
        console_emit(f"EVENT_DATE: {result.event_date}", silent=args.silent)
        console_emit(f"VENUE: {result.venue}", silent=args.silent)
        console_emit(f"LOCATION: {result.location}", silent=args.silent)
        console_emit(f"CITY: {result.city}", silent=args.silent)
        console_emit(f"STATE: {result.state}", silent=args.silent)
        console_emit(f"STATE_CODE: {result.state_code}", silent=args.silent)
        console_emit(f"COUNTRY: {result.country}", silent=args.silent)
        console_emit(f"COUNTRY_CODE: {result.country_code}", silent=args.silent)
        console_emit(f"SETLIST_URL: {result.setlist_url}", silent=args.silent)
        console_emit(f"VENUE_URL: {result.venue_url}", silent=args.silent)
        if index != len(results):
            console_emit("", silent=args.silent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
