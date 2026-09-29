"""Text cleanup utilities for safe titles, ASCII normalization, comparison keys, and full-file reads."""

__version__ = "v512"
import codecs
import os
import re
import unicodedata
import zipfile
from html import unescape

from tlo_constants import US_STATE_CODES



MAX_TEXT_SAMPLE_BYTES = 1 * 1024 * 1024
MAX_TEXT_FULL_BYTES = 16 * 1024 * 1024
MAX_DOCX_XML_BYTES = 16 * 1024 * 1024

SINGLE_QUOTE_TRANSLATION = str.maketrans({
    "‘": "'",
    "’": "'",
    "‛": "'",
    "′": "'",
    "ʼ": "'",
    "＇": "'",
    "`": "'",
})



ASCII_TEXT_TRANSLATION = str.maketrans({
    "\u00a0": " ", "\u1680": " ", "\u2000": " ", "\u2001": " ",
    "\u2002": " ", "\u2003": " ", "\u2004": " ", "\u2005": " ",
    "\u2006": " ", "\u2007": " ", "\u2008": " ", "\u2009": " ",
    "\u200a": " ", "\u202f": " ", "\u205f": " ", "\u3000": " ",
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
    "\u2014": "-", "\u2015": "-", "\u2212": "-", "\ufe58": "-",
    "\ufe63": "-", "\uff0d": "-",
    "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
    "\u2032": "'", "\u2035": "'", "\u0060": "'", "\u00b4": "'",
    "\uff07": "'",
    "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
    "\u2033": '"', "\u2036": '"', "\uff02": '"',
    "\u2026": "...", "\u00ad": "", "\ufeff": "", "\ufffd": "",
    "\u00df": "ss", "\u1e9e": "SS",
    "\u00e6": "ae", "\u00c6": "AE",
    "\u0153": "oe", "\u0152": "OE",
    "\u00f8": "o", "\u00d8": "O",
    "\u0111": "d", "\u0110": "D",
    "\u00f0": "d", "\u00d0": "D",
    "\u00fe": "th", "\u00de": "Th",
    "\u0142": "l", "\u0141": "L",
    "\u0131": "i", "\u0130": "I",
})


def standard_ascii_text(text: str, fallback: str = "") -> str:
    """Return text suitable for TLO-written names and tags using printable ASCII only.

    Accented Latin letters are transliterated where possible (for example,
    "Mötley Crüe" -> "Motley Crue"). Smart punctuation and Unicode spacing
    are converted to ordinary ASCII equivalents. Other non-ASCII/control
    characters are dropped.
    """
    value = str(text or "").translate(ASCII_TEXT_TRANSLATION)
    value = unicodedata.normalize("NFKD", value)
    out = []
    for ch in value:
        category = unicodedata.category(ch)
        if category.startswith("M"):
            continue
        if ch in "\r\n\t\f\v" or category.startswith("Z"):
            out.append(" ")
            continue
        if category in {"Cc", "Cf", "Cs", "Co", "Cn"}:
            continue
        if ord(ch) < 128 and ch.isprintable():
            out.append(ch)
    return compact_ws("".join(out)) or compact_ws(fallback)




FOLDER_NEVER_CONTAINED_INFO_FILE_MARKER = "folder never contained an info file"

def setlist_text_requests_generated_from_music_files(text: str) -> bool:
    """Return True for marker-only placeholder setlists that should be regenerated.

    Some old or external placeholder setlists contain only the sentence
    "Folder never contained an info file". Those files should not be copied into
    TLOHome/setlists as if they were real setlists; postprocess/tagging should
    regenerate from the folder music files. If the marker appears with other
    usable content, the content is retained and parsed normally.
    """
    normalized = normalize_single_quotes(text or "").casefold().strip()
    if FOLDER_NEVER_CONTAINED_INFO_FILE_MARKER not in normalized:
        return False
    remainder = normalized.replace(FOLDER_NEVER_CONTAINED_INFO_FILE_MARKER, "")
    remainder = re.sub(r"[\s\uFEFF.:'\"()\[\]{}!?;,-]+", "", remainder)
    return not remainder
def normalize_single_quotes(text: str) -> str:
    return (text or "").translate(SINGLE_QUOTE_TRANSLATION)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_single_quotes(text)).strip()


def clean_token_text(text: str) -> str:
    text = normalize_single_quotes(text).replace("_", " ").replace("/", " ")
    text = re.sub(r"[\[\]{}]+", " ", text)
    text = re.sub(r"\s+-\s+", " | ", text)
    return normalize_whitespace(text)


def normalized_compare_value(text: str) -> str:
    text = normalize_single_quotes(text).lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return normalize_whitespace(text)


def safe_title(text: str) -> str:
    words = []
    for word in normalize_whitespace(text).split():
        if word.upper() in US_STATE_CODES:
            words.append(word.upper())
        elif word.lower() in {"and", "of", "the", "at", "in", "on", "for", "a", "an"}:
            words.append(word.lower())
        elif re.fullmatch(r"[A-Z]{2,5}", word):
            words.append(word.upper())
        else:
            words.append(word[:1].upper() + word[1:])
    if not words:
        return ""
    words[0] = words[0][:1].upper() + words[0][1:]
    return " ".join(words)


def compact_ws(text: str) -> str:
    return " ".join(normalize_single_quotes(text).strip().split())


def _normalize_text_preserve_lines(text: str) -> str:
    lines = [compact_ws(line) for line in (text or "").replace("\r", "\n").split("\n")]
    kept = [line for line in lines if line]
    return "\n".join(kept)


def _decode_utf8_with_legacy_spans(raw: bytes) -> tuple[str, str]:
    """Preserve valid UTF-8 while decoding isolated legacy bytes as cp1252.

    ``surrogateescape`` marks only bytes that are invalid in UTF-8.  Converting
    those marked bytes back through cp1252 avoids turning the *valid* UTF-8
    portions of a mixed/hand-edited setlist into mojibake.
    """
    decoded = raw.decode("utf-8-sig", errors="surrogateescape")
    if not any("\udc80" <= ch <= "\udcff" for ch in decoded):
        return decoded, "utf-8-sig"

    out: list[str] = []
    legacy = bytearray()

    def flush_legacy() -> None:
        if not legacy:
            return
        data = bytes(legacy)
        legacy.clear()
        try:
            out.append(data.decode("cp1252"))
        except UnicodeDecodeError:
            out.append(data.decode("latin-1"))

    for ch in decoded:
        codepoint = ord(ch)
        if 0xDC80 <= codepoint <= 0xDCFF:
            legacy.append(codepoint - 0xDC00)
            continue
        flush_legacy()
        out.append(ch)
    flush_legacy()
    return "".join(out), "utf-8+cp1252"


def _bomless_utf16_encoding(raw: bytes) -> str:
    """Return a likely BOM-less UTF-16 endian encoding, or an empty string."""
    if len(raw) < 4 or raw.count(b"\x00") < max(2, len(raw) // 8):
        return ""
    even_nuls = sum(1 for byte in raw[0::2] if byte == 0)
    odd_nuls = sum(1 for byte in raw[1::2] if byte == 0)
    # ASCII-heavy UTF-16 LE places most NULs in odd byte positions; BE does
    # the inverse. Require a clear bias so arbitrary binary data is not guessed.
    if odd_nuls >= max(2, even_nuls * 2):
        return "utf-16-le"
    if even_nuls >= max(2, odd_nuls * 2):
        return "utf-16-be"
    return ""


def decode_text_bytes(raw: bytes) -> tuple[str, str]:
    """Decode traded setlist text without UTF-16 or mixed-encoding mojibake.

    BOM-marked and NUL-dominant UTF-16 are recognized *before* UTF-8 because
    NUL bytes are legal UTF-8 and would otherwise mask BOM-less UTF-16. Clean
    UTF-8 is preferred. A trailing partial UTF-8 sequence (common when a bounded
    sample ends inside a multi-byte character) is dropped without poisoning the
    whole sample. If strict UTF-8 still fails, valid UTF-8 spans are preserved
    while only invalid bytes are decoded through cp1252/latin-1.
    """
    raw = bytes(raw or b"")
    if not raw:
        return "", "empty"

    if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
        try:
            return raw.decode("utf-16"), "utf-16"
        except UnicodeDecodeError:
            pass

    bomless_utf16 = _bomless_utf16_encoding(raw)
    if bomless_utf16:
        try:
            return raw.decode(bomless_utf16), bomless_utf16
        except UnicodeDecodeError:
            pass

    for encoding in ("utf-8-sig", "utf-8"):
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError:
            pass

    # An incremental decoder with final=False accepts only the special case
    # where the sample ends in an incomplete multi-byte UTF-8 sequence. Any
    # invalid byte earlier in the sample still raises and falls through to the
    # mixed-encoding path below.
    try:
        decoder = codecs.getincrementaldecoder("utf-8-sig")("strict")
        text = decoder.decode(raw, final=False)
        buffered, _flag = decoder.getstate()
        if buffered:
            return text, "utf-8-truncated-sample"
    except (LookupError, UnicodeDecodeError):
        pass

    return _decode_utf8_with_legacy_spans(raw)




_RTF_DESTINATIONS = frozenset({
    "fonttbl", "colortbl", "stylesheet", "info", "pict", "object",
    "header", "headerl", "headerr", "headerf", "footer", "footerl",
    "footerr", "footerf", "generator", "themedata", "colorschememapping",
    "listtable", "listoverridetable", "rsidtbl", "xmlnstbl",
})

def _rtf_to_text(text: str) -> str:
    """Convert the subset of RTF used by trader setlists into plain text.

    The parser is deliberately small but group-aware: metadata/destination
    groups are skipped, character escapes are decoded using ansicpg, and
    paragraph/TextEdit line boundaries are preserved.
    """
    out = []
    stack = []
    state = {"skip": False, "uc": 1, "codepage": 1252, "group_start": True}
    skip_fallback = 0
    i = 0
    length = len(text)

    def emit(value: str) -> None:
        nonlocal skip_fallback
        if state["skip"]:
            return
        if skip_fallback > 0:
            skip_fallback -= 1
            return
        out.append(value)

    while i < length:
        ch = text[i]
        if ch == "{":
            stack.append(dict(state))
            state = dict(state)
            state["group_start"] = True
            i += 1
            continue
        if ch == "}":
            if stack:
                state = stack.pop()
            i += 1
            continue
        if ch != "\\":
            emit(ch)
            if not ch.isspace():
                state["group_start"] = False
            i += 1
            continue

        # Backslash followed by a physical newline is TextEdit's line break.
        if i + 1 < length and text[i + 1] in "\r\n":
            if not state["skip"]:
                out.append("\n")
            i += 2
            if i < length and text[i - 1] == "\r" and text[i] == "\n":
                i += 1
            continue
        if i + 1 >= length:
            i += 1
            continue
        nxt = text[i + 1]
        if nxt in "\\{}":
            emit(nxt)
            state["group_start"] = False
            i += 2
            continue
        if nxt == "*":
            state["skip"] = True
            i += 2
            continue
        if nxt == "'" and i + 3 < length:
            pair = text[i + 2:i + 4]
            try:
                byte = bytes([int(pair, 16)])
                encoding = f"cp{int(state['codepage'])}"
                decoded = byte.decode(encoding, errors="replace")
            except (ValueError, LookupError):
                decoded = "�"
            emit(decoded)
            state["group_start"] = False
            i += 4
            continue

        match = re.match(r"\\([A-Za-z]+)(-?\d+)? ?", text[i:])
        if match:
            word = match.group(1)
            number = match.group(2)
            lowered = word.casefold()
            i += len(match.group(0))
            if state.get("group_start") and lowered in _RTF_DESTINATIONS:
                state["skip"] = True
            state["group_start"] = False
            if lowered == "ansicpg" and number:
                try:
                    state["codepage"] = int(number)
                except ValueError:
                    pass
            elif lowered == "uc" and number:
                try:
                    state["uc"] = max(0, int(number))
                except ValueError:
                    pass
            elif lowered == "u" and number and not state["skip"]:
                value = int(number)
                if value < 0:
                    value += 65536
                try:
                    out.append(chr(value))
                except ValueError:
                    pass
                skip_fallback = int(state.get("uc", 1) or 0)
            elif lowered in {"par", "line"} and not state["skip"]:
                out.append("\n")
            elif lowered == "tab" and not state["skip"]:
                out.append(" ")
            elif not state["skip"]:
                symbol_words = {
                    "lquote": "'", "rquote": "'",
                    "ldblquote": '"', "rdblquote": '"',
                    "emdash": "-", "endash": "-",
                    "bullet": "•",
                    "emspace": " ", "enspace": " ", "qmspace": " ",
                }
                if lowered in symbol_words:
                    out.append(symbol_words[lowered])
            continue

        # Standard RTF control symbols that carry text semantics.
        if nxt == "~":
            emit(" ")
        elif nxt == "_":
            emit("-")
        elif nxt == "-":
            pass  # optional hyphen: emit nothing
        # Unknown control symbols are consumed rather than leaking RTF syntax.
        i += 2

    return _normalize_text_preserve_lines("".join(out))


def _read_text_content(
    path_name: str,
    *,
    max_bytes: int = MAX_TEXT_FULL_BYTES,
    allow_truncate: bool = False,
) -> str:
    if not path_name or not os.path.isfile(path_name):
        return ""

    _, ext = os.path.splitext(path_name)
    ext = ext.lower()
    byte_limit = max(1, int(max_bytes or 1))

    try:
        if ext == ".doc":
            # Legacy binary Word .doc files are not text. Keep the extension
            # discoverable for diagnostics, but never decode the binary payload
            # as setlist text.
            return ""
        if ext == ".docx":
            with zipfile.ZipFile(path_name, "r") as zf:
                info = zf.getinfo("word/document.xml")
                if int(info.file_size or 0) > MAX_DOCX_XML_BYTES:
                    return ""
                xml_bytes = zf.read(info)
                if len(xml_bytes) > MAX_DOCX_XML_BYTES:
                    return ""
                xml = xml_bytes.decode("utf-8", errors="ignore")
            xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
            xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
            xml = re.sub(r"</w:p>", "\n", xml)
            xml = re.sub(r"<[^>]+>", "", xml)
            return _normalize_text_preserve_lines(unescape(xml).replace("\t", " "))

        try:
            file_size = os.path.getsize(path_name)
        except OSError:
            file_size = 0
        if file_size > byte_limit and not allow_truncate:
            return ""

        with open(path_name, "rb") as infile:
            raw = infile.read(byte_limit + 1)
        if len(raw) > byte_limit:
            if not allow_truncate:
                return ""
            raw = raw[:byte_limit]

        text, _encoding = decode_text_bytes(raw)
        if ext == ".rtf":
            return _rtf_to_text(text)
        return text
    except OSError:
        return ""
    except (KeyError, zipfile.BadZipFile, RuntimeError):
        return ""

    return ""


def read_text_file_sample(path_name: str, max_chars: int = 20000) -> str:
    text = _read_text_content(
        path_name,
        max_bytes=MAX_TEXT_SAMPLE_BYTES,
        allow_truncate=True,
    )
    return text[:max_chars] if text else ""


def read_text_file_full(path_name: str) -> str:
    return _read_text_content(
        path_name,
        max_bytes=MAX_TEXT_FULL_BYTES,
        allow_truncate=False,
    )
