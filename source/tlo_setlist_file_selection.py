__version__ = "v318"
# TLO-GI package version: v318
__version_summary__ = 'Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.'
# TLO-GI version summary: Adds CorruptFlacs.txt logging for FLAC tagging failures and hidden --myTLO support to TLO Search.
import os
import re

from tlo_wrapper_rules import is_common_music_folder_name, is_wrapper_part_folder_name, split_wrapper_part_suffix
from tlo_constants import MONTH_NAME_CASED_PATTERN

SETLIST_NAME_PATTERNS = [
    re.compile(r"set[\s._-]*list", re.IGNORECASE),
    re.compile(r"info", re.IGNORECASE),
    re.compile(r"notes?", re.IGNORECASE),
    re.compile(r"read[\s._-]*me", re.IGNORECASE),
    re.compile(r"track", re.IGNORECASE),
    re.compile(r"song", re.IGNORECASE),
]

HOUSEKEEPING_NAME_PATTERNS = [
    re.compile(r"\bmd5\b", re.IGNORECASE),
    re.compile(r"\bffp\b", re.IGNORECASE),
    re.compile(r"\bfpt\b", re.IGNORECASE),
    re.compile(r"\bsfv\b", re.IGNORECASE),
    re.compile(r"checksum", re.IGNORECASE),
    re.compile(r"checksums", re.IGNORECASE),
    re.compile(r"fingerprint", re.IGNORECASE),
    re.compile(r"finger", re.IGNORECASE),
    re.compile(r"\bst5\b", re.IGNORECASE),
    re.compile(r"\bshn\b", re.IGNORECASE),
    re.compile(r"\bcue\b", re.IGNORECASE),
    re.compile(r"\bm3u\b", re.IGNORECASE),
    re.compile(r"\bm3u8\b", re.IGNORECASE),
    re.compile(r"\bpls\b", re.IGNORECASE),
    re.compile(r"\blog\b", re.IGNORECASE),
    re.compile(r"torrent", re.IGNORECASE),
    re.compile(r"spectrogram", re.IGNORECASE),
    re.compile(r"aucdtect", re.IGNORECASE),
    re.compile(r"dislaimer", re.IGNORECASE),
    re.compile(r"disclaimer", re.IGNORECASE),
    re.compile(r"easyed", re.IGNORECASE),
    re.compile(r"previous", re.IGNORECASE),
    re.compile(r"trader[']?s?\s*little\s*helper", re.IGNORECASE),
    re.compile(r"\btlh\b", re.IGNORECASE),
    re.compile(r"folder[\s._-]*aucdtect", re.IGNORECASE),
    re.compile(r"ffmpeg", re.IGNORECASE),
]

SETLIST_CONTENT_PATTERNS = [
    re.compile(r"^\s*\d{1,2}[.) -]+\s*\S+", re.IGNORECASE),
    re.compile(r"^\s*d[0-9]+t[0-9]+", re.IGNORECASE),
    re.compile(r"set\s*1|set\s*2|encore", re.IGNORECASE),
    re.compile(r"^\s*disc\s*\d+", re.IGNORECASE),
    re.compile(r"^\s*cd\s*\d+", re.IGNORECASE),
]

DATE_PATTERNS = [
    r"(?<![0-9xX])(?:\d{2}|(?:19|20)\d{2})(?:\s*[._-]\s*|\s+)[0-9xX]{1,2}(?:\s*[._-]\s*|\s+)[0-9xX]{1,2}(?![0-9xX])",
    r"(?<![0-9xX])[0-9xX]{1,2}(?:\s*[._-]\s*|\s+)[0-9xX]{1,2}(?:\s*[._-]\s*|\s+)(?:\d{2}|(?:19|20)\d{2})(?![0-9xX])",
    r"(?<![0-9xX])[0-9xX]{1,2}\s*/\s*[0-9xX]{1,2}\s*/\s*(?:\d{2}|(?:19|20)\d{2})(?![0-9xX])",
    r"(?<![0-9xX])(?:19|20)\d{6}(?![0-9xX])",
    r"(?<![0-9xX])(?:19|20)\d{2}[ -]\d{4}(?![0-9xX])",
    rf"(?<![A-Za-z0-9]){MONTH_NAME_CASED_PATTERN}[\s._,\-]*\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?[\s._,\-]*(?:\d{{2}}|(?:19|20)\d{{2}})(?![A-Za-z0-9])",
    rf"(?<![A-Za-z0-9])\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?[\s._,\-]*{MONTH_NAME_CASED_PATTERN}[\s._,\-]*(?:\d{{2}}|(?:19|20)\d{{2}})(?![A-Za-z0-9])",
    rf"(?<![A-Za-z0-9])(?:19|20)\d{{2}}[\s._,\-]*{MONTH_NAME_CASED_PATTERN}[\s._,\-]*\d{{1,2}}(?:st|nd|rd|th|ST|ND|RD|TH)?(?![A-Za-z0-9])",
    rf"(?<![A-Za-z0-9]){MONTH_NAME_CASED_PATTERN}[\s._,\-]*(?:19|20)\d{{2}}(?![A-Za-z0-9])",
]
_COMPILED_DATE_PATTERNS = [re.compile(pattern) for pattern in DATE_PATTERNS]

_AUDIO_FILENAME_LINE_RE = re.compile(
    r"^[\w .()\[\]{}'&+-]+\.(?:flac|shn|shnf|wav|mp3|m4a|aac|ogg|oga|opus|aif|aiff|ape|wv|alac)$",
    re.IGNORECASE,
)
_CHECKSUM_LINE_PATTERNS = [
    re.compile(r"^\s*[a-fA-F0-9]{16,128}\s+[* ]?.+\s*$"),
    re.compile(r"^\s*.+?\s*[:=]\s*[a-fA-F0-9]{16,128}\s*$"),
    re.compile(r"^\s*[a-fA-F0-9]{8,128}\s*$"),
    re.compile(r"^\s*[a-fA-F0-9]{8}\s+.+\s*$"),
]
_TEXT_SAMPLE_CACHE = {}
_TXT_ANALYSIS_CACHE = {}


def _decoded_text_quality(raw_bytes, text):
    raw = raw_bytes or b""
    decoded = text or ""
    alpha_count = sum(ch.isalpha() for ch in decoded)
    printable_count = sum((ch.isprintable() and ch not in "\x00\ufffd") or ch in "\r\n\t" for ch in decoded)
    decoded_len = len(decoded)
    decoded_null_count = decoded.count("\x00")
    null_count = raw.count(b"\x00")
    raw_len = len(raw)
    null_ratio = (null_count / raw_len) if raw_len else 0.0
    decoded_null_ratio = (decoded_null_count / decoded_len) if decoded_len else 0.0
    printable_ratio = (printable_count / decoded_len) if decoded_len else 0.0
    return {
        "alpha_count": alpha_count,
        "printable_ratio": printable_ratio,
        "null_ratio": null_ratio,
        "decoded_null_ratio": decoded_null_ratio,
        "raw_len": raw_len,
        "decoded_len": decoded_len,
    }


def _decode_text_sample_bytes(raw):
    if not raw:
        return "", _decoded_text_quality(raw, "")

    candidates = []
    # UTF-16 files legitimately contain many NUL bytes. Try BOM and inferred
    # UTF-16 before deciding that a NUL-heavy text file is unusable.
    for order, encoding in enumerate(("utf-8-sig", "utf-16", "utf-16-le", "utf-16-be", "cp1252", "latin-1")):
        try:
            decoded = raw.decode(encoding, errors="ignore")
        except Exception:
            continue
        quality = _decoded_text_quality(raw, decoded)
        decoded_null_penalty = int(quality.get("decoded_null_ratio", 0.0) * 1000)
        score = quality["alpha_count"] - decoded_null_penalty + int(quality["printable_ratio"] * 10)
        candidates.append((score, -order, decoded, quality))

    if not candidates:
        return "", _decoded_text_quality(raw, "")
    candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return candidates[0][2], candidates[0][3]


def _is_unreadable_or_null_text_sample(text, quality):
    value = text or ""
    q = quality or {}
    raw_len = int(q.get("raw_len") or 0)
    alpha_count = int(q.get("alpha_count") or 0)
    printable_ratio = float(q.get("printable_ratio") or 0.0)
    null_ratio = float(q.get("null_ratio") or 0.0)
    decoded_null_ratio = float(q.get("decoded_null_ratio") or 0.0)

    if raw_len == 0:
        return True
    # Full-of-NUL or binary-like candidates should not be selected even when
    # their filename is attractive (for example info.txt).
    if decoded_null_ratio >= 0.10:
        return True
    if null_ratio >= 0.30 and alpha_count < 3:
        return True
    if alpha_count < 3:
        return True
    if printable_ratio < 0.60:
        return True
    return False


def _looks_like_checksum_line(text):
    line = (text or "").strip()
    if not line:
        return False
    if not any(ch.isdigit() for ch in line):
        return False
    compact = re.sub(r"\s+", " ", line)
    return any(pattern.match(compact) for pattern in _CHECKSUM_LINE_PATTERNS)


def _looks_like_human_info_line(text):
    line = (text or "").strip()
    if not line:
        return False
    if _looks_like_checksum_line(line):
        return False
    if _AUDIO_FILENAME_LINE_RE.match(line):
        return False

    lowered = line.lower()
    if any(pattern.search(line) for pattern in SETLIST_CONTENT_PATTERNS):
        return True
    if any(pattern.search(line) for pattern in _COMPILED_DATE_PATTERNS):
        return True

    alpha_words = re.findall(r"[A-Za-z]{2,}", line)
    alpha_count = sum(ch.isalpha() for ch in line)

    if len(alpha_words) >= 2 and alpha_count >= 6:
        return True
    if alpha_count >= 8 and any(marker in line for marker in (",", " - ", "|", "@")):
        return True
    if alpha_count >= 12 and not re.search(
        r"md5|ffp|fpt|checksum|checksums|finger|fingerprint|sfv|aucdtect|spectrogram|torrent|m3u8?|pls|cue|log|easyed|previous|dislaimer|disclaimer",
        lowered,
        re.IGNORECASE,
    ):
        return True

    return False


def _safe_read_text_sample(path_name, max_bytes=16000):
    normalized = os.path.normpath(path_name)
    cache_key = (normalized, max_bytes)
    cached = _TEXT_SAMPLE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    text = ""
    quality = _decoded_text_quality(b"", "")
    try:
        with open(path_name, "rb") as infile:
            raw = infile.read(max_bytes)
        text, quality = _decode_text_sample_bytes(raw)
    except OSError:
        text = ""
        quality = _decoded_text_quality(b"", "")
    _TEXT_SAMPLE_CACHE[cache_key] = (text, quality)
    return text, quality


def _analyze_txt_file(path_name):
    normalized = os.path.normpath(path_name)
    cached = _TXT_ANALYSIS_CACHE.get(normalized)
    if cached is not None:
        return cached

    text, quality = _safe_read_text_sample(path_name, max_bytes=32000)
    analysis = {"text": text, "is_checksum_only": False, "is_unreadable_or_null": False, "content_score": 0}
    if _is_unreadable_or_null_text_sample(text, quality):
        analysis["is_unreadable_or_null"] = True
        analysis["content_score"] = -1000
    elif text:
        meaningful_lines = []
        for raw_line in text.splitlines()[:120]:
            stripped = raw_line.strip()
            if stripped:
                meaningful_lines.append(stripped)
        if len(meaningful_lines) >= 3:
            checksum_count = sum(1 for line in meaningful_lines if _looks_like_checksum_line(line))
            info_count = sum(1 for line in meaningful_lines if _looks_like_human_info_line(line))
            analysis["is_checksum_only"] = (
                info_count == 0 and checksum_count >= 3 and checksum_count >= max(3, int(len(meaningful_lines) * 0.6))
            )
        if not analysis["is_checksum_only"]:
            score = 0
            for line in text.splitlines()[:80]:
                stripped = line.strip()
                if not stripped:
                    continue
                for pattern in SETLIST_CONTENT_PATTERNS:
                    if pattern.search(stripped):
                        score += 5
                if 2 <= len(stripped.split()) <= 10 and len(stripped) < 80:
                    if not re.search(r"md5|ffp|checksum|torrent|spectrogram|aucdtect|sfv|m3u|m3u8|pls|cue|log", stripped, re.IGNORECASE):
                        score += 1
            analysis["content_score"] = score
        else:
            analysis["content_score"] = -1000
    _TXT_ANALYSIS_CACHE[normalized] = analysis
    return analysis


def _is_checksum_only_txt_file(path_name):
    return _analyze_txt_file(path_name)["is_checksum_only"]


def _is_unreadable_or_null_txt_file(path_name):
    return _analyze_txt_file(path_name).get("is_unreadable_or_null", False)


def _is_disqualified_txt_file(path_name):
    base_name = os.path.basename(path_name).lower()
    return any(pattern.search(base_name) for pattern in HOUSEKEEPING_NAME_PATTERNS)


def _txt_content_score(path_name):
    return _analyze_txt_file(path_name)["content_score"]


def _txt_name_score(path_name):
    base_name = os.path.basename(path_name).lower()
    score = 0
    for pattern in SETLIST_NAME_PATTERNS:
        if pattern.search(base_name):
            score += 10
    if base_name == "info.txt":
        score += 40
    if "setlist" in base_name:
        score += 25
    if "info" in base_name:
        score += 8
    if "readme" in base_name or "read_me" in base_name or "read-me" in base_name:
        score += 5
    score -= min(len(base_name), 80) / 100.0
    return score


def _exception_name_score(path_name):
    base_name = os.path.basename(path_name).lower()
    score = 0
    for pattern in SETLIST_NAME_PATTERNS:
        if pattern.search(base_name):
            score += 10
    if base_name in {"info.doc", "info.docx", "info.rtf"}:
        score += 40
    if "setlist" in base_name:
        score += 25
    if "info" in base_name:
        score += 8
    if "readme" in base_name or "read_me" in base_name or "read-me" in base_name:
        score += 5
    score -= min(len(base_name), 80) / 100.0
    return score


def _ordered_exception_files(files):
    return sorted([p for p in files if p], key=lambda p: (-_exception_name_score(p), p.lower()))


def _choose_best_exception_file(files):
    ordered = _ordered_exception_files(files)
    return ordered[0] if ordered else ""


def _ordered_txt_files(txt_files):
    filtered = [
        p for p in txt_files
        if not _is_disqualified_txt_file(p)
        and not _is_unreadable_or_null_txt_file(p)
        and not _is_checksum_only_txt_file(p)
    ]
    return sorted(filtered, key=lambda p: (-(_txt_content_score(p) * 3 + _txt_name_score(p)), p.lower()))


def _choose_best_txt_file(txt_files):
    ordered = _ordered_txt_files(txt_files)
    return ordered[0] if ordered else ""


def _filesystem_files_in_dir_with_extensions(target_dir, extensions):
    """Return direct child files in target_dir whose extensions match."""
    normalized_target = os.path.normpath(target_dir or "")
    normalized_exts = {ext.lower() for ext in extensions}
    results = []
    try:
        with os.scandir(normalized_target) as entries:
            children = sorted(list(entries), key=lambda entry: entry.name.lower())
    except (OSError, PermissionError, FileNotFoundError):
        return results
    for entry in children:
        try:
            if entry.is_file(follow_symlinks=False) and os.path.splitext(entry.name)[1].lower() in normalized_exts:
                results.append(os.path.normpath(entry.path))
        except (OSError, PermissionError):
            continue
    return results


def _filesystem_files_under_dir_with_extensions(target_dir, extensions):
    """Return descendant files below target_dir whose extensions match, excluding target_dir itself."""
    normalized_target = os.path.normpath(target_dir or "")
    normalized_exts = {ext.lower() for ext in extensions}
    results = []
    for root, dirs, files in os.walk(normalized_target, topdown=True, followlinks=False):
        dirs[:] = [d for d in dirs if not str(d or "").strip().lower().endswith("-ignoredir") and str(d or "").strip().lower() not in {"$recycle.bin", "system volume information"}]
        if os.path.normpath(root) == normalized_target:
            continue
        for filename in sorted(files, key=lambda value: value.lower()):
            if os.path.splitext(filename)[1].lower() in normalized_exts:
                results.append(os.path.normpath(os.path.join(root, filename)))
    return results


def _files_in_dir_with_extensions(path_list, target_dir, extensions):
    normalized_target = os.path.normpath(target_dir)
    normalized_exts = {ext.lower() for ext in extensions}
    results = [
        p for p in path_list
        if os.path.dirname(os.path.normpath(p or "")) == normalized_target and os.path.splitext(p or "")[1].lower() in normalized_exts
    ]
    # Phase 1 now logs only a representative media file path for each music
    # directory. Setlist names are discovered here, at the moment they are
    # needed, by scanning the known music directory or allowed parent.
    results.extend(_filesystem_files_in_dir_with_extensions(normalized_target, normalized_exts))
    return _unique_ordered(results)


def _files_under_dir_with_extensions(path_list, target_dir, extensions):
    normalized_target = os.path.normpath(target_dir)
    normalized_exts = {ext.lower() for ext in extensions}
    results = []
    for p in path_list:
        if os.path.splitext(p or "")[1].lower() not in normalized_exts:
            continue
        parent = os.path.dirname(os.path.normpath(p or ""))
        if parent == normalized_target:
            continue
        try:
            if os.path.commonpath([normalized_target, os.path.normpath(p)]) == normalized_target:
                results.append(p)
        except ValueError:
            continue
    results.extend(_filesystem_files_under_dir_with_extensions(normalized_target, normalized_exts))
    return _unique_ordered(results)


def _unique_ordered(paths):
    seen = set()
    ordered = []
    for path_name in paths:
        normalized = os.path.normpath(path_name or "")
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(normalized)
    return ordered


def _direct_child_dirs_from_logged_paths(path_list, parent_dir):
    normalized_parent = os.path.normpath(parent_dir)
    children = []
    seen = set()

    def add_child(path_name):
        normalized = os.path.normpath(path_name or "")
        if not normalized:
            return
        key = normalized.casefold()
        if key not in seen:
            seen.add(key)
            children.append(normalized)

    # Legacy complete-path logs may contain directory rows. Keep supporting
    # them, but do not require them.
    for path_name in path_list:
        normalized = os.path.normpath(path_name or "")
        if not normalized or os.path.dirname(normalized) != normalized_parent:
            continue
        if os.path.isdir(normalized):
            add_child(normalized)

    # v215+ logs carry only representative media file paths, so determine
    # parent-child safety from the live filesystem when the setlist lookup is
    # actually performed.
    try:
        with os.scandir(normalized_parent) as entries:
            for entry in sorted(list(entries), key=lambda entry: entry.name.lower()):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        add_child(entry.path)
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError, FileNotFoundError):
        pass

    return sorted(children, key=lambda value: value.lower())


def _wrapper_relationship_key(dir_name):
    name = str(dir_name or "").strip()
    if not name:
        return ""
    base_name, suffix = split_wrapper_part_suffix(name)
    if suffix:
        # Exact wrapper folders (CD1, Disc 1, Set 2, etc.) are all related as
        # release parts under the same parent. Suffix forms must share the same
        # stripped base (Big Release CD1 / Big Release CD2).
        return (base_name or "__exact_wrapper_part__").casefold()
    if is_common_music_folder_name(name):
        return "__common_music_wrapper__"
    return ""


def _all_child_dirs_related_release_parts(child_dirs):
    if not child_dirs:
        return False
    keys = []
    for child_dir in child_dirs:
        key = _wrapper_relationship_key(os.path.basename(child_dir))
        if not key:
            return False
        keys.append(key)
    # Exact wrapper/common folders such as CD1/CD2/FLAC are mutually related.
    # Wrapper-suffixed folders are related only when their stripped release base
    # is identical.
    meaningful = [key for key in keys if key not in {"__exact_wrapper_part__", "__common_music_wrapper__"}]
    if meaningful and len(set(meaningful)) > 1:
        return False
    return True


def _release_child_name_tokens(child_dirs):
    tokens = []
    for child_dir in child_dirs:
        name = os.path.basename(child_dir or "").casefold()
        name = re.sub(r"\b(?:cd|disc|disk|set|part)\s*\d+\b", " ", name)
        name = re.sub(r"\d+", " ", name)
        pieces = [p for p in re.split(r"[^a-z]+", name) if len(p) >= 3]
        tokens.append(pieces)
    return tokens


def _child_dirs_share_release_prefix(child_dirs):
    """Return True when siblings appear to be parts of one release.

    This is intentionally a safety signal, not a broad artist-folder match: it
    requires at least two non-trivial normalized leading words shared by every
    child directory after common part/disk/number tokens are removed.
    """
    if len(child_dirs) < 2:
        return False
    token_lists = _release_child_name_tokens(child_dirs)
    if any(len(tokens) < 2 for tokens in token_lists):
        return False
    first = token_lists[0]
    common_count = 0
    for idx, token in enumerate(first[:4]):
        if all(len(tokens) > idx and tokens[idx] == token for tokens in token_lists[1:]):
            common_count += 1
        else:
            break
    return common_count >= 2


def _small_parent_lookup_allowed(child_dirs, music_dir):
    """Allow parent lookup for compact release folders.

    A parent with twelve or fewer child directories is considered a plausible
    single-release container, particularly for multi-disc or split-set layouts.
    The caller still ranks direct music-folder setlists ahead of parent/sibling
    candidates, and broad artist folders with many children remain excluded.
    """
    if not child_dirs:
        return False
    normalized_music = os.path.normcase(os.path.normpath(music_dir or ""))
    normalized_children = {os.path.normcase(os.path.normpath(child)) for child in child_dirs}
    if normalized_music not in normalized_children:
        return False
    if len(child_dirs) <= 12:
        return True
    return _child_dirs_share_release_prefix(child_dirs)


_SPECIAL_SETLIST_DIR_RE = re.compile(
    r"(?i)^(?:info|infos|extras?|set[\s._-]*lists?|set[\s._-]*list|data|notes?|docs?|documentation|text|txt)$"
)


def _special_setlist_child_dirs(parent_dir, music_dir, child_dirs):
    """Return sibling info/setlist/data folders that may contain setlists."""
    normalized_music = os.path.normcase(os.path.normpath(music_dir or ""))
    results = []
    for child_dir in child_dirs:
        normalized_child = os.path.normcase(os.path.normpath(child_dir or ""))
        if not normalized_child or normalized_child == normalized_music:
            continue
        name = os.path.basename(child_dir or "").strip()
        if _SPECIAL_SETLIST_DIR_RE.match(name):
            results.append(os.path.normpath(child_dir))
    # If the filesystem scan failed to return a special folder but one exists,
    # include it.  This keeps the helper useful in tests and on stale logs.
    for name in ("info", "Info", "extras", "Extras", "extra", "Extra", "setlist", "setlists", "set list", "data", "notes", "docs"):
        candidate = os.path.join(parent_dir, name)
        if os.path.isdir(candidate):
            ncase = os.path.normcase(os.path.normpath(candidate))
            if ncase != normalized_music and all(os.path.normcase(os.path.normpath(p)) != ncase for p in results):
                results.append(os.path.normpath(candidate))
    return sorted(results, key=lambda value: value.lower())


def _parent_setlist_lookup_allowed(path_list, music_dir, parent_dir):
    """Return True when a parent folder is safe to use for setlist lookup.

    Parent setlists are allowed only when the parent is directly related to the
    music folder: a single-child parent, a media-only wrapper child, a parent
    whose child directories are all related wrapper/release parts, or a compact
    parent with twelve or fewer child directories. This prevents selecting an
    artist-folder or broad collection-folder setlist for one child show merely
    because that parent contains the current music directory.
    """
    normalized_music = os.path.normpath(music_dir)
    normalized_parent = os.path.normpath(parent_dir or "")
    if not normalized_parent or os.path.dirname(normalized_music) != normalized_parent:
        return False

    child_dirs = _direct_child_dirs_from_logged_paths(path_list, normalized_parent)
    if not child_dirs:
        return is_common_music_folder_name(os.path.basename(normalized_music)) or is_wrapper_part_folder_name(os.path.basename(normalized_music))

    if len(child_dirs) == 1 and os.path.normcase(child_dirs[0]) == os.path.normcase(normalized_music):
        return True

    if _all_child_dirs_related_release_parts(child_dirs):
        return True

    if _small_parent_lookup_allowed(child_dirs, normalized_music):
        return True

    return False


def find_setlist_files_for_music_dir(all_logged_paths, music_dir, main_dir_path):
    """Return ordered usable setlist candidates for a music directory.

    The order preserves the single-setlist selection precedence while allowing
    aggregated release-part groups to concatenate all unique candidates.
    """
    music_dir = os.path.normpath(music_dir)
    main_dir_path = os.path.normpath(main_dir_path)
    ordered = []

    # First look directly in the music directory.
    direct_exception_files = _files_in_dir_with_extensions(all_logged_paths, music_dir, {".rtf", ".doc", ".docx"})
    ordered.extend(_ordered_exception_files(direct_exception_files))
    direct_txt_candidates = _files_in_dir_with_extensions(all_logged_paths, music_dir, {".txt"})
    ordered.extend(_ordered_txt_files(direct_txt_candidates))

    # Parent-folder setlists are common for release-part/media-wrapper folders,
    # but broad artist or collection parents must not be searched just because
    # they contain the current child. Only use the immediate parent when that
    # parent is directly related to the child or to all sibling release parts.
    search_dirs = []
    parent_dir = os.path.dirname(music_dir)
    parent_allowed = _parent_setlist_lookup_allowed(all_logged_paths, music_dir, parent_dir)
    child_dirs = _direct_child_dirs_from_logged_paths(all_logged_paths, parent_dir) if parent_allowed else []
    if parent_allowed:
        search_dirs.append(os.path.normpath(parent_dir))
        search_dirs.extend(_special_setlist_child_dirs(parent_dir, music_dir, child_dirs))

    # main_dir_path may be the parent for aggregated wrapper-part groups. Keep
    # it only when it is the same allowed immediate parent; do not walk upward
    # into unrelated ancestors for setlist candidates.
    if main_dir_path not in search_dirs and main_dir_path != music_dir:
        if os.path.normpath(main_dir_path) == os.path.normpath(parent_dir) and parent_allowed:
            search_dirs.append(os.path.normpath(main_dir_path))

    seen_dirs = set()
    ordered_dirs = []
    for d in search_dirs:
        nd = os.path.normpath(d)
        if nd not in seen_dirs:
            seen_dirs.add(nd)
            ordered_dirs.append(nd)

    for target_dir in ordered_dirs:
        exception_files = _files_in_dir_with_extensions(all_logged_paths, target_dir, {".rtf", ".doc", ".docx"})
        ordered.extend(_ordered_exception_files(exception_files))

    for target_dir in ordered_dirs:
        txt_candidates = _files_in_dir_with_extensions(all_logged_paths, target_dir, {".txt"})
        ordered.extend(_ordered_txt_files(txt_candidates))

    # Descendant paths are last. This keeps parent/main setlists ahead of
    # deeper incidental text files, but lets aggregated release-part groups keep
    # unique disc-specific setlists when they exist.
    descendant_exception_files = _files_under_dir_with_extensions(all_logged_paths, music_dir, {".rtf", ".doc", ".docx"})
    ordered.extend(_ordered_exception_files(descendant_exception_files))

    descendant_txt_candidates = _files_under_dir_with_extensions(all_logged_paths, music_dir, {".txt"})
    ordered.extend(_ordered_txt_files(descendant_txt_candidates))

    return _unique_ordered(ordered)


def find_setlist_file_for_music_dir(all_logged_paths, music_dir, main_dir_path):
    candidates = find_setlist_files_for_music_dir(all_logged_paths, music_dir, main_dir_path)
    return candidates[0] if candidates else ""
