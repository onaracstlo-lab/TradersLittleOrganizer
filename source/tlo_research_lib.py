"""Shared TLO Research search logic for metadata and complete-path logs."""

from __future__ import annotations

__version__ = "v369"

from dataclasses import dataclass
import glob
import json
import os
import re
from typing import Iterable


# Research accepts the normalized date forms users see in TLO metadata. A
# single four-digit year is also valid. Unknown-only dates such as xxxx-xx-xx
# are intentionally not classified as date queries because they are not a
# specific date to research.
_DATE_TOKEN_RE = re.compile(
    r"^(?:19|20)\d{2}(?:"
    r"-(?:0[1-9]|1[0-2]|xx)(?:-(?:0[1-9]|[12]\d|3[01]|xx))?"
    r"|-(?:(?:19|20)?\d{2})"
    r")?$",
    re.IGNORECASE,
)
_TRAILING_DATE_RE = re.compile(
    r"^(?P<artist>.+?)\s+(?P<date>(?:19|20)\d{2}(?:"
    r"-(?:0[1-9]|1[0-2]|xx)(?:-(?:0[1-9]|[12]\d|3[01]|xx))?"
    r"|-(?:(?:19|20)?\d{2})"
    r")?)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResearchQuery:
    kind: str
    raw: str
    artist: str = ""
    date: str = ""
    venue: str = ""


@dataclass
class MetaRecord:
    log_path: str
    raw_text: str
    fields: dict[str, list[str]]

    def first(self, name: str) -> str:
        values = self.fields.get(name.upper(), [])
        return values[0] if values else ""


@dataclass(frozen=True)
class CompEntry:
    log_path: str
    line: str


def _norm_text(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def parse_research_query(value: str) -> ResearchQuery:
    """Classify INPUT as date, artist+date, or venue.

    Artist+date is recognized only when the input ends in one supported date
    token. This leaves venue names containing arbitrary numbers untouched.
    """
    raw = " ".join(str(value or "").strip().split())
    if not raw:
        raise ValueError("Research input must not be empty.")

    if _DATE_TOKEN_RE.fullmatch(raw):
        return ResearchQuery(kind="date", raw=raw, date=raw)

    match = _TRAILING_DATE_RE.fullmatch(raw)
    if match and match.group("artist").strip():
        return ResearchQuery(
            kind="artist_date",
            raw=raw,
            artist=match.group("artist").strip(),
            date=match.group("date"),
        )

    return ResearchQuery(kind="venue", raw=raw, venue=raw)


def _parse_meta_block(log_path: str, lines: list[str]) -> MetaRecord | None:
    if not lines:
        return None
    fields: dict[str, list[str]] = {}
    for line in lines:
        if ":" not in line:
            continue
        name, value = line.split(":", 1)
        key = name.strip().upper()
        if not key:
            continue
        fields.setdefault(key, []).append(value.strip())
    if not fields:
        return None
    raw_text = "\n".join(lines).rstrip() + "\n"
    return MetaRecord(log_path=log_path, raw_text=raw_text, fields=fields)


def load_meta_records(log_dir: str) -> list[MetaRecord]:
    """Read SHOW_NAME..END_SHOW_METADATA records from every meta*.log."""
    records: list[MetaRecord] = []
    for log_path in sorted(glob.glob(os.path.join(log_dir, "meta*.log")), key=lambda p: p.casefold()):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                block: list[str] = []
                in_record = False
                for raw_line in handle:
                    line = raw_line.rstrip("\r\n")
                    if line.startswith("SHOW_NAME:"):
                        # A new SHOW_NAME is also a safe boundary if a damaged or
                        # interrupted log omitted END_SHOW_METADATA.
                        if block:
                            parsed = _parse_meta_block(log_path, block)
                            if parsed is not None:
                                records.append(parsed)
                        block = [line]
                        in_record = True
                        continue
                    if not in_record:
                        continue
                    block.append(line)
                    if line.strip() == "END_SHOW_METADATA":
                        parsed = _parse_meta_block(log_path, block)
                        if parsed is not None:
                            records.append(parsed)
                        block = []
                        in_record = False
                if block:
                    parsed = _parse_meta_block(log_path, block)
                    if parsed is not None:
                        records.append(parsed)
        except OSError:
            # One unreadable historical log must not prevent research of the
            # remaining log files.
            continue
    return records


def load_comp_entries(log_dir: str) -> list[CompEntry]:
    """Load non-comment path entries from every comp*.log."""
    entries: list[CompEntry] = []
    for log_path in sorted(glob.glob(os.path.join(log_dir, "comp*.log")), key=lambda p: p.casefold()):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                for raw_line in handle:
                    line = raw_line.rstrip("\r\n")
                    stripped = line.strip()
                    if not stripped or stripped.startswith("#") or stripped.startswith("SEARCH_PATH:"):
                        continue
                    entries.append(CompEntry(log_path=log_path, line=stripped))
        except OSError:
            continue
    return entries


def record_matches(record: MetaRecord, query: ResearchQuery) -> bool:
    if query.kind == "date":
        return _norm_text(record.first("DATE")) == _norm_text(query.date)
    if query.kind == "artist_date":
        return (
            _norm_text(record.first("ARTIST")) == _norm_text(query.artist)
            and _norm_text(record.first("DATE")) == _norm_text(query.date)
        )
    if query.kind == "venue":
        venue = _norm_text(record.first("VENUE"))
        needle = _norm_text(query.venue)
        return bool(venue and needle and needle in venue)
    return False


def _record_prefixes(record: MetaRecord) -> list[str]:
    prefixes: list[str] = []
    main_dir = record.first("MAIN_DIR_PATH")
    if main_dir:
        prefixes.append(main_dir)
    for raw in record.fields.get("MUSIC_DIRS_JSON", []):
        try:
            decoded = json.loads(raw)
        except Exception:
            continue
        if isinstance(decoded, list):
            prefixes.extend(str(item) for item in decoded if str(item).strip())

    seen: set[str] = set()
    result: list[str] = []
    for item in prefixes:
        key = item.replace("/", "\\").rstrip("\\").casefold()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def comp_entries_for_record(record: MetaRecord, entries: Iterable[CompEntry]) -> list[CompEntry]:
    prefix_keys = [p.replace("/", "\\").rstrip("\\").casefold() for p in _record_prefixes(record)]
    if not prefix_keys:
        return []
    matched: list[CompEntry] = []
    for entry in entries:
        line_key = entry.line.replace("/", "\\").casefold()
        if any(line_key == prefix or line_key.startswith(prefix + "\\") for prefix in prefix_keys):
            matched.append(entry)
    return matched


def research_logs(tlo_home: str, query_text: str) -> str:
    """Return a human-readable Research report from TLO meta/comp logs."""
    query = parse_research_query(query_text)
    log_dir = os.path.join(tlo_home, "logs")
    if not os.path.isdir(log_dir):
        raise ValueError(f"TLO log directory does not exist: {log_dir}")

    meta_records = load_meta_records(log_dir)
    comp_entries = load_comp_entries(log_dir)
    matches = [record for record in meta_records if record_matches(record, query)]

    type_text = {
        "date": "date",
        "artist_date": "artist + date",
        "venue": "venue",
    }.get(query.kind, query.kind)
    lines: list[str] = [
        f"Research: {query.raw}",
        f"Type: {type_text}",
        f"Matches: {len(matches)}",
        "",
    ]
    if not matches:
        lines.append("No matching metadata records found.")
        return "\n".join(lines) + "\n"

    for index, record in enumerate(matches, 1):
        lines.append(f"===== MATCH {index} =====")
        lines.append(f"META LOG: {os.path.basename(record.log_path)}")
        lines.extend(record.raw_text.rstrip().splitlines())
        related = comp_entries_for_record(record, comp_entries)
        lines.append("COMP LOG:")
        if related:
            for entry in related:
                lines.append(f"{os.path.basename(entry.log_path)}: {entry.line}")
        else:
            lines.append("(no corresponding comp entry found)")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
