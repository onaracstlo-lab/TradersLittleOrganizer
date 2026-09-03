#!/usr/bin/env python3
"""Standalone TLO Research console application."""

__version__ = "v426"

import argparse
import sys

from tlo_path_inputs import resolve_tlo_home
from tlo_research_lib import research_logs
from tlo_version import DISPLAY_VERSION


class ResearchError(RuntimeError):
    pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tlo-research",
        description="Search TLO meta*.log and comp*.log records by artist/date, venue, or date.",
    )
    parser.add_argument(
        "query",
        nargs="+",
        metavar="INPUT",
        help="Artist followed by date, venue, or date. Multiple words may be quoted or supplied normally.",
    )
    parser.add_argument(
        "--TLOHome",
        dest="TLOHome",
        default="",
        metavar="DIR",
        help="TLOHome directory; if omitted, uses the TLOHome environment variable.",
    )
    parser.add_argument("--myTLO", dest="myTLO", default="", metavar="DIR", help=argparse.SUPPRESS)
    parser.add_argument("--version", action="version", version=f"%(prog)s {DISPLAY_VERSION}")
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        tlo_home = resolve_tlo_home(args.TLOHome, args.myTLO, error_type=ResearchError)
        output = research_logs(tlo_home, " ".join(args.query))
    except (ResearchError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    sys.stdout.write(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
