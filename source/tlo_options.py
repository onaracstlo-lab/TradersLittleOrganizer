__version__ = "v351"
# TLO-GI package version: v351
__version_summary__ = 'Uses normal dark text for donation details and corrects the About contact wording.'
# TLO-GI version summary: Uses normal dark text for donation details and corrects the About contact wording.

import argparse
from dataclasses import dataclass
from typing import Any, Callable, Optional, Sequence


LOOKUP_DEPENDENCY_ERROR = "--setlistfm-lookup requires --etree-lookup on the command line."
COMPLIANT_RENAME_CONFLICT_ERROR = "--compliant and --rename-compliantly are mutually exclusive."


def parse_bool(value):
    val = str(value).strip().lower()
    true_values = {"true", "t", "yes", "y", "1"}
    false_values = {"false", "f", "no", "n", "0"}
    if val in true_values:
        return True
    if val in false_values:
        return False
    raise argparse.ArgumentTypeError(
        f"Invalid boolean value '{value}' (use true/false, yes/no, y/n, 1/0)."
    )


def parse_max_workers(value):
    try:
        num = int(str(value).strip())
    except Exception:
        raise argparse.ArgumentTypeError("max-workers must be an integer >= 0")
    if num < 0:
        raise argparse.ArgumentTypeError("max-workers must be an integer >= 0")
    return num


def parse_compliant_artist_mode(value):
    val = str(value or "").strip().lower().replace("_", "-")
    aliases = {
        "master": "master",
        "m": "master",
        "db": "master",
        "artist-db": "master",
        "artistdb": "master",
        "as-is": "as-is",
        "asis": "as-is",
        "as is": "as-is",
        "raw": "as-is",
        "a": "as-is",
    }
    if val in aliases:
        return aliases[val]
    raise argparse.ArgumentTypeError("compliant-artist-mode must be master or as-is")


def parse_performance_mode(value):
    val = str(value or "balanced").strip().lower()
    choices = {"gentle", "balanced", "fast", "extreme"}
    if val not in choices:
        raise argparse.ArgumentTypeError("performance-mode must be gentle, balanced, fast, or extreme")
    return val


@dataclass(frozen=True)
class Option:
    config_field: str
    flag: str
    kind: str
    default: Any = False
    choices: Sequence[str] = ()
    help: str = ""
    gui: Optional[str] = None
    gui_label: str = ""
    gui_row: int = 0
    gui_col: int = 0
    metavar: str = ""
    type_func: Optional[Callable[[Any], Any]] = None
    suppress_absent: bool = False


OPTIONS = [
    Option(
        "silent", "--silent", "flag",
        help="Suppress all console output.",
    ),
    Option(
        "compliant", "--compliant", "flag",
        gui="checkbox", gui_label="Compliant", gui_row=0, gui_col=1,
        help="Use the simplified compliant Phase 2/3 parsing rules. Mutually exclusive with --rename-compliantly.",
    ),
    Option(
        "compliant_artist_mode", "--compliant-artist-mode", "choice",
        default="", choices=("master", "as-is"), metavar="MODE",
        type_func=parse_compliant_artist_mode, suppress_absent=True,
        help=argparse.SUPPRESS,
    ),
    Option(
        "as_is_artist_name", "--as-is-artist-name", "flag",
        gui="checkbox", gui_label="As-Is Artist Name", gui_row=2, gui_col=1,
        help="Preserve the artist name as found in show metadata instead of replacing a matched alias with the Artist DB master name.",
    ),
    Option(
        "tag_during_inventory", "--tag-during-inventory", "flag",
        gui="checkbox", gui_label="Tag in Place", gui_row=0, gui_col=2,
        help="Tag audio files in place during Full Inventory and supported Add Shows processing, writing success results to tagsN.txt and errors to tageN.txt under TLOHome/logs.",
    ),
    Option(
        "tag_copy_during_inventory", "--tag-copy-during-inventory", "flag",
        gui="checkbox", gui_label="Tag Copy", gui_row=1, gui_col=2,
        help="During Full Inventory, copy each identified music folder to --tag-copy-destination and tag the copy instead of the original.",
    ),
    Option(
        "rename_compliantly", "--rename-compliantly", "flag",
        gui="checkbox", gui_label="Rename Compliantly", gui_row=1, gui_col=1,
        help="Rename a folder using the resolved Show Name. Mutually exclusive with --compliant. In Full Inventory with no tagging/copy mode, rename the original folder in place without writing audio tags.",
    ),
    Option(
        "convert_shn", "--convert-shn", "flag",
        gui="checkbox", gui_label="Convert shn", gui_row=1, gui_col=3,
        help="Convert .shn/.shnf files to .flac during Tag, Full Inventory, or Add Shows; delete originals only after successful conversion.",
    ),
    Option(
        "artist_in_album", "--no-artist-in-album", "store_false",
        default=True, gui="checkbox", gui_label="Artist in Album Tag", gui_row=0, gui_col=3,
        help="Include the artist name at the beginning of Album tags by default. Use this flag to preserve the prior Album tag format without the artist prefix.",
    ),
    Option(
        "tag_copy_destination", "--tag-copy-destination", "text",
        default="", metavar="DIR",
        help="Destination parent directory for Tag Copy. The GUI asks for this after Inventory is started.",
    ),
    Option(
        "tag_copy_and_delete_enabled", "--tag-copy-delete-original", "flag",
        gui="checkbox", gui_label="Tag Copy/Delete Original", gui_row=2, gui_col=2,
        help="In the GUI, ask for the destination after Inventory is started, tag the transferred folder, verify it, and remove the original material.",
    ),
    Option(
        "tag_copy_and_delete_path", "--tag-copy-and-delete", "text",
        default="", metavar="DIR",
        help="Inventory-time destination parent directory. After show metadata is captured from the original music folder, copy or move the folder there, verify cross-partition copies by file size, delete the original, and inventory the destination copy.",
    ),
    Option(
        "etree_lookup", "--etree-lookup", "flag",
        gui="checkbox", gui_label="etreeDB", gui_row=0, gui_col=0,
        help="Look up venue/location from eTreeDB after artist and yyyy-mm-dd date are identified.",
    ),
    Option(
        "setlistfm_lookup", "--setlistfm-lookup", "flag",
        gui="checkbox", gui_label="setlist.fm", gui_row=1, gui_col=0,
        help="If eTreeDB returns no usable result, look up venue/location from setlist.fm. Requires --etree-lookup on the command line.",
    ),
    Option(
        "performance_mode", "--performance-mode", "choice",
        default="balanced", choices=("gentle", "balanced", "fast", "extreme"),
        metavar="MODE", type_func=parse_performance_mode, gui="combo", gui_label="Performance Mode",
        help="Inventory load mode: gentle, balanced, fast, or extreme.",
    ),
    Option(
        "max_workers", "--max-workers", "int",
        default=0, metavar="N", type_func=parse_max_workers, gui="entry", gui_label="Max Workers",
        suppress_absent=True,
        help="Maximum search-path worker processes. Use 0 for the performance-mode default.",
    ),
    Option(
        "search_path_override", "--search-path", "text",
        default="", metavar="STRING", gui="entry", gui_label="Search Path",
        help="Override toBeInventoried.txt and process a single search path. May be quoted or unquoted; may begin with [Volume] before the path.",
    ),
    Option(
        "current_storage_volume", "--current-storage-volume", "text",
        default=None, metavar="STRING",
        help="Prepopulate Add to Inventory storage/volume. Overrides TLOCurrentStorage.",
    ),
]

OPTIONS_BY_FIELD = {option.config_field: option for option in OPTIONS}


def iter_options(fields: Optional[Sequence[str]] = None):
    if fields is None:
        yield from OPTIONS
        return
    field_set = set(fields)
    for option in OPTIONS:
        if option.config_field in field_set:
            yield option


def add_option_to_parser(parser: argparse.ArgumentParser, option: Option) -> None:
    kwargs = {"dest": option.config_field, "help": option.help}
    if option.metavar:
        kwargs["metavar"] = option.metavar
    if option.kind == "flag":
        parser.add_argument(option.flag, action="store_true", **kwargs)
        return
    if option.kind == "store_false":
        kwargs["default"] = option.default
        parser.add_argument(option.flag, action="store_false", **kwargs)
        return
    if option.kind == "choice":
        kwargs["choices"] = tuple(option.choices)
        kwargs["type"] = option.type_func or str
    elif option.kind == "int":
        kwargs["type"] = option.type_func or int
    elif option.kind == "text":
        kwargs["type"] = option.type_func or str
    else:
        raise ValueError(f"Unsupported option kind: {option.kind}")
    if option.suppress_absent:
        kwargs["default"] = argparse.SUPPRESS
    else:
        kwargs["default"] = option.default
    parser.add_argument(option.flag, **kwargs)


def add_options_to_parser(parser: argparse.ArgumentParser, fields: Optional[Sequence[str]] = None) -> None:
    for option in iter_options(fields):
        add_option_to_parser(parser, option)


def option_defaults(fields: Optional[Sequence[str]] = None) -> dict:
    return {option.config_field: option.default for option in iter_options(fields)}


def namespace_values(namespace: argparse.Namespace, fields: Optional[Sequence[str]] = None) -> dict:
    return {
        option.config_field: getattr(namespace, option.config_field, option.default)
        for option in iter_options(fields)
    }


def validate_compliant_rename_exclusivity(values: dict) -> None:
    """Reject simultaneous compliant parsing and compliant renaming.

    Compliant mode treats the existing folder name as authoritative input, while
    Rename Compliantly is a non-compliant workflow that constructs a new folder
    name from resolved metadata. They cannot be enabled for the same operation.
    """
    if bool(values.get("compliant", False)) and bool(values.get("rename_compliantly", False)):
        raise ValueError(COMPLIANT_RENAME_CONFLICT_ERROR)


def apply_lookup_dependency(values: dict, *, mode: str) -> bool:
    """Apply the setlist.fm -> eTreeDB dependency in one canonical place.

    ``mode='strict'`` is used for command-line/startup validation and raises
    when setlist.fm is enabled without eTreeDB. ``mode='auto'`` is used for GUI
    checkbox state and turns on eTreeDB when setlist.fm is selected.
    """
    if mode not in {"strict", "auto"}:
        raise ValueError("mode must be strict or auto")
    changed = False
    if bool(values.get("setlistfm_lookup", False)) and not bool(values.get("etree_lookup", False)):
        if mode == "strict":
            raise ValueError(LOOKUP_DEPENDENCY_ERROR)
        values["etree_lookup"] = True
        changed = True
    return changed


GUI_CHECKBOX_OPTIONS = tuple(
    sorted((option for option in OPTIONS if option.gui == "checkbox"), key=lambda o: (o.gui_row, o.gui_col))
)
