"""Shared TLO Research search logic for metadata and complete-path logs."""

from __future__ import annotations

__version__ = "v423"

from dataclasses import dataclass
import json
import os
import re
from typing import Iterable

from tlo_file_listing import scandir_matching_files


# Research deliberately reuses TLO's canonical inventory date parser instead
# of maintaining a separate date grammar. This keeps Research classification in
# lock-step with every date form Inventory accepts, including x-placeholders,
# textual months, compact dates, ranges, and slash forms. Standalone 19xx/20xx
# years remain valid Research dates even though Inventory does not generally
# treat a bare year as a performance-date match.
_STANDALONE_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$", re.IGNORECASE)


def _exact_date_normalizations(value: str) -> tuple[str, ...]:
    raw = " ".join(str(value or "").strip().split())
    if not raw:
        return ()
    if _STANDALONE_YEAR_RE.fullmatch(raw):
        return (raw,)

    # Lazy import keeps ordinary Inventory GUI startup light; the full metadata
    # parser is loaded only when Research actually needs to classify a query.
    from tlo_phase23_v2 import _find_date_matches

    matches = _find_date_matches(
        raw,
        allow_slash=True,
        allow_year_space_month_day_exception=True,
    )
    normalized: list[str] = []
    seen: set[str] = set()
    for match in matches:
        if match.get("start") != 0 or match.get("end") != len(raw):
            continue
        candidate = str(match.get("normalized") or "").strip()
        key = candidate.casefold()
        if candidate and key not in seen:
            seen.add(key)
            normalized.append(candidate)
    return tuple(normalized)


def _split_artist_trailing_date(raw: str) -> tuple[str, tuple[str, ...]]:
    # Try every whitespace boundary from left to right. The first exact date
    # suffix is the longest date expression, which correctly handles inputs such
    # as "Grateful Dead April 14, 2001" rather than misclassifying only "2001".
    for match in re.finditer(r"\s+", raw):
        artist = raw[: match.start()].strip()
        suffix = raw[match.end() :].strip()
        if not artist or not suffix:
            continue
        candidates = _exact_date_normalizations(suffix)
        if candidates:
            return artist, candidates
    return "", ()


@dataclass(frozen=True)
class ResearchQuery:
    kind: str
    raw: str
    artist: str = ""
    date: str = ""
    date_candidates: tuple[str, ...] = ()
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


@dataclass(frozen=True)
class RawLogHit:
    log_path: str
    line_number: int
    line: str


def _norm_text(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def _normalized_line(value: str) -> str:
    return " ".join(str(value or "").strip().split()).casefold()


def _line_directly_relates_to_query(line: str, query: ResearchQuery) -> bool:
    """Return True when one raw log line contains the supplied Research evidence.

    Structured matching remains field-aware. This broader raw-line pass exists so
    Research can also expose historical/source evidence that lives outside the
    selected metadata block (for example an original folder/tag string that later
    metadata normalization replaced).
    """
    haystack = _normalized_line(line)
    if not haystack:
        return False

    raw = _normalized_line(query.raw)
    if raw and raw in haystack:
        return True

    if query.kind == "date":
        return any(
            _normalized_line(candidate) in haystack
            for candidate in (query.date_candidates or (query.date,))
            if _normalized_line(candidate)
        )

    if query.kind == "artist_date":
        artist = _normalized_line(query.artist)
        if not artist or artist not in haystack:
            return False
        return any(
            _normalized_line(candidate) in haystack
            for candidate in (query.date_candidates or (query.date,))
            if _normalized_line(candidate)
        )

    if query.kind == "venue":
        venue = _normalized_line(query.venue)
        return bool(venue and venue in haystack)

    return False


def load_raw_query_hits(log_dir: str, query: ResearchQuery) -> list[RawLogHit]:
    """Return every raw meta/comp log line directly related to the query.

    No early exit or per-file cap is used. Line numbers are retained so Research
    can trace an unexpected value back to the exact historical log occurrence.
    """
    hits: list[RawLogHit] = []
    paths = scandir_matching_files(log_dir, "meta*.log")
    paths.extend(scandir_matching_files(log_dir, "comp*.log"))
    for log_path in sorted(set(paths), key=lambda p: p.casefold()):
        try:
            with open(log_path, "r", encoding="utf-8", errors="replace") as handle:
                for line_number, raw_line in enumerate(handle, 1):
                    line = raw_line.rstrip("\r\n")
                    if _line_directly_relates_to_query(line, query):
                        hits.append(RawLogHit(log_path=log_path, line_number=line_number, line=line))
        except OSError:
            continue
    return hits


def parse_research_query(value: str) -> ResearchQuery:
    """Classify INPUT as date, artist+date, or venue.

    Artist+date is recognized only when the input ends in one supported date
    token. This leaves venue names containing arbitrary numbers untouched.
    """
    raw = " ".join(str(value or "").strip().split())
    if not raw:
        raise ValueError("Research input must not be empty.")

    date_candidates = _exact_date_normalizations(raw)
    if date_candidates:
        return ResearchQuery(
            kind="date",
            raw=raw,
            date=date_candidates[0],
            date_candidates=date_candidates,
        )

    artist, date_candidates = _split_artist_trailing_date(raw)
    if artist and date_candidates:
        return ResearchQuery(
            kind="artist_date",
            raw=raw,
            artist=artist,
            date=date_candidates[0],
            date_candidates=date_candidates,
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
    for log_path in scandir_matching_files(log_dir, "meta*.log"):
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
    for log_path in scandir_matching_files(log_dir, "comp*.log"):
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
        record_date = _norm_text(record.first("DATE"))
        return any(record_date == _norm_text(candidate) for candidate in (query.date_candidates or (query.date,)))
    if query.kind == "artist_date":
        record_date = _norm_text(record.first("DATE"))
        return (
            _norm_text(record.first("ARTIST")) == _norm_text(query.artist)
            and any(record_date == _norm_text(candidate) for candidate in (query.date_candidates or (query.date,)))
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
    raw_hits = load_raw_query_hits(log_dir, query)

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
        lines.append("")

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

    lines.append("===== ALL RELATED RAW LOG LINES =====")
    lines.append(f"Raw log lines: {len(raw_hits)}")
    if raw_hits:
        for hit in raw_hits:
            lines.append(f"{os.path.basename(hit.log_path)}:{hit.line_number}: {hit.line}")
    else:
        lines.append("(no additional raw meta/comp lines directly matched the research input)")
    lines.append("")
    return "\n".join(lines).rstrip() + "\n"
