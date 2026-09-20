"""Safe consolidation of non-date multipart/alternate sibling collections."""

from __future__ import annotations

__version__ = "v478"

import json
import ntpath
import os
import re
import uuid
import zipfile
from dataclasses import dataclass, field
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from xml.etree import ElementTree

from tlo_media_rules import MEDIA_EXTENSIONS
from tlo_setlist_file_selection import _ordered_exception_files, _ordered_txt_files
from tlo_wrapper_rules import split_wrapper_part_suffix

JOURNAL_NAME = ".tlo-sibling-consolidation.json"
TEMP_PREFIX = ".tlo-collection-"
TEXT_SETLIST_EXTENSIONS = {".txt", ".nfo"}
DOCUMENT_SETLIST_EXTENSIONS = {".rtf", ".docx"}
SETLIST_EXTENSIONS = TEXT_SETLIST_EXTENSIONS | DOCUMENT_SETLIST_EXTENSIONS
HOUSEKEEPING_RE = re.compile(
    r"(?i)(?:md5|ffp|fpt|checksum|fingerprint|\bsfv\b|aucdtect|spectrogram|torrent|m3u8?|\bcue\b|\blog\b)"
)
ALT_SUFFIX_RE = re.compile(
    r"(?i)^(?P<base>.+?)(?:\s*\(\s*alt[\s._-]*(?P<paren>\d{1,3})\s*\)|[\s._-]+alt[\s._-]*(?P<bare>\d{1,3}))\s*$"
)
FULL_DATE_RE = re.compile(
    r"(?i)(?<!\d)(?:(?:19|20)\d{2}[._/-]\d{1,2}[._/-]\d{1,2}|\d{1,2}[._/-]\d{1,2}[._/-](?:19|20)?\d{2})(?!\d)"
)
UNKNOWN_FULL_DATE_RE = re.compile(r"(?i)(?<![A-Za-z0-9])xxxx[._/-]xx[._/-]xx(?![A-Za-z0-9])")
TRACK_LINE_RE = re.compile(
    r"(?i)^\s*(?:(?:cd|disc|disk|set|d)\s*\d+\s*[-._ ]*)?(?:track\s*)?\d{1,3}\s*[.)_:-]+\s*(?P<title>\S.*)$"
)
FILE_TRACK_PREFIX_RE = re.compile(
    r"(?i)^.*?(?:\b(?:cd|disc|disk|set|d)?\d{1,2}t\d{1,3}\b|(?:^|[-_. ])\d{1,3}\s*[-._)])\s*"
)
LEADING_NUMBER_RE = re.compile(r"^\s*\d{1,3}\s*[-._)]*\s*")
TRAILING_TIME_RE = re.compile(r"\s*[\[(]?\d{1,2}:\d{2}(?::\d{2})?[\])]?(?:\s*[-–—].*)?\s*$")
WORD_NUMBER = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
    "a": 1, "b": 2,
}

_WINDOWS_DRIVE_JOURNAL_RE = re.compile(r"^([A-Za-z]):[\\/](.*)$")
_WSL_DRIVE_JOURNAL_RE = re.compile(r"^/mnt/([A-Za-z])(?:/(.*))?$", re.IGNORECASE)
_WSL_MOUNT_ROOT = "/mnt"


def _runtime_recovery_path(path_name: str, *, platform_name: Optional[str] = None) -> str:
    """Translate a journal path to the path syntax used by this runtime.

    Recovery journals are intentionally durable across interrupted runs.  A
    collection may therefore be interrupted under native Windows and recovered
    under WSL (or vice versa).  The journal keeps the paths written by the
    original runtime, while recovery validates and operates on equivalent paths
    for the current runtime.
    """
    text = str(path_name or "").strip().strip('\"').strip("'")
    if not text:
        return ""
    runtime = os.name if platform_name is None else str(platform_name)
    if runtime == "nt":
        normalized = text.replace("\\", "/")
        match = _WSL_DRIVE_JOURNAL_RE.match(normalized)
        if match:
            drive = match.group(1).upper()
            rest = (match.group(2) or "").replace("/", "\\").strip("\\")
            return ntpath.normpath(f"{drive}:\\{rest}" if rest else f"{drive}:\\")
        return ntpath.normpath(text)

    match = _WINDOWS_DRIVE_JOURNAL_RE.match(text)
    if match:
        drive = match.group(1).lower()
        rest = match.group(2).replace("\\", "/").lstrip("/")
        return os.path.normpath(
            os.path.join(_WSL_MOUNT_ROOT, drive, *([part for part in rest.split("/") if part] if rest else []))
        )
    return os.path.normpath(text)


@dataclass
class CollectionMember:
    path: str
    index: int
    music_dirs: List[str] = field(default_factory=list)
    titles: List[str] = field(default_factory=list)
    setlist_files: List[str] = field(default_factory=list)


@dataclass
class CollectionPlan:
    parent_dir: str
    base_name: str
    kind: str
    members: List[CollectionMember]
    excluded_similar: List[str] = field(default_factory=list)

    @property
    def final_path(self) -> str:
        return os.path.join(self.parent_dir, self.base_name)


class SiblingCollectionRecoveryError(RuntimeError):
    """An interrupted TLO move cannot be recovered without user review."""


class _SiblingCollectionRollbackFailure(RuntimeError):
    """Internal rollback failure carrying the container that still holds the journal."""

    def __init__(self, container: str, reason: str):
        super().__init__(reason)
        self.container = container


def _same_path(left: str, right: str) -> bool:
    try:
        return os.path.normcase(os.path.abspath(os.path.normpath(left))) == os.path.normcase(
            os.path.abspath(os.path.normpath(right))
        )
    except Exception:
        return os.path.normcase(os.path.normpath(str(left or ""))) == os.path.normcase(
            os.path.normpath(str(right or ""))
        )


def _recovery_member_rows(container: str, payload: dict) -> List[Tuple[str, str, str, str]]:
    rows: List[Tuple[str, str, str, str]] = []
    for row in list(payload.get("members") or []):
        journal_original = str(row.get("original") or "").strip()
        original = _runtime_recovery_path(journal_original)
        child_name = str(row.get("child_name") or "")
        staged_name = str(row.get("staged_name") or child_name)
        staged = os.path.join(container, staged_name) if staged_name else ""
        original_exists = bool(original and os.path.lexists(original))
        staged_exists = bool(staged and os.path.lexists(staged))
        if original and _same_path(original, container):
            if staged_exists:
                state = "CONTAINER_OCCUPIES_ORIGINAL; staged member present"
            else:
                state = "CONTAINER_OCCUPIES_ORIGINAL; staged member MISSING"
        elif original_exists and staged_exists:
            state = "BOTH original and staged copies exist"
        elif original_exists:
            state = "ORIGINAL_ONLY"
        elif staged_exists:
            state = "STAGED_ONLY"
        else:
            state = "MISSING from both original and staged locations"
        rows.append((journal_original, original, staged, state))
    return rows


def _format_recovery_error(container: str, payload: Optional[dict], reason: str, *, dry_run: bool = False) -> str:
    journal = os.path.join(container, JOURNAL_NAME)
    lines = [
        "Interrupted sibling-collection move requires recovery.",
        f"Reason: {reason}",
        f"Recovery container: {container}",
        f"Recovery journal: {journal}",
    ]
    if isinstance(payload, dict):
        logged_final_path = str(payload.get("final_path") or "").strip()
        final_path = _runtime_recovery_path(logged_final_path)
        if final_path:
            lines.append(f"Planned final folder: {final_path}")
            if logged_final_path and os.path.normpath(logged_final_path) != final_path:
                lines.append(f"Journal path form: {logged_final_path}")
        rows = _recovery_member_rows(container, payload)
        if rows:
            lines.append("Member state:")
            for journal_original, original, staged, state in rows:
                lines.append(f"  - original: {original}")
                if journal_original and os.path.normpath(journal_original) != original:
                    lines.append(f"    journal:  {journal_original}")
                lines.append(f"    staged:   {staged}")
                lines.append(f"    state:    {state}")
    if dry_run:
        lines.append("Dry Run is read-only, so it will not move folders to repair this state.")
        lines.append("Run a normal (non-Dry-Run) inventory of this path to let TLO attempt automatic recovery first.")
    else:
        lines.append("TLO stopped rather than guessing about folder contents.")
        lines.append("Close any program that may be using the listed folders and run Inventory again.")
        lines.append("If the same error repeats, preserve the recovery container and journal; do not delete or merge them manually.")
        lines.append("A BOTH or MISSING state needs review of the exact original/staged paths shown above before any manual move.")
    return "\n".join(lines)


def _read_recovery_journal(container: str) -> dict:
    journal = os.path.join(container, JOURNAL_NAME)
    with open(journal, "r", encoding="utf-8") as infile:
        return json.load(infile)


def assert_no_interrupted_sibling_consolidations(start_path: str) -> None:
    """Read-only guard used by Dry Run before ordinary traversal."""
    for current, dirs, files in os.walk(start_path, topdown=True, followlinks=False):
        is_temp = os.path.basename(current).startswith(TEMP_PREFIX)
        has_journal = JOURNAL_NAME in files
        if is_temp or has_journal:
            payload = None
            reason = "recovery journal is present" if has_journal else "temporary collection folder exists without its recovery journal"
            if has_journal:
                try:
                    payload = _read_recovery_journal(current)
                except Exception as exc:
                    reason = f"recovery journal cannot be read: {exc}"
            raise SiblingCollectionRecoveryError(
                _format_recovery_error(current, payload, reason, dry_run=True)
            )
        dirs[:] = [name for name in dirs if not name.casefold().endswith("-ignoredir")]


def _emit(callback: Optional[Callable[[str], None]], text: str) -> None:
    if callback:
        callback(str(text))


def _is_under(path_name: str, root: str) -> bool:
    try:
        path_abs = os.path.abspath(os.path.normpath(path_name))
        root_abs = os.path.abspath(os.path.normpath(root))
        return os.path.commonpath([path_abs, root_abs]) == root_abs
    except (OSError, ValueError):
        return False


def _logged_media_paths(complete_path_log: str) -> List[str]:
    try:
        with open(complete_path_log, "r", encoding="utf-8", errors="ignore") as infile:
            lines = infile.readlines()
    except OSError:
        return []
    results = []
    for raw in lines:
        value = raw.strip()
        if value and not value.startswith("#") and not value.startswith("SEARCH_PATH:"):
            if os.path.splitext(value)[1].lower() in MEDIA_EXTENSIONS:
                results.append(os.path.normpath(value))
    return results


def _part_number(suffix: str) -> int:
    token = re.sub(
        r"(?i)^(?:cd|disc|disk|pt\.?|part|set|side|tape|d)[\s._-]*", "", suffix or ""
    ).strip().casefold()
    if token.isdigit():
        return int(token)
    if token in WORD_NUMBER:
        return WORD_NUMBER[token]
    if token and re.fullmatch(r"[ivx]{1,6}", token):
        values = {"i": 1, "v": 5, "x": 10}
        total = previous = 0
        for character in reversed(token):
            value = values[character]
            total += -value if value < previous else value
            previous = max(previous, value)
        return total
    return 0


def _suffix_info(folder_name: str) -> Optional[Tuple[str, str, int]]:
    name = str(folder_name or "").strip()
    match = ALT_SUFFIX_RE.fullmatch(name)
    if match:
        base = match.group("base").strip(" ._-")
        number = int(match.group("paren") or match.group("bare") or 0)
        if base and number > 0:
            return base, "alt", number
    base, suffix = split_wrapper_part_suffix(name)
    number = _part_number(suffix)
    if base and suffix and number > 0:
        return base, "part", number
    return None


def _natural_key(value: str) -> Tuple[object, ...]:
    return tuple(int(piece) if piece.isdigit() else piece for piece in re.split(r"(\d+)", str(value).casefold()))


def _normalize_title(value: str) -> str:
    title = TRAILING_TIME_RE.sub("", str(value or ""))
    title = re.sub(r"(?i)\s*(?:>|->)\s*$", "", title)
    title = re.sub(r"(?i)\([^)]*(?:cut|tape\s*flip|fade|audience)[^)]*\)\s*$", "", title)
    return " ".join(re.sub(r"[^\w]+", " ", title.casefold()).split())


def _decode_bytes(raw: bytes) -> str:
    choices = []
    for order, encoding in enumerate(("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252", "latin-1")):
        try:
            text = raw.decode(encoding, errors="replace")
        except Exception:
            continue
        score = sum(ch.isalpha() for ch in text) - text.count("\ufffd") * 4 - text.count("\x00") * 8
        choices.append((score, -order, text))
    return max(choices, default=(0, 0, ""))[2]


def _read_docx_text(path_name: str) -> str:
    try:
        with zipfile.ZipFile(path_name) as archive:
            document = archive.getinfo("word/document.xml")
            if document.file_size > 16 * 1024 * 1024:
                return ""
            root = ElementTree.fromstring(archive.read(document))
    except Exception:
        return ""
    namespace = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs = []
    for paragraph in root.iter(namespace + "p"):
        text = "".join(node.text or "" for node in paragraph.iter(namespace + "t"))
        if text.strip():
            paragraphs.append(text.strip())
    return "\n".join(paragraphs)


def _read_rtf_text(path_name: str) -> str:
    try:
        with open(path_name, "rb") as infile:
            raw = infile.read()
    except OSError:
        return ""
    text = _decode_bytes(raw)
    text = re.sub(r"\\par[d]?\b", "\n", text, flags=re.I)
    text = re.sub(r"\\'[0-9a-fA-F]{2}", " ", text)
    text = re.sub(r"\\[a-zA-Z]+-?\d*\s?", "", text)
    return text.replace("{", "").replace("}", "")


def _read_setlist_text(path_name: str) -> str:
    extension = os.path.splitext(path_name)[1].lower()
    if extension == ".docx":
        return _read_docx_text(path_name)
    if extension == ".rtf":
        return _read_rtf_text(path_name)
    try:
        with open(path_name, "rb") as infile:
            return _decode_bytes(infile.read())
    except OSError:
        return ""


def _candidate_setlists(root: str) -> List[str]:
    text_files, documents = [], []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = [
            name for name in dirs
            if not name.casefold().endswith("-ignoredir")
            and name.casefold() not in {"$recycle.bin", "system volume information"}
        ]
        for name in files:
            extension = os.path.splitext(name)[1].lower()
            if extension not in SETLIST_EXTENSIONS or HOUSEKEEPING_RE.search(name):
                continue
            path_name = os.path.normpath(os.path.join(current, name))
            (text_files if extension in TEXT_SETLIST_EXTENSIONS else documents).append(path_name)
    ranked = _ordered_txt_files(text_files) + _ordered_exception_files(documents)
    return sorted(dict.fromkeys(ranked), key=_natural_key)


def _titles_from_text(text: str) -> List[str]:
    results = []
    for line in str(text or "").splitlines():
        match = TRACK_LINE_RE.match(line.strip())
        if match:
            title = _normalize_title(match.group("title"))
            if title and title not in {"intro", "outro", "encore", "banter", "tuning"}:
                results.append(title)
    return results


def _audio_files_under(root: str) -> List[str]:
    results = []
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        dirs[:] = [
            name for name in dirs
            if not name.casefold().endswith("-ignoredir")
            and name.casefold() not in {"$recycle.bin", "system volume information"}
        ]
        for name in files:
            if os.path.splitext(name)[1].lower() in MEDIA_EXTENSIONS:
                results.append(os.path.normpath(os.path.join(current, name)))
    return sorted(results, key=_natural_key)


def _titles_from_audio_files(paths: Sequence[str]) -> List[str]:
    results = []
    for path_name in paths:
        stem = os.path.splitext(os.path.basename(path_name))[0]
        stem = LEADING_NUMBER_RE.sub("", LEADING_NUMBER_RE.sub("", FILE_TRACK_PREFIX_RE.sub("", stem)))
        title = _normalize_title(stem)
        if title and not title.isdigit():
            results.append(title)
    return results


def _member_evidence(path_name: str, index: int) -> CollectionMember:
    setlists = _candidate_setlists(path_name)
    titles = []
    for setlist in setlists:
        titles.extend(_titles_from_text(_read_setlist_text(setlist)))
    audio_files = _audio_files_under(path_name)
    if len(titles) < 2:
        titles = _titles_from_audio_files(audio_files)
    return CollectionMember(
        path=os.path.normpath(path_name),
        index=index,
        music_dirs=sorted({os.path.dirname(path) for path in audio_files}, key=_natural_key),
        titles=titles,
        setlist_files=setlists,
    )


def _similar_titles(left: Sequence[str], right: Sequence[str]) -> bool:
    left_values = [value for value in left if value]
    right_values = [value for value in right if value]
    if len(left_values) < 2 or len(right_values) < 2:
        return False
    left_set, right_set = set(left_values), set(right_values)
    smaller = min(len(left_set), len(right_set))
    if smaller and len(left_set & right_set) / smaller >= 0.60:
        return True
    best = 0
    for left_start in range(len(left_values)):
        for right_start in range(len(right_values)):
            run = 0
            while (
                left_start + run < len(left_values)
                and right_start + run < len(right_values)
                and left_values[left_start + run] == right_values[right_start + run]
            ):
                run += 1
            best = max(best, run)
    return best >= 3 and best / min(len(left_values), len(right_values)) >= 0.50


def _same_filesystem(paths: Iterable[str]) -> bool:
    try:
        return len({os.stat(path_name).st_dev for path_name in paths}) == 1
    except OSError:
        return False


def discover_collection_plans(start_path: str, logged_media_paths: Sequence[str]) -> List[CollectionPlan]:
    """Return direct-sibling plans represented by this search and partition."""
    start = os.path.abspath(os.path.normpath(start_path))
    media_dirs = sorted({os.path.dirname(os.path.normpath(path)) for path in logged_media_paths})
    rows: Dict[Tuple[str, str, str], Dict[str, Tuple[int, List[str]]]] = {}
    for music_dir in media_dirs:
        current = os.path.abspath(music_dir)
        while current != start and _is_under(current, start):
            parent = os.path.dirname(current)
            info = _suffix_info(os.path.basename(current))
            if info and parent:
                base, kind, index = info
                row = rows.setdefault((os.path.normcase(parent), base.casefold(), kind), {})
                row.setdefault(current, (index, []))[1].append(music_dir)
                if kind == "alt":
                    unsuffixed = os.path.join(parent, base)
                    if os.path.isdir(unsuffixed):
                        related = [candidate for candidate in media_dirs if _is_under(candidate, unsuffixed)]
                        if related:
                            row.setdefault(unsuffixed, (0, related))
                break
            current = parent

    plans = []
    for (_parent_key, _base_key, kind), candidates in rows.items():
        if len(candidates) < 2:
            continue
        first_path = next(iter(candidates))
        parent_dir = os.path.dirname(first_path)
        first_info = _suffix_info(os.path.basename(first_path))
        if not first_info:
            continue
        base_name = first_info[0]
        # Sibling collection consolidation is intentionally limited to non-specific
        # collection names.  xxxx-xx-xx is a complete show-date placeholder in TLO
        # and must therefore block physical sibling consolidation just like a real
        # yyyy-mm-dd date; otherwise unrelated unknown-date shows can be merged.
        if " - " not in base_name or FULL_DATE_RE.search(base_name) or UNKNOWN_FULL_DATE_RE.search(base_name):
            continue
        members = [
            _member_evidence(path_name, index)
            for path_name, (index, _music) in candidates.items()
            if os.path.isdir(path_name)
        ]
        members.sort(key=lambda member: (member.index, _natural_key(os.path.basename(member.path))))
        if len(members) < 2 or len({member.index for member in members}) != len(members):
            continue
        if not _same_filesystem([parent_dir] + [member.path for member in members]):
            continue
        included, excluded = [], []
        for member in members:
            if any(_similar_titles(prior.titles, member.titles) for prior in included):
                excluded.append(member.path)
                continue
            if kind == "alt" and included and (
                len(member.titles) < 2 or any(len(prior.titles) < 2 for prior in included)
            ):
                excluded.append(member.path)
                continue
            included.append(member)
        if len(included) < 2:
            continue
        final_path = os.path.join(parent_dir, base_name)
        if os.path.lexists(final_path) and all(
            os.path.normcase(final_path) != os.path.normcase(member.path) for member in included
        ):
            continue
        plans.append(CollectionPlan(parent_dir, base_name, kind, included, excluded))

    claimed, safe = set(), []
    for plan in sorted(plans, key=lambda item: _natural_key(item.final_path)):
        member_keys = {os.path.normcase(member.path) for member in plan.members}
        if claimed & member_keys:
            continue
        claimed.update(member_keys)
        safe.append(plan)
    return safe


def _staged_member_name(plan: CollectionPlan, member: CollectionMember) -> str:
    """Return the name used for a member inside the consolidated container.

    An ``alt`` family can include an unsuffixed member whose pathname is also
    the desired aggregate pathname.  Keeping that member's basename would
    create ``.../Name/Name`` after consolidation.  Stage that original member
    as ``(alt0)`` instead; numbered alternates keep their existing names and
    natural ordering.
    """
    original_name = os.path.basename(member.path)
    if plan.kind == "alt" and _same_path(member.path, plan.final_path):
        return f"{plan.base_name} (alt0)"
    return original_name


def _journal_payload(plan: CollectionPlan, temp_path: str) -> dict:
    return {
        "schema": 2,
        "temporary_path": os.path.normpath(temp_path),
        "final_path": os.path.normpath(plan.final_path),
        "generated_info": "info.txt",
        "members": [
            {
                "original": os.path.normpath(member.path),
                "child_name": os.path.basename(member.path),
                "staged_name": _staged_member_name(plan, member),
            }
            for member in plan.members
        ],
    }


def _write_json(path_name: str, payload: dict) -> None:
    with open(path_name, "w", encoding="utf-8", newline="\n") as outfile:
        json.dump(payload, outfile, ensure_ascii=False, indent=2, sort_keys=True)
        outfile.write("\n")
        outfile.flush()
        os.fsync(outfile.fileno())


def _validate_journal(container: str, payload: dict) -> bool:
    parent = os.path.dirname(os.path.normpath(container))
    final_path = _runtime_recovery_path(str(payload.get("final_path") or ""))
    members = list(payload.get("members") or [])
    if payload.get("schema") not in {1, 2} or not final_path or os.path.dirname(final_path) != parent or not members:
        return False
    staged_names = set()
    for row in members:
        original = _runtime_recovery_path(str(row.get("original") or ""))
        child_name = str(row.get("child_name") or "")
        staged_name = str(row.get("staged_name") or child_name)
        if not original or os.path.dirname(original) != parent or os.path.basename(original) != child_name:
            return False
        for name in (child_name, staged_name):
            if not name or os.path.sep in name or (os.path.altsep and os.path.altsep in name):
                return False
        staged_key = os.path.normcase(staged_name)
        if staged_key in staged_names:
            return False
        staged_names.add(staged_key)
    return True


def _rollback_container(container: str, payload: dict) -> bool:
    if not _validate_journal(container, payload):
        return False

    # When the planned final path is itself one of the original collection
    # members, a crash after temp->final rename leaves the recovery container
    # occupying that member's original pathname.  Move the whole container
    # aside first so that pathname can be restored like every other member.
    self_member = any(
        _same_path(_runtime_recovery_path(str(row.get("original") or "")), container)
        for row in payload["members"]
    )

    for row in payload["members"]:
        original = _runtime_recovery_path(row["original"])
        child = os.path.join(container, str(row.get("staged_name") or row["child_name"]))
        original_exists = os.path.lexists(original)
        child_exists = os.path.lexists(child)
        if _same_path(original, container):
            if not child_exists:
                return False
            continue
        if original_exists == child_exists:
            return False

    if self_member:
        parent = os.path.dirname(os.path.normpath(container))
        recovery_container = os.path.join(
            parent, f"{TEMP_PREFIX}recovery-{uuid.uuid4().hex}"
        )
        try:
            os.rename(container, recovery_container)
        except Exception as exc:
            raise _SiblingCollectionRollbackFailure(container, f"could not move the colliding recovery container aside: {exc}") from exc
        container = recovery_container

    try:
        for row in payload["members"]:
            original = _runtime_recovery_path(row["original"])
            child = os.path.join(container, str(row.get("staged_name") or row["child_name"]))
            if os.path.lexists(child):
                os.rename(child, original)
        for generated in (payload.get("generated_info"), JOURNAL_NAME):
            path_name = os.path.join(container, str(generated or ""))
            if generated and os.path.isfile(path_name):
                os.unlink(path_name)
        os.rmdir(container)
    except Exception as exc:
        raise _SiblingCollectionRollbackFailure(container, str(exc)) from exc
    return True


def recover_interrupted_sibling_consolidations(
    start_path: str, emit: Optional[Callable[[str], None]] = None
) -> int:
    recovered = 0
    for current, dirs, files in os.walk(start_path, topdown=True, followlinks=False):
        is_temp = os.path.basename(current).startswith(TEMP_PREFIX)
        has_journal = JOURNAL_NAME in files
        if not has_journal:
            if is_temp:
                dirs[:] = []
                raise SiblingCollectionRecoveryError(
                    _format_recovery_error(
                        current,
                        None,
                        "temporary collection folder exists without its recovery journal",
                    )
                )
            continue
        try:
            payload = _read_recovery_journal(current)
        except Exception as exc:
            _emit(emit, f"SIBLING_COLLECTION_RECOVERY_FAILED: {current} | unreadable journal: {exc}")
            dirs[:] = []
            raise SiblingCollectionRecoveryError(
                _format_recovery_error(
                    current, None, f"recovery journal cannot be read: {exc}"
                )
            ) from exc
        error_container = current
        try:
            success = _rollback_container(current, payload)
        except Exception as exc:
            success = False
            error_container = str(getattr(exc, "container", current) or current)
            _emit(emit, f"SIBLING_COLLECTION_RECOVERY_FAILED: {error_container} | {exc}")
            reason = f"automatic rollback failed: {exc}"
        else:
            reason = "folder state is ambiguous or the recovery container could not be removed"
        if not success:
            raise SiblingCollectionRecoveryError(
                _format_recovery_error(error_container, payload, reason)
            )
        recovered += 1
        _emit(emit, f"SIBLING_COLLECTION_RECOVERED: {current}")
        dirs[:] = []
    return recovered


def _concatenated_setlist_text(plan: CollectionPlan) -> str:
    sections = []
    for section_number, member in enumerate(plan.members, start=1):
        for setlist_path in sorted(member.setlist_files, key=_natural_key):
            text = _read_setlist_text(setlist_path).strip()
            if text:
                relative = os.path.relpath(setlist_path, member.path)
                sections.append(
                    f"Disc {section_number}\n[{os.path.basename(member.path)} / {relative}]\n{text}"
                )
    return "\n\n".join(sections).rstrip() + ("\n" if sections else "")


def _rewrite_complete_path_log(complete_path_log: str, rewrites: Sequence[Tuple[str, str]]) -> None:
    with open(complete_path_log, "rb") as infile:
        original = infile.read()
    text = original.decode("utf-8", errors="replace")
    output = []
    for raw in text.splitlines():
        value = raw.strip()
        replacement = value
        if value and not value.startswith("#") and not value.startswith("SEARCH_PATH:"):
            for old_root, new_root in rewrites:
                if _is_under(value, old_root):
                    replacement = os.path.join(new_root, os.path.relpath(value, old_root))
                    break
        output.append(raw if replacement == value else replacement)
    temp_log = complete_path_log + f".tlo-{uuid.uuid4().hex}.tmp"
    try:
        with open(temp_log, "w", encoding="utf-8", newline="\n") as outfile:
            outfile.write("\n".join(output) + ("\n" if text.endswith(("\n", "\r")) else ""))
            outfile.flush()
            os.fsync(outfile.fileno())
        os.replace(temp_log, complete_path_log)
    finally:
        if os.path.exists(temp_log):
            os.unlink(temp_log)


def _restore_complete_path_log(complete_path_log: str, original: bytes) -> None:
    temp_log = complete_path_log + f".tlo-restore-{uuid.uuid4().hex}.tmp"
    try:
        with open(temp_log, "wb") as outfile:
            outfile.write(original)
            outfile.flush()
            os.fsync(outfile.fileno())
        os.replace(temp_log, complete_path_log)
    finally:
        if os.path.exists(temp_log):
            os.unlink(temp_log)


def _execute_plan(plan: CollectionPlan, complete_path_log: str) -> None:
    temp_path = os.path.join(plan.parent_dir, f"{TEMP_PREFIX}{uuid.uuid4().hex}")
    final_path = os.path.normpath(plan.final_path)
    final_is_member = any(
        os.path.normcase(final_path) == os.path.normcase(member.path) for member in plan.members
    )
    if os.path.lexists(final_path) and not final_is_member:
        raise RuntimeError(f"destination already exists: {final_path}")
    with open(complete_path_log, "rb") as infile:
        original_log = infile.read()
    os.mkdir(temp_path)
    payload = _journal_payload(plan, temp_path)
    _write_json(os.path.join(temp_path, JOURNAL_NAME), payload)
    combined = _concatenated_setlist_text(plan)
    rewrites = []
    current_container = temp_path
    log_committed = False
    try:
        for member in plan.members:
            staged_name = _staged_member_name(plan, member)
            os.rename(member.path, os.path.join(temp_path, staged_name))
            rewrites.append((member.path, os.path.join(final_path, staged_name)))
        if combined:
            with open(os.path.join(temp_path, "info.txt"), "w", encoding="utf-8", newline="\n") as outfile:
                outfile.write(combined)
                outfile.flush()
                os.fsync(outfile.fileno())
        os.rename(temp_path, final_path)
        current_container = final_path
        _rewrite_complete_path_log(complete_path_log, rewrites)
        log_committed = True
        os.unlink(os.path.join(final_path, JOURNAL_NAME))
    except Exception:
        if log_committed:
            try:
                _restore_complete_path_log(complete_path_log, original_log)
            except Exception:
                pass
        try:
            _rollback_container(current_container, payload)
        except Exception:
            pass
        raise


def consolidate_sibling_collections(
    start_path: str,
    complete_path_log: str,
    emit: Optional[Callable[[str], None]] = None,
) -> List[dict]:
    results = []
    for plan in discover_collection_plans(start_path, _logged_media_paths(complete_path_log)):
        try:
            _execute_plan(plan, complete_path_log)
        except Exception as exc:
            _emit(emit, f"SIBLING_COLLECTION_FAILED: {plan.final_path} | {exc}")
            continue
        result = {
            "parent": plan.final_path,
            "kind": plan.kind,
            "children": [os.path.join(plan.final_path, _staged_member_name(plan, member)) for member in plan.members],
            "excluded_similar": list(plan.excluded_similar),
        }
        results.append(result)
        _emit(
            emit,
            f"SIBLING_COLLECTION_CREATED: {plan.final_path} | children={len(plan.members)} | excluded_similar={len(plan.excluded_similar)}",
        )
    return results
