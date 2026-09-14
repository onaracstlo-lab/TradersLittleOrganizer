#!/usr/bin/env python3
"""Reverse logged TLO folder operations. Audio tags are never changed."""
from __future__ import annotations

__version__ = "v465"

import argparse
import os
import sys

from tlo_reverse_folders import ReverseFoldersError, prepare_reverse_plan, reverse_folder_operations
from tlo_version import DISPLAY_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tlo-reverse",
        description=(
            "Reverse logged TLO folder operations affecting PATH. The operation type is inferred from TLO logs; "
            "no copy/rename mode flag is required. Audio tags are never reversed or changed."
        ),
    )
    parser.add_argument("path", help="Fully qualified original or current folder/path to reverse")
    parser.add_argument("--TLOHome", dest="tlo_home", default="", help="TLOHome override")
    parser.add_argument("--myTLO", dest="my_tlo", default="", help=argparse.SUPPRESS)
    parser.add_argument("--log", default="", help="Use one specific success tag log when a broad path is ambiguous")
    parser.add_argument("--dry-run", action="store_true", help="Show the selected log and folder actions without changing folders")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        plan = prepare_reverse_plan(args.path, tlo_home=args.tlo_home, my_tlo=args.my_tlo, log_path=args.log)
        print(f"TLO Reverse Folders {DISPLAY_VERSION}")
        print(f"Selected log: {plan.log_path}")
        print(f"Matching folder operations: {len(plan.operations)}")
        for op in plan.operations:
            print(f"  {op.operation}: {op.source} -> {op.destination}")
        if args.dry_run:
            print("Dry run: no folders will be changed.")
        result = reverse_folder_operations(plan, dry_run=args.dry_run, emit=print)
        return 0 if result.errors == 0 and result.conflicts == 0 else 2
    except ReverseFoldersError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
