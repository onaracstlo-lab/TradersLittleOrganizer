#!/usr/bin/env python3
"""Reverse logged folder operations, or Manual Tweaks including logged original tags."""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import argparse
import sys

from tlo_reverse_folders import ReverseFoldersError, prepare_reverse_plan, reverse_folder_operations
from tlo_manual_undo import ManualUndoError
from tlo_version import DISPLAY_VERSION


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tlo-reverse",
        description=(
            "Reverse logged TLO folder operations affecting PATH. The operation type is inferred from TLO logs; "
            "no copy/rename mode flag is required. Normal folder reversals never change tags; "
            "--manual-updates replays original metadata from the Manual Tweaks undo log."
        ),
    )
    parser.add_argument("path", nargs="?", default="", help="Folder to reverse, or destination parent for --recover-staging; omitted with --manual-updates --list")
    parser.add_argument("--TLOHome", dest="tlo_home", default="", help="TLOHome override")
    parser.add_argument("--myTLO", dest="my_tlo", default="", help=argparse.SUPPRESS)
    parser.add_argument("--log", default="", help="Use one specific success tag log when a broad path is ambiguous")
    parser.add_argument("--dry-run", action="store_true", help="Show the selected log and folder actions without changing folders")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--manual-updates", "--manual-tweaks", action="store_true",
                       help="Undo Manual Tweaks including original tags; --log selects a journal under logs/manual-updates-undo")
    modes.add_argument("--recover-staging", action="store_true",
                       help="Recover interrupted Copy/Delete moves under PATH (destination parent directory)")
    parser.add_argument('--list', action='store_true', help='With --manual-updates, list undo journals newest first and report inventory eligibility')
    parser.add_argument('--batch', type=int, default=0, metavar='N', help='With --manual-updates, undo exactly N linked updates newest-first (1–100); omit PATH')
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.list and not args.manual_updates:
        parser.error('--list requires --manual-updates')
    if args.batch and (not args.manual_updates or args.list or args.log or args.path):
        parser.error('--batch requires --manual-updates without PATH, --list or --log')
    if args.batch < 0 or args.batch > 100:
        parser.error('--batch must be between 1 and 100')
    if not args.path and not (args.manual_updates and (args.list or args.batch)):
        parser.error('PATH is required except for --manual-updates --list/--batch')
    try:
        from tlo_path_inputs import resolve_tlo_home
        from tlo_runtime_control import inventory_operation_lock
        if args.recover_staging and not (args.tlo_home or args.my_tlo or __import__('os').environ.get('TLOHome')):
            # Staging recovery is also available when TLOHome is not configured.
            # Use a destination-local lock in this standalone recovery mode.
            import hashlib
            import os
            import tempfile
            key = hashlib.sha256(os.path.abspath(args.path).encode('utf-8')).hexdigest()[:32]
            home = os.path.join(tempfile.gettempdir(), 'tlo-staging-recovery-locks', key)
        else:
            home = resolve_tlo_home(tlo_home=args.tlo_home, my_tlo=args.my_tlo,
                                    error_type=ManualUndoError, app_name="tlo-reverse")
        with inventory_operation_lock(home):
            return _run_locked(args, home)
    except (ReverseFoldersError, ManualUndoError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130


def _run_locked(args, home: str) -> int:
    try:
        if args.manual_updates:
            from tlo_manual_undo import list_manual_updates, reverse_manual_update
            if args.list:
                for entry in list_manual_updates(home):
                    print(f"{entry['state']} | inventory unchanged: {entry['inventory_unchanged']} | {entry['journal']} | {entry.get('destination', entry.get('error', ''))}")
                return 0
            if args.batch:
                from tlo_manual_undo import reverse_manual_updates_batch
                result = reverse_manual_updates_batch(home, args.batch, dry_run=args.dry_run, emit=print)
                print(f"Batch Manual Tweaks undo: {result['reversed']} reversed / {result['planned']} planned")
                return 0
            reverse_manual_update(args.path, tlo_home=home, log_path=args.log,
                                  dry_run=args.dry_run, emit=print)
            return 0
        if args.recover_staging:
            from tlo_staging_recovery import recover_interrupted_stage_moves
            print(f"TLO Staged Move Recovery {DISPLAY_VERSION}")
            results = recover_interrupted_stage_moves(args.path, dry_run=args.dry_run, emit=print)
            pending = f"; would restore: {results['would_restore']}" if args.dry_run else ""
            print(f"Recovery records: {results['found']}; restored: {results['restored']}{pending}; conflicts: {results['conflicts']}")
            return 2 if results['conflicts'] else 0
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
    except (ReverseFoldersError, ManualUndoError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("Cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
