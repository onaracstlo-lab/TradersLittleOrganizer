__version__ = "v336"
# TLO-GI package version: v336
__version_summary__ = 'Restricts standalone Tag to direct tagging and hides undocumented myTLO help.'
# TLO-GI version summary: Restricts standalone Tag to direct tagging and hides undocumented myTLO help.

import argparse
import multiprocessing
import sys

from console_output_lib import console_emit
if __name__ == "__main__":
    multiprocessing.freeze_support()

from tlo_options import add_options_to_parser, parse_bool
from tlo_path_inputs import strip_optional_quotes
from tlo_tag_lib import run_tagger


def _parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="tlo-tag.py",
        description="Tag audio files in TLOHome/readyForXfer or an explicit tagPath.",
    )
    parser.add_argument("--TLOHome", dest="TLOHome", default="", metavar="DIR", help="TLOHome directory. Defaults from the TLOHome environment variable when present.")
    parser.add_argument("--myTLO", dest="myTLO", default="", metavar="DIR", help=argparse.SUPPRESS)
    add_options_to_parser(parser, fields=(
        "compliant",
        "etree_lookup",
        "rename_compliantly",
        "convert_shn",
        "artist_in_album",
    ))
    tagger_help = {
        "compliant": "Use the simplified compliant folder-name parsing rules.",
        "etree_lookup": "Use eTreeDB as a metadata and song-title fallback during tagging.",
        "rename_compliantly": "Rename an identified folder using the resolved Show Name before tagging it in place.",
        "convert_shn": "Convert .shn/.shnf files in the selected tagging path to .flac; delete a source only after successful verified conversion.",
    }
    for action in parser._actions:
        if action.dest in tagger_help:
            action.help = tagger_help[action.dest]
    parser.add_argument("--debug", dest="debug", nargs="?", const=True, default=False, type=parse_bool, metavar="BOOL", help="Enable debug output and write Unknown-title diagnostic setlist copies under TLOHome/debug; optional BOOL accepts true/false, yes/no, y/n, 1/0.")
    parser.add_argument("--tag-path", dest="tagPathOption", default="", metavar="DIR", help="Optional fully qualified tagging path override.")
    parser.add_argument("tagPath", nargs="?", default="", help="Optional fully qualified tagging path override.")
    args = parser.parse_args(argv)
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
            rename_compliantly=bool(args.rename_compliantly),
            convert_shn=bool(args.convert_shn),
            artist_in_album=bool(args.artist_in_album),
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
