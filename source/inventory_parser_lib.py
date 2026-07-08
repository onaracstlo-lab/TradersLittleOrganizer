__version__ = "v328"
# TLO-GI package version: v328
__version_summary__ = 'Adds native-Windows Explorer drag/drop to the Tagger window Tagging Path field.'
# TLO-GI version summary: Adds native-Windows Explorer drag/drop to the Tagger window Tagging Path field.
import argparse
import sys
import os
import uuid
from dataclasses import dataclass, field

from console_output_lib import console_emit
from tlo_options import (
    add_options_to_parser,
    apply_lookup_dependency,
    namespace_values,
    parse_bool,
    parse_compliant_artist_mode,
    parse_max_workers,
    parse_performance_mode,
)
from tlo_path_inputs import (
    strip_optional_quotes,
    normalize_platform_input_path,
    resolve_current_storage_volume,
    resolve_tlo_home,
    tlo_home_type,
)


@dataclass
class Config:
    debug: bool
    silent: bool
    TLOHome: str
    logs: object = None
    tlo_dbs_dir: str = ""
    artist_sqlite_db_file: str = ""
    venue_reference_db_file: str = ""
    current_search_path: str = ""
    current_search_index: int = 0
    current_slam: str = ""
    current_volume_label: str = ""
    current_volume_key: str = ""
    current_path_copy_destination: str = ""
    current_path_copy_delete_destination: str = ""
    current_inventory_path: str = ""
    search_path_override: str = ""
    search_path_slam_override: str = ""
    search_path_copy_override: str = ""
    search_path_copy_delete_override: str = ""
    compliant: bool = False
    compliant_artist_mode: str = "master"
    tag_during_inventory: bool = False
    tag_copy_during_inventory: bool = False
    tag_copy_destination: str = ""
    tag_copy_and_delete_path: str = ""
    rename_compliantly: bool = False
    convert_shn: bool = False
    etree_lookup: bool = False
    setlistfm_lookup: bool = False
    setlistfm_min_interval_seconds: float = 0.600
    setlistfm_max_calls: int = 1400
    setlistfm_run_id: str = field(default_factory=lambda: uuid.uuid4().hex)
    active_search_paths: list[str] = field(default_factory=list)
    inventory_complete: bool = False
    inventory_scanning_complete: bool = False
    current_log_token: str = ""
    current_log_mode: str = "w"
    active_log_tokens: list[str] = field(default_factory=list)
    current_run_log_tokens: list[str] = field(default_factory=list)
    current_metadata_records: list = field(default_factory=list)
    newly_allocated_log_tokens: list[str] = field(default_factory=list)
    cancel_requested: bool = False
    performance_mode: str = "balanced"
    max_workers: int = 0
    runtime_pause_proxy: object = None
    prepared_inventory_items: list = field(default_factory=list)
    inventory_volume_actions: dict = field(default_factory=dict)
    inventory_path_actions: list = field(default_factory=list)
    volume_action_callback: object = None
    capacity_alert_callback: object = None



def _looks_like_windows_multiprocessing_spawn_args(args):
    if not args:
        return False
    joined = " ".join(str(arg) for arg in args)
    return (
        "--multiprocessing-fork" in args
        or "--multiprocessing-fork" in joined
        or any(str(arg).startswith("parent_pid=") for arg in args)
        or any(str(arg).startswith("pipe_handle=") for arg in args)
    )


def prompt_for_compliant_artist_mode(config_or_namespace) -> str:
    """Return the compliant artist mode, prompting in interactive CLI runs.

    Master checks String1 against the artist DB and uses the master name when
    matched. As-Is uses String1 directly without an artist DB lookup. GUI code
    supplies the value explicitly; non-interactive command-line runs default to
    master to avoid blocking scheduled/scripted jobs.
    """
    mode = parse_compliant_artist_mode(getattr(config_or_namespace, "compliant_artist_mode", "master") or "master")
    if not bool(getattr(config_or_namespace, "compliant", False)):
        setattr(config_or_namespace, "compliant_artist_mode", mode)
        return mode
    raw_mode = str(getattr(config_or_namespace, "compliant_artist_mode", "") or "").strip()
    if raw_mode:
        setattr(config_or_namespace, "compliant_artist_mode", mode)
        return mode
    if bool(getattr(config_or_namespace, "silent", False)) or not sys.stdin.isatty():
        setattr(config_or_namespace, "compliant_artist_mode", "master")
        return "master"
    while True:
        answer = input("Compliant artist names: Master artist from DB or As-Is String1? [M/a]: ").strip()
        if not answer:
            mode = "master"
            break
        try:
            mode = parse_compliant_artist_mode(answer)
            break
        except argparse.ArgumentTypeError:
            console_emit("Enter M for Master or A for As-Is.", error=True)
    setattr(config_or_namespace, "compliant_artist_mode", mode)
    return mode



def _apply_lookup_dependency_or_parser_error(values: dict, parser=None, *, mode: str = "strict") -> None:
    try:
        apply_lookup_dependency(values, mode=mode)
    except ValueError as exc:
        if parser is not None:
            parser.error(str(exc))
        raise


def _validate_tag_copy_values(values: dict, parser=None) -> None:
    if bool(values.get("tag_during_inventory", False)) and bool(values.get("tag_copy_during_inventory", False)):
        message = "--tag-during-inventory and --tag-copy-during-inventory are mutually exclusive."
        if parser is not None:
            parser.error(message)
        raise ValueError(message)

    copy_delete_destination = str(values.get("tag_copy_and_delete_path") or "").strip()
    copy_delete_enabled = bool(copy_delete_destination)

    if bool(values.get("tag_copy_during_inventory", False)):
        destination = str(values.get("tag_copy_destination") or "").strip()
        if not destination:
            message = "--tag-copy-during-inventory requires --tag-copy-destination DIR on the command line."
            if parser is not None:
                parser.error(message)
            raise ValueError(message)
        normalized = normalize_platform_input_path(strip_optional_quotes(destination).strip())
        if not os.path.isabs(normalized) or not os.path.isdir(normalized):
            message = f"--tag-copy-destination must be an existing fully qualified directory path: {destination}"
            if parser is not None:
                parser.error(message)
            raise ValueError(message)
        values["tag_copy_destination"] = os.path.normpath(normalized)

    if copy_delete_destination:
        normalized = normalize_platform_input_path(strip_optional_quotes(copy_delete_destination).strip())
        if not os.path.isabs(normalized) or not os.path.isdir(normalized):
            message = f"--tag-copy-and-delete must be an existing fully qualified directory path: {copy_delete_destination}"
            if parser is not None:
                parser.error(message)
            raise ValueError(message)
        values["tag_copy_and_delete_path"] = os.path.normpath(normalized)


def build_inventory_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Drive/partition reporting tool",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--debug", nargs="?", const=True, type=parse_bool, default=False, metavar="BOOL", help="Enable debug output. With no value, enables debug output; also accepts true/false, yes/no, y/n, 1/0. This is the only toggle that accepts an optional BOOL for backwards compatibility.")
    parser.add_argument("--TLOHome", metavar="DIR", help="Fully qualified existing writable directory path for TLOHome. Defaults from the TLOHome environment variable when present.")
    parser.add_argument("--myTLO", metavar="STRING", help=argparse.SUPPRESS)
    add_options_to_parser(parser, fields=(
        "silent",
        "search_path_override",
        "compliant",
        "compliant_artist_mode",
        "tag_during_inventory",
        "tag_copy_during_inventory",
        "tag_copy_destination",
        "tag_copy_and_delete_path",
        "rename_compliantly",
        "convert_shn",
        "etree_lookup",
        "setlistfm_lookup",
        "performance_mode",
        "max_workers",
        "current_storage_volume",
    ))
    parser.add_argument("-$slam", "--$slam", dest="search_path_slam_override", metavar="STRING", help="Artist override paired with --search-path. Invalid by itself.")
    parser.add_argument("--$copy", dest="search_path_copy_override", metavar="DIR", help="Per-search-path Tag Copy destination. Only valid with --search-path; mutually exclusive with --$copy-delete.")
    parser.add_argument("--$copy-delete", dest="search_path_copy_delete_override", metavar="DIR", help="Per-search-path Tag Copy and Delete destination. Only valid with --search-path; mutually exclusive with --$copy.")
    return parser


def parse_command_line():
    parser = build_inventory_parser()
    raw_args = sys.argv[1:]
    if _looks_like_windows_multiprocessing_spawn_args(raw_args):
        parsed, unknown = parser.parse_known_args(raw_args)
        filtered_unknown = [arg for arg in unknown if not str(arg).startswith(("parent_pid=", "pipe_handle="))]
        if filtered_unknown:
            parser.error(f"unrecognized arguments: {' '.join(filtered_unknown)}")
    else:
        parsed = parser.parse_args(raw_args)
    if getattr(parsed, "search_path_slam_override", None) and not getattr(parsed, "search_path_override", ""):
        parser.error("--$slam is only valid when --search-path is also provided.")
    if getattr(parsed, "search_path_copy_override", None) and not getattr(parsed, "search_path_override", ""):
        parser.error("--$copy is only valid when --search-path is also provided.")
    if getattr(parsed, "search_path_copy_delete_override", None) and not getattr(parsed, "search_path_override", ""):
        parser.error("--$copy-delete is only valid when --search-path is also provided.")
    if getattr(parsed, "search_path_copy_override", None) and getattr(parsed, "search_path_copy_delete_override", None):
        parser.error("--$copy and --$copy-delete are mutually exclusive for a single --search-path.")

    try:
        parsed.TLOHome = resolve_tlo_home(
            tlo_home=getattr(parsed, "TLOHome", ""),
            my_tlo=getattr(parsed, "myTLO", ""),
            error_type=argparse.ArgumentTypeError,
        )
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))

    values = vars(parsed)
    _apply_lookup_dependency_or_parser_error(values, parser, mode="strict")
    _validate_tag_copy_values(values, parser)
    prompt_for_compliant_artist_mode(parsed)
    return vars(parsed)


def build_config():
    cli_config = parse_command_line()
    values = namespace_values(argparse.Namespace(**cli_config))
    _apply_lookup_dependency_or_parser_error(values, mode="strict")
    _validate_tag_copy_values(values)
    config = Config(
        debug=bool(cli_config.get("debug", False)),
        silent=bool(values.get("silent", False)),
        TLOHome=cli_config["TLOHome"],
        search_path_override=(values.get("search_path_override") or ""),
        search_path_slam_override=(cli_config.get("search_path_slam_override") or ""),
        search_path_copy_override=(cli_config.get("search_path_copy_override") or ""),
        search_path_copy_delete_override=(cli_config.get("search_path_copy_delete_override") or ""),
        compliant=bool(values.get("compliant", False)),
        compliant_artist_mode=values.get("compliant_artist_mode", "master") or "master",
        tag_during_inventory=bool(values.get("tag_during_inventory", False)),
        tag_copy_during_inventory=bool(values.get("tag_copy_during_inventory", False)),
        tag_copy_destination=(values.get("tag_copy_destination") or ""),
        tag_copy_and_delete_path=(values.get("tag_copy_and_delete_path") or ""),
        rename_compliantly=bool(values.get("rename_compliantly", False)),
        convert_shn=bool(values.get("convert_shn", False)),
        etree_lookup=bool(values.get("etree_lookup", False)),
        setlistfm_lookup=bool(values.get("setlistfm_lookup", False)),
        performance_mode=values.get("performance_mode", "balanced") or "balanced",
        max_workers=int(values.get("max_workers", 0) or 0),
        current_volume_label=resolve_current_storage_volume(values.get("current_storage_volume")),
    )
    apply_lookup_dependency(vars(config), mode="strict")
    _validate_tag_copy_values(vars(config))
    return config
