"""Folder-only reversal for logged TLO rename/copy/copy-delete operations."""
from __future__ import annotations

__version__ = "v471"

from dataclasses import dataclass
from datetime import datetime
import os
import re
import shutil
from typing import Callable, Iterable, Optional

from logging_lib import ensure_logs_dir
from tlo_file_listing import scandir_matching_files
from tlo_path_inputs import normalize_platform_input_path, resolve_tlo_home, strip_optional_quotes
from tlo_tree_compare import directory_trees_exactly_match


class ReverseFoldersError(RuntimeError):
    pass


_TRANSFER_RE = re.compile(
    r"^(?P<code>TAG_COPY_DELETE_(?:MOVE|COPY)|TAG_COPY|RENAME_COMPLIANTLY):\s+"
    r"(?P<source>.+?)\s+->\s+(?P<destination>.+?)\s*$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class FolderOperation:
    log_path: str
    line_number: int
    code: str
    source: str
    destination: str

    @property
    def operation(self) -> str:
        code = self.code.upper()
        if code.startswith("TAG_COPY_DELETE_"):
            return "copy-delete"
        if code == "TAG_COPY":
            return "copy"
        return "rename"


@dataclass(frozen=True)
class ReversePlan:
    tlo_home: str
    requested_path: str
    log_path: str
    operations: tuple[FolderOperation, ...]


@dataclass
class ReverseFoldersResult:
    planned: int = 0
    reversed: int = 0
    already_reversed: int = 0
    conflicts: int = 0
    skipped: int = 0
    errors: int = 0
    messages: list[str] | None = None

    def __post_init__(self) -> None:
        if self.messages is None:
            self.messages = []


def _norm(value: str) -> str:
    raw = strip_optional_quotes(value or "").strip()
    if not raw:
        return ""
    return os.path.normpath(normalize_platform_input_path(raw))


def _key(value: str) -> str:
    return os.path.normcase(os.path.normpath(value))


def _same_or_under(path_name: str, root: str) -> bool:
    try:
        return os.path.commonpath([os.path.abspath(path_name), os.path.abspath(root)]) == os.path.abspath(root)
    except (ValueError, OSError):
        return False


def _related(path_name: str, requested: str) -> bool:
    return _key(path_name) == _key(requested) or _same_or_under(path_name, requested) or _same_or_under(requested, path_name)


def _candidate_tag_logs(tlo_home: str) -> list[str]:
    logs_dir = os.path.join(tlo_home, "logs")
    found: list[str] = []
    for pattern in ("tags*.txt", "tag*.log"):
        found.extend(scandir_matching_files(logs_dir, pattern))
    return sorted({os.path.normpath(p) for p in found if os.path.isfile(p)})


def operations_from_log(log_path: str) -> list[FolderOperation]:
    result: list[FolderOperation] = []
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as infile:
            for line_number, raw in enumerate(infile, start=1):
                match = _TRANSFER_RE.match(raw.strip())
                if not match:
                    continue
                source = _norm(match.group("source"))
                destination = _norm(match.group("destination"))
                if not source or not destination:
                    continue
                result.append(FolderOperation(log_path, line_number, match.group("code").upper(), source, destination))
    except OSError:
        return []
    return result


def _operation_is_current(op: FolderOperation) -> bool:
    src = os.path.isdir(op.source)
    dst = os.path.isdir(op.destination)
    if op.operation == "copy":
        return src and dst
    return dst and not os.path.exists(op.source)


def _operation_is_already_reversed(op: FolderOperation) -> bool:
    src = os.path.isdir(op.source)
    dst = os.path.exists(op.destination)
    if op.operation == "copy":
        return src and not dst
    return src and not dst


def _matching_operations(log_path: str, requested_path: str) -> list[FolderOperation]:
    return [op for op in operations_from_log(log_path) if _related(op.source, requested_path) or _related(op.destination, requested_path)]


def prepare_reverse_plan(
    path: str,
    *,
    tlo_home: str = "",
    my_tlo: str = "",
    log_path: str = "",
) -> ReversePlan:
    resolved_home = resolve_tlo_home(tlo_home=tlo_home, my_tlo=my_tlo, error_type=ReverseFoldersError)
    requested = _norm(path)
    if not requested or not os.path.isabs(requested):
        raise ReverseFoldersError("Path must be a fully qualified folder path.")

    if log_path:
        chosen = _norm(log_path)
        if not os.path.isfile(chosen):
            raise ReverseFoldersError(f"Specified log does not exist: {chosen}")
        ops = _matching_operations(chosen, requested)
        if not ops:
            raise ReverseFoldersError("The specified log contains no folder operation matching the requested path.")
        return ReversePlan(resolved_home, requested, chosen, tuple(ops))

    candidates: list[tuple[str, list[FolderOperation], int, float]] = []
    for candidate in _candidate_tag_logs(resolved_home):
        ops = _matching_operations(candidate, requested)
        if not ops:
            continue
        current_count = sum(1 for op in ops if _operation_is_current(op))
        already_count = sum(1 for op in ops if _operation_is_already_reversed(op))
        active_score = current_count * 100 + already_count
        try:
            mtime = os.path.getmtime(candidate)
        except OSError:
            mtime = 0.0
        candidates.append((candidate, ops, active_score, mtime))

    if not candidates:
        raise ReverseFoldersError(f"No logged folder operation matches: {requested}")

    # Existing destination/source state identifies the run in normal cases.
    best_score = max(item[2] for item in candidates)
    best = [item for item in candidates if item[2] == best_score]
    if best_score == 0:
        raise ReverseFoldersError(
            "Matching historical log entries were found, but none match the current folder state. "
            "Nothing was selected automatically. Use a narrower path or --log."
        )

    # If more than one run is still active for the same broad path, never guess.
    active_best = [item for item in best if any(_operation_is_current(op) for op in item[1])]
    if len(active_best) > 1:
        names = ", ".join(os.path.basename(item[0]) for item in sorted(active_best, key=lambda x: x[3], reverse=True))
        raise ReverseFoldersError(
            "More than one logged run matches the requested path and current folder state: " + names + ". Use a narrower path or --log."
        )
    chosen = active_best[0] if active_best else max(best, key=lambda item: item[3])
    return ReversePlan(resolved_home, requested, chosen[0], tuple(chosen[1]))


def _relative_file_names(root: str) -> set[str]:
    found: set[str] = set()
    for current, _dirs, files in os.walk(root):
        for name in files:
            found.add(os.path.normcase(os.path.normpath(os.path.relpath(os.path.join(current, name), root))))
    return found


def _append_audit(tlo_home: str, lines: Iterable[str]) -> str:
    target = os.path.join(ensure_logs_dir(tlo_home), "reverseFolders.log")
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %I:%M:%S %p %Z").lstrip("0")
    with open(target, "a", encoding="utf-8", newline="\n") as out:
        out.write(f"Reverse Folders | {stamp}\n")
        for line in lines:
            out.write(str(line).rstrip("\r\n") + "\n")
        out.write("\n")
    return target


def reverse_folder_operations(
    plan: ReversePlan,
    *,
    dry_run: bool = False,
    emit: Optional[Callable[[str], None]] = None,
) -> ReverseFoldersResult:
    result = ReverseFoldersResult(planned=len(plan.operations))
    audit = [
        f"Requested path: {plan.requested_path}",
        f"Selected log: {plan.log_path}",
        f"Operations: {len(plan.operations)}",
        f"Dry run: {'yes' if dry_run else 'no'}",
    ]

    def report(text: str) -> None:
        result.messages.append(text)
        audit.append(text)
        if emit:
            emit(text)

    # Reverse deepest destinations first so nested mappings cannot invalidate parents.
    operations = sorted(plan.operations, key=lambda op: (op.destination.count(os.sep), op.line_number), reverse=True)
    for op in operations:
        src_exists = os.path.isdir(op.source)
        dst_exists = os.path.isdir(op.destination)
        prefix = f"{op.operation.upper()} line {op.line_number}"

        if _operation_is_already_reversed(op):
            result.already_reversed += 1
            report(f"ALREADY_REVERSED: {prefix}: {op.destination} -> {op.source}")
            continue

        if op.operation == "copy":
            if not src_exists or not dst_exists:
                result.skipped += 1
                report(f"SKIPPED: {prefix}: expected both original and copied folder to exist | {op.source} | {op.destination}")
                continue
            # TAG_COPY may legitimately alter audio tags in the copy. Compare only
            # relative file identity, not bytes/sizes, before deleting the copied tree.
            try:
                if _relative_file_names(op.source) != _relative_file_names(op.destination):
                    result.conflicts += 1
                    report(f"CONFLICT: {prefix}: copy contents no longer have the same relative file set; copy left untouched | {op.destination}")
                    continue
            except OSError as exc:
                result.errors += 1
                report(f"ERROR: {prefix}: {exc}")
                continue
            if dry_run:
                result.reversed += 1
                report(f"WOULD_REMOVE_COPY: {op.destination} (original retained at {op.source})")
                continue
            try:
                shutil.rmtree(op.destination)
                result.reversed += 1
                report(f"REMOVED_COPY: {op.destination} (original retained at {op.source})")
            except Exception as exc:
                result.errors += 1
                report(f"ERROR: {prefix}: {exc}")
            continue

        if src_exists and dst_exists:
            result.conflicts += 1
            report(f"CONFLICT: {prefix}: original and destination both exist; left untouched | {op.destination} -> {op.source}")
            continue
        if not dst_exists:
            result.skipped += 1
            report(f"SKIPPED: {prefix}: logged destination is absent | {op.destination}")
            continue

        parent = os.path.dirname(op.source)
        if dry_run:
            result.reversed += 1
            report(f"WOULD_RESTORE_{op.operation.upper()}: {op.destination} -> {op.source}")
            continue
        try:
            os.makedirs(parent, exist_ok=True)
            if os.path.lexists(op.source):
                raise ReverseFoldersError("original path appeared during reversal")
            same_fs = os.stat(op.destination).st_dev == os.stat(parent).st_dev
            if same_fs:
                os.rename(op.destination, op.source)
            else:
                temp = op.source + ".tlo-reverse-partial"
                if os.path.lexists(temp):
                    raise ReverseFoldersError(f"temporary reverse path already exists: {temp}")
                shutil.copytree(op.destination, temp, symlinks=False)
                if not directory_trees_exactly_match(op.destination, temp):
                    shutil.rmtree(temp, ignore_errors=True)
                    raise ReverseFoldersError("cross-filesystem reverse verification failed")
                os.rename(temp, op.source)
                shutil.rmtree(op.destination)
            result.reversed += 1
            report(f"RESTORED_{op.operation.upper()}: {op.destination} -> {op.source}")
        except Exception as exc:
            result.errors += 1
            report(f"ERROR: {prefix}: {exc}")

    report(
        f"Complete: planned={result.planned} reversed={result.reversed} already_reversed={result.already_reversed} "
        f"conflicts={result.conflicts} skipped={result.skipped} errors={result.errors}"
    )
    _append_audit(plan.tlo_home, audit)
    return result
