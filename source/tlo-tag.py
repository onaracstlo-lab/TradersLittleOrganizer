__version__ = "v318"
# TLO-GI package version: v318
__version_summary__ = 'Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.'
# TLO-GI version summary: Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.

import argparse
import multiprocessing
import sys

from console_output_lib import console_emit
if __name__ == "__main__":
    multiprocessing.freeze_support()

from inventory_parser_lib import _validate_tag_copy_values
from tlo_options import add_options_to_parser, parse_bool
from tlo_path_inputs import strip_optional_quotes
from tlo_tag_lib import run_tagger


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="tlo-tag.py",
        description="Tag audio files in TLOHome/readyForXfer, myTLO/readyForXfer, or an explicit tagPath.",
    )
    parser.add_argument("--TLOHome", dest="TLOHome", default="", metavar="DIR", help="TLOHome directory. Defaults from the TLOHome environment variable when present.")
    parser.add_argument("--myTLO", dest="myTLO", default="", metavar="DIR", help="myTLO directory. When supplied, it takes precedence over --TLOHome and TLOHome environment variable.")
    add_options_to_parser(parser, fields=(
        "compliant",
        "etree_lookup",
        "tag_during_inventory",
        "tag_copy_during_inventory",
        "tag_copy_destination",
        "rename_compliantly",
        "convert_shn",
    ))
    parser.add_argument("--debug", dest="debug", nargs="?", const=True, default=False, type=parse_bool, metavar="BOOL", help="Enable debug output and write Unknown-title diagnostic setlist copies under TLOHome/debug; optional BOOL accepts true/false, yes/no, y/n, 1/0.")
    parser.add_argument("--tag-path", dest="tagPathOption", default="", metavar="DIR", help="Optional fully qualified tagging path override.")
    parser.add_argument("tagPath", nargs="?", default="", help="Optional fully qualified tagging path override.")
    args = parser.parse_args(argv)
    values = vars(args)
    try:
        _validate_tag_copy_values(values, parser)
    except ValueError:
        raise
    option_value = strip_optional_quotes(args.tagPathOption).strip()
    positional_value = strip_optional_quotes(args.tagPath).strip()
    if option_value and positional_value and option_value != positional_value:
        parser.error("Use either --tag-path or positional tagPath, not both with different values.")
    args.tagPath = option_value or positional_value
    return args


def main(argv=None) -> int:
    args = _parse_args(argv)
    try:
        run_tagger(
            tlo_home=args.TLOHome,
            my_tlo=args.myTLO,
            compliant=bool(args.compliant),
            tag_path=args.tagPath,
            etree_lookup=bool(args.etree_lookup),
            debug=bool(args.debug),
            tag_in_place=bool(args.tag_during_inventory),
            tag_copy=bool(args.tag_copy_during_inventory),
            tag_copy_destination=str(getattr(args, "tag_copy_destination", "") or ""),
            rename_compliantly=bool(args.rename_compliantly),
            convert_shn=bool(args.convert_shn),
            emit=lambda text: console_emit(str(text), end="" if str(text).endswith("\n") else "\n"),
        )
        return 0
    except KeyboardInterrupt:
        console_emit("Tagger cancelled.", error=True)
        return 130
    except Exception as exc:
        console_emit(f"ERROR: {exc}", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
