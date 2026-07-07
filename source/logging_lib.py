__version__ = "v320"
# TLO-GI package version: v320
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
# TLO-GI version summary: Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.
import logging
import os
import re
import string
from dataclasses import dataclass

from tlo_bootlist_volume_policy import format_log_volume_path, format_volume_path


TLO_DBS_DIRNAME = "TLO_DBs"
LOGS_DIRNAME = "logs"
ARTIST_SQLITE_DB_FILENAME = "artists.sqlite"
VENUE_REFERENCE_DB_FILENAME = "venues.txt"
LOG_FILE_PREFIXES = {
    "dead_end": "dead",
    "duplicate": "dups",
    "complete_paths": "comp",
    "groups": "groups",
    "conflicts": "conf",
    "show_metadata": "meta",
    "tag_success": "tags",
    "tag_error": "tage",
    # Retained so cleanup/prune logic removes legacy tagN.log files.
    "tag_legacy": "tag",
}
LOG_TOKEN_CHARS = string.digits + string.ascii_uppercase
LOG_TOKEN_PATTERN = re.compile(r"^(?:conf|dead|comp|dups|groups|meta|tag|tags|tage)([A-Za-z0-9]+)\.(?:log|txt)$")


def sanitize_scope_label(label):
    cleaned = str(label or "search").strip()
    if not cleaned:
        cleaned = "search"

    cleaned = cleaned.replace("/", "_").replace("\\", "_")
    cleaned = cleaned.replace(":", "_")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("_.-")
    return cleaned or "search"


def _token_to_string(number):
    if number < 0:
        raise ValueError("token number must be non-negative")
    if number == 0:
        return LOG_TOKEN_CHARS[0]
    chars = []
    base = len(LOG_TOKEN_CHARS)
    while number:
        number, remainder = divmod(number, base)
        chars.append(LOG_TOKEN_CHARS[remainder])
    return "".join(reversed(chars))


def logs_dir_for_home(tlo_home):
    return os.path.join(tlo_home, LOGS_DIRNAME)


def ensure_logs_dir(tlo_home):
    logs_dir = logs_dir_for_home(tlo_home)
    os.makedirs(logs_dir, exist_ok=True)
    return logs_dir


def _log_file_extension_for_prefix(prefix: str) -> str:
    return ".txt" if str(prefix or "") in {"tags", "tage"} else ".log"


def _log_path_for_prefix(logs_dir: str, prefix: str, token: str) -> str:
    return os.path.join(logs_dir, f"{prefix}{token}{_log_file_extension_for_prefix(prefix)}")


def _format_logger_message(message, args) -> str:
    if args:
        try:
            return str(message) % args
        except Exception:
            return " ".join([str(message)] + [str(arg) for arg in args])
    return str(message)


def _tag_line_is_error(line: str) -> bool:
    text = str(line or "").strip()
    upper = text.upper()
    if not text:
        return False
    if upper.startswith(("ERROR", "WARN", "SKIP", "CANCELLED")):
        return True
    if upper.startswith(("TAG_SKIP", "TAG_COPY_AND_DELETE_SKIP", "RENAME_COMPLIANTLY_SKIP")):
        return True
    if "_FAILED" in upper or " FAILED" in upper or "FILE_ERROR" in upper or "CONVERT_SHN_ERROR" in upper:
        return True
    match = re.search(r"\bfile_errors=(\d+)", text, re.IGNORECASE)
    if match and int(match.group(1) or 0) > 0:
        return True
    return False


def _tag_reason_code_from_line(line: str) -> str:
    text = str(line or "").strip()
    if not text or text.startswith("SEARCH_PATH:") or text.startswith("#"):
        return ""
    if text.startswith("WARN_SUMMARY:"):
        return ""
    match = re.match(r"^([A-Z][A-Z0-9_]+):", text)
    if match:
        code = match.group(1)
        if code.startswith(("SKIP", "WARN", "ERROR", "CANCELLED", "CONVERT_SHN", "TAG_SKIP", "TAG_COPY", "RENAME")):
            return code
    upper = text.upper()
    if upper.startswith("ERROR"):
        return "ERROR_TAGGING"
    if upper.startswith("WARN"):
        return "WARN_TAGGING"
    if upper.startswith(("SKIP", "TAG_SKIP")):
        return "SKIP_TAGGING"
    if upper.startswith("CANCELLED"):
        return "SKIP_CANCELLED"
    return ""


def existing_short_log_tokens(tlo_home):
    used = set()
    logs_dir = logs_dir_for_home(tlo_home)
    try:
        names = os.listdir(logs_dir)
    except OSError:
        return used
    for name in names:
        match = LOG_TOKEN_PATTERN.match(name)
        if match:
            used.add(match.group(1))
    return used


def allocate_log_tokens(tlo_home, count):
    requested = max(0, int(count or 0))
    max_tokens = len(LOG_TOKEN_CHARS)
    if requested > max_tokens:
        raise ValueError(
            f"Too many simultaneous log tokens requested: {requested}. "
            f"The short log-token range supports at most {max_tokens} active search paths or group files."
        )

    used = existing_short_log_tokens(tlo_home)
    available = [token for token in LOG_TOKEN_CHARS if token not in used]
    if requested > len(available):
        raise ValueError(
            f"Not enough short log tokens available: requested {requested}, available {len(available)}. "
            "Archive or remove old tokenized logs under TLOHome/logs before starting another run."
        )
    return available[:requested]


def delete_logs_for_tokens(tlo_home, tokens):
    deleted = []
    logs_dir = logs_dir_for_home(tlo_home)
    for token in tokens or []:
        token_text = str(token or "").strip()
        if not token_text:
            continue
        for prefix in LOG_FILE_PREFIXES.values():
            log_file = _log_path_for_prefix(logs_dir, prefix, token_text)
            try:
                if os.path.exists(log_file):
                    os.remove(log_file)
                    deleted.append(log_file)
            except OSError:
                continue
    return deleted


def truncate_logs_for_tokens(tlo_home, tokens):
    """Replace existing related log files for tokens without changing names.

    Used when the existing-inventory prompt returns re-inventory.  This clears every
    conf/dead/comp/dups/groups/meta/tag log tied to the old volume token before
    the fresh inventory writes to the reused token.
    """
    truncated = []
    logs_dir = ensure_logs_dir(tlo_home)
    for token in tokens or []:
        token_text = str(token or "").strip()
        if not token_text:
            continue
        for prefix in LOG_FILE_PREFIXES.values():
            log_file = _log_path_for_prefix(logs_dir, prefix, token_text)
            try:
                with open(log_file, "w", encoding="utf-8"):
                    pass
                truncated.append(log_file)
            except OSError:
                continue
    return truncated



def _line_path_after_prefix(line: str, prefix: str) -> str:
    stripped = (line or "").strip()
    if not stripped.startswith(prefix):
        return ""
    return stripped.split(prefix, 1)[1].strip()


def _path_under_any_scope(path_name: str, root_paths) -> bool:
    if not path_name:
        return False
    try:
        from tlo_bootlist_volume_policy import path_is_same_or_under
        return any(path_is_same_or_under(path_name, root) for root in (root_paths or []) if str(root or "").strip())
    except Exception:
        normalized = os.path.normcase(os.path.normpath(str(path_name or "")))
        for root in root_paths or []:
            root_norm = os.path.normcase(os.path.normpath(str(root or "")))
            if normalized == root_norm or normalized.startswith(root_norm + os.sep):
                return True
        return False


def _structured_block_path(block_lines):
    candidate = ""
    for line in block_lines:
        for prefix in ("MAIN_DIR_PATH:", "MUSIC_DIR:", "MUSIC_SAMPLE_FILE:", "MUSIC_FILE:", "TXT_FILE:", "SETLIST_FILE:"):
            value = _line_path_after_prefix(line, prefix)
            if value:
                candidate = value
                if prefix == "MAIN_DIR_PATH:":
                    return candidate
    return candidate


def _prune_structured_log(path_name, root_paths, end_marker):
    try:
        with open(path_name, "r", encoding="utf-8", errors="ignore") as infile:
            lines = infile.readlines()
    except OSError:
        return False
    out = []
    block = []
    changed = False
    in_block = False
    for line in lines:
        if not in_block and (line.startswith("GROUP_NUMBER:") or line.startswith("SHOW_NAME:")):
            in_block = True
            block = [line]
            continue
        if in_block:
            block.append(line)
            if line.strip() == end_marker:
                block_path = _structured_block_path(block)
                if _path_under_any_scope(block_path, root_paths):
                    changed = True
                else:
                    out.extend(block)
                block = []
                in_block = False
            continue
        out.append(line)
    if block:
        out.extend(block)
    if changed:
        with open(path_name, "w", encoding="utf-8", newline="") as outfile:
            outfile.writelines(out)
    return changed


def _line_mentions_pruned_path(line, root_paths):
    # Extract obvious path fragments from the log line and compare by subtree.
    text = (line or "").strip()
    if not text or text.startswith("#") or text.startswith("SEARCH_PATH:"):
        return False
    candidates = []
    if ":" in text:
        candidates.append(text.split(":", 1)[1].strip())
    if "|" in text:
        candidates.extend(part.strip() for part in text.split("|"))
    parts = text.split()
    candidates.extend(part.strip() for part in parts if part.startswith("/") or (len(part) >= 2 and part[1:2] == ":"))
    return any(_path_under_any_scope(candidate, root_paths) for candidate in candidates)


def _prune_line_log(path_name, root_paths):
    try:
        with open(path_name, "r", encoding="utf-8", errors="ignore") as infile:
            lines = infile.readlines()
    except OSError:
        return False
    out = [line for line in lines if not _line_mentions_pruned_path(line, root_paths)]
    if len(out) != len(lines):
        with open(path_name, "w", encoding="utf-8", newline="") as outfile:
            outfile.writelines(out)
        return True
    return False


def prune_logs_for_tokens_and_paths(tlo_home, tokens, root_paths):
    """Remove prior log entries under root_paths from reused token logs.

    This supports child-path re-inventory of a broader previously inventoried
    search path.  The existing token is kept, but records for the child subtree
    are removed before the new child inventory is appended.
    """
    pruned = []
    roots = [str(root or "").strip() for root in (root_paths or []) if str(root or "").strip()]
    if not roots:
        return pruned
    logs_dir = ensure_logs_dir(tlo_home)
    for token in tokens or []:
        token_text = str(token or "").strip()
        if not token_text:
            continue
        group_path = os.path.join(logs_dir, f"groups{token_text}.log")
        if _prune_structured_log(group_path, roots, "END_GROUP"):
            pruned.append(group_path)
        meta_path = os.path.join(logs_dir, f"meta{token_text}.log")
        if _prune_structured_log(meta_path, roots, "END_SHOW_METADATA"):
            pruned.append(meta_path)
        for prefix in ("dead", "dups", "comp", "conf", "tag", "tags", "tage"):
            log_path = _log_path_for_prefix(logs_dir, prefix, token_text)
            if _prune_line_log(log_path, roots):
                pruned.append(log_path)
    return pruned

def delete_logs_for_search_paths(tlo_home, search_paths):
    # Retained for compatibility with earlier bundles. Current cleanup uses token-based names.
    deleted = []
    for search_path in search_paths or []:
        scope_label = sanitize_scope_label(search_path)
        for legacy_base_name in ("deadEndLog", "duplicatesLog", "completePathLog", "groupsLog", "conflictLog", "showMetadataLog"):
            log_file = os.path.join(tlo_home, f"{legacy_base_name}_{scope_label}.log")
            try:
                if os.path.exists(log_file):
                    os.remove(log_file)
                    deleted.append(log_file)
            except OSError:
                continue
    return deleted


def _dedupe_preserve_order(values):
    out = []
    for value in values or []:
        clean = str(value or "").strip()
        if clean and clean not in out:
            out.append(clean)
    return out


def _split_search_path_header_tail(tail):
    return [piece.strip() for piece in re.split(r"\s+\|\s+", str(tail or "")) if piece.strip()]


def _extract_existing_search_path_header(lines):
    """Return (header_paths, body_start_index) for an existing short log file."""
    values = []
    body_start = 0
    for index, line in enumerate(lines or []):
        stripped = (line or "").strip()
        if not stripped:
            body_start = index + 1
            continue
        if stripped.startswith("SEARCH_PATH:"):
            values.append(stripped.split(":", 1)[1].strip())
            body_start = index + 1
            continue
        if stripped.startswith("#"):
            matched = False
            for marker in ("for search paths:", "for search path:"):
                if marker in stripped:
                    values.extend(_split_search_path_header_tail(stripped.split(marker, 1)[1].strip()))
                    body_start = index + 1
                    matched = True
                    break
            if matched:
                continue
        break
    return _dedupe_preserve_order(values), body_start


def _descriptive_header(prefix_name, search_paths):
    paths = _dedupe_preserve_order(search_paths if isinstance(search_paths, (list, tuple)) else [search_paths])
    if len(paths) <= 1:
        return f"# {prefix_name} for search path: {paths[0] if paths else ''}"
    return f"# {prefix_name} for search paths: {' | '.join(paths)}"


def _header_lines(prefix_name, search_paths):
    paths = _dedupe_preserve_order(search_paths)
    if not paths:
        paths = [format_volume_path("", "")]
    lines = [_descriptive_header(prefix_name, paths) + "\n"]
    lines.extend(f"SEARCH_PATH: {path}\n" for path in paths)
    return lines


def _ensure_appended_log_header(log_file, prefix_name, display_search_path):
    """Ensure an append-mode log has a top header containing display_search_path."""
    try:
        with open(log_file, "r", encoding="utf-8", errors="ignore") as infile:
            lines = infile.readlines()
    except OSError:
        lines = []

    existing_paths, body_start = _extract_existing_search_path_header(lines)
    paths = _dedupe_preserve_order(existing_paths + [display_search_path])
    body = lines[body_start:] if lines else []
    if lines and body_start == 0 and existing_paths:
        body = lines
    new_lines = _header_lines(prefix_name, paths)
    if body and (new_lines[-1].strip() or body[0].strip()):
        new_lines.append("\n")
    new_lines.extend(body)
    try:
        with open(log_file, "w", encoding="utf-8", newline="") as outfile:
            outfile.writelines(new_lines)
    except OSError:
        pass


@dataclass
class LogPaths:
    dead_end: str
    duplicate: str
    complete_paths: str
    groups: str
    conflicts: str
    show_metadata: str
    tag_success: str
    tag_error: str
    tag_legacy: str = ""

    @property
    def tag(self) -> str:
        # Compatibility: older code/tests that ask for paths.tag receive the
        # success tag log. New code should use tag_success/tag_error.
        return self.tag_success


class LogManager:
    def __init__(self, tlo_home):
        self.tlo_home = tlo_home
        self.logs_dir = ensure_logs_dir(tlo_home)
        self.tlo_dbs_dir = self._tlo_dbs_dir()
        self.artist_sqlite_db_file = os.path.join(self.tlo_dbs_dir, ARTIST_SQLITE_DB_FILENAME)
        self.venue_reference_db_file = os.path.join(self.tlo_dbs_dir, VENUE_REFERENCE_DB_FILENAME)
        self.search_counter = 0
        self.current_scope_label = ""
        self.current_log_token = ""

        self.paths = LogPaths("", "", "", "", "", "", "", "")
        self._dead_end_logger = self._null_logger("deadEndLog")
        self._duplicate_logger = self._null_logger("duplicatesLog")
        self._complete_paths_logger = self._null_logger("completePathLog")
        self._groups_logger = self._null_logger("groupsLog")
        self._conflicts_logger = self._null_logger("conflictLog")
        self._show_metadata_logger = self._null_logger("showMetadataLog")
        self._tag_success_logger = self._null_logger("tagSuccessLog")
        self._tag_error_logger = self._null_logger("tagErrorLog")
        self._tag_logger = self._tag_success_logger
        self.tag_reason_counts = {}
        self._emitting_tag_reason_summary = False

    def _sanitize_scope_label(self, label):
        cleaned = str(label or "search").strip()
        if not cleaned:
            cleaned = "search"

        cleaned = cleaned.replace("/", "_").replace("\\", "_")
        cleaned = cleaned.replace(":", "_")
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned).strip("_.-")
        return cleaned or "search"

    def _build_log_file(self, prefix, token):
        return _log_path_for_prefix(self.logs_dir, prefix, token)

    def _tlo_dbs_dir(self):
        db_dir = os.path.join(self.tlo_home, TLO_DBS_DIRNAME)
        os.makedirs(db_dir, exist_ok=True)
        return db_dir

    def _null_logger(self, logger_name):
        logger = logging.getLogger(f"{logger_name}:null:{id(self)}")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.propagate = False
        logger.addHandler(logging.NullHandler())
        return logger

    def _configure_logger(self, logger_name, log_file, mode="w"):
        logger = logging.getLogger(f"{logger_name}:{log_file}")
        logger.handlers.clear()
        logger.setLevel(logging.INFO)
        logger.propagate = False
        safe_mode = "a" if str(mode or "w").lower().startswith("a") else "w"
        handler = logging.FileHandler(log_file, mode=safe_mode, encoding="utf-8")
        handler.setLevel(logging.INFO)
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        return logger

    def _switch_to_scope(self, scope_label, token, search_path, log_mode="w"):
        self.current_scope_label = sanitize_scope_label(scope_label)
        self.current_log_token = str(token or "")
        self.paths = LogPaths(
            dead_end=self._build_log_file(LOG_FILE_PREFIXES["dead_end"], self.current_log_token),
            duplicate=self._build_log_file(LOG_FILE_PREFIXES["duplicate"], self.current_log_token),
            complete_paths=self._build_log_file(LOG_FILE_PREFIXES["complete_paths"], self.current_log_token),
            groups=self._build_log_file(LOG_FILE_PREFIXES["groups"], self.current_log_token),
            conflicts=self._build_log_file(LOG_FILE_PREFIXES["conflicts"], self.current_log_token),
            show_metadata=self._build_log_file(LOG_FILE_PREFIXES["show_metadata"], self.current_log_token),
            tag_success=self._build_log_file(LOG_FILE_PREFIXES["tag_success"], self.current_log_token),
            tag_error=self._build_log_file(LOG_FILE_PREFIXES["tag_error"], self.current_log_token),
            tag_legacy=self._build_log_file(LOG_FILE_PREFIXES["tag_legacy"], self.current_log_token),
        )
        append_mode = str(log_mode or "w").lower().startswith("a")
        prefix_by_attr = [
            (self.paths.dead_end, "deadEndLog"),
            (self.paths.duplicate, "duplicatesLog"),
            (self.paths.complete_paths, "completePathLog"),
            (self.paths.groups, "groupsLog"),
            (self.paths.conflicts, "conflictLog"),
            (self.paths.show_metadata, "showMetadataLog"),
            (self.paths.tag_success, "tagSuccessLog"),
            (self.paths.tag_error, "tagErrorLog"),
        ]
        if append_mode:
            for log_file, prefix_name in prefix_by_attr:
                _ensure_appended_log_header(log_file, prefix_name, search_path)

        self._dead_end_logger = self._configure_logger("deadEndLog", self.paths.dead_end, log_mode)
        self._duplicate_logger = self._configure_logger("duplicatesLog", self.paths.duplicate, log_mode)
        self._complete_paths_logger = self._configure_logger("completePathLog", self.paths.complete_paths, log_mode)
        self._groups_logger = self._configure_logger("groupsLog", self.paths.groups, log_mode)
        self._conflicts_logger = self._configure_logger("conflictLog", self.paths.conflicts, log_mode)
        self._show_metadata_logger = self._configure_logger("showMetadataLog", self.paths.show_metadata, log_mode)
        self._tag_success_logger = self._configure_logger("tagSuccessLog", self.paths.tag_success, log_mode)
        self._tag_error_logger = self._configure_logger("tagErrorLog", self.paths.tag_error, log_mode)
        self._tag_logger = self._tag_success_logger
        if not append_mode:
            self._dead_end_logger.info(_descriptive_header("deadEndLog", search_path))
            self._duplicate_logger.info(_descriptive_header("duplicatesLog", search_path))
            self._complete_paths_logger.info(_descriptive_header("completePathLog", search_path))
            self._groups_logger.info(_descriptive_header("groupsLog", search_path))
            self._conflicts_logger.info(_descriptive_header("conflictLog", search_path))
            self._show_metadata_logger.info(_descriptive_header("showMetadataLog", search_path))
            self._tag_success_logger.info(_descriptive_header("tagSuccessLog", search_path))
            self._tag_error_logger.info(_descriptive_header("tagErrorLog", search_path))

    def start_search_path(self, search_path, index=None, log_token=None, volume_label="", log_mode="w"):
        self.search_counter = index or 0
        scope_label = sanitize_scope_label(search_path)
        token = str(log_token or self.search_counter or "0")
        display_search_path = format_log_volume_path(volume_label, search_path)
        append_mode = str(log_mode or "w").lower().startswith("a")
        self._switch_to_scope(scope_label, token, display_search_path, log_mode=log_mode)
        if not append_mode:
            self.complete_paths("SEARCH_PATH: %s", display_search_path)
            self.groups("SEARCH_PATH: %s", display_search_path)
            self.conflicts("SEARCH_PATH: %s", display_search_path)
            self.show_metadata("SEARCH_PATH: %s", display_search_path)
            self.tag_success("SEARCH_PATH: %s", display_search_path)
            self.tag_error("SEARCH_PATH: %s", display_search_path)

    def dead_end(self, message, *args):
        self._dead_end_logger.info(message, *args)

    def duplicate(self, message, *args):
        self._duplicate_logger.info(message, *args)

    def complete_paths(self, message, *args):
        self._complete_paths_logger.info(message, *args)

    def groups(self, message, *args):
        self._groups_logger.info(message, *args)

    def conflicts(self, message, *args):
        self._conflicts_logger.info(message, *args)

    def show_metadata(self, message, *args):
        self._show_metadata_logger.info(message, *args)

    def tag_success(self, message, *args):
        self._tag_success_logger.info(message, *args)

    def tag_error(self, message, *args):
        text = _format_logger_message(message, args)
        for line in (text.splitlines() or [text]):
            self.record_tag_reason_line(line)
            self._tag_error_logger.info("%s", line)

    def record_tag_reason_line(self, line):
        if getattr(self, "_emitting_tag_reason_summary", False):
            return
        code = _tag_reason_code_from_line(line)
        if not code:
            return
        self.tag_reason_counts[code] = int(self.tag_reason_counts.get(code, 0) or 0) + 1

    def tag(self, message, *args):
        text = _format_logger_message(message, args)
        lines = text.splitlines() or [text]
        for line in lines:
            if _tag_line_is_error(line):
                self.record_tag_reason_line(line)
                self._tag_error_logger.info("%s", line)
            else:
                self._tag_success_logger.info("%s", line)


def setup_logging(config):
    config.logs = LogManager(config.TLOHome)
    config.tlo_dbs_dir = config.logs.tlo_dbs_dir
    config.logs_dir = config.logs.logs_dir
    config.artist_sqlite_db_file = config.logs.artist_sqlite_db_file
    config.venue_reference_db_file = config.logs.venue_reference_db_file
    return config.logs
