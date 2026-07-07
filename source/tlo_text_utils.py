"""Text cleanup utilities for safe titles, ASCII normalization, comparison keys, and full-file reads."""

__version__ = "v322"
# TLO-GI package version: v322
__version_summary__ = 'Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.'
# TLO-GI version summary: Preserves trailing parenthetical show-name suffixes across compliant Add Shows, full inventory rename/tag, and standalone tagging.
import os
import re
import unicodedata
import zipfile
from html import unescape

from tlo_constants import US_STATE_CODES


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


def _read_text_content(path_name: str) -> str:
    if not path_name or not os.path.isfile(path_name):
        return ""

    _, ext = os.path.splitext(path_name)
    ext = ext.lower()

    try:
        if ext == ".docx":
            with zipfile.ZipFile(path_name, "r") as zf:
                xml = zf.read("word/document.xml").decode("utf-8", errors="ignore")
            xml = re.sub(r"<w:tab[^>]*/>", "\t", xml)
            xml = re.sub(r"<w:br[^>]*/>", "\n", xml)
            xml = re.sub(r"</w:p>", "\n", xml)
            xml = re.sub(r"<[^>]+>", "", xml)
            return _normalize_text_preserve_lines(unescape(xml).replace("\t", " "))

        with open(path_name, "rb") as infile:
            raw = infile.read()

        for encoding in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                text = raw.decode(encoding, errors="ignore")
                if ext == ".rtf":
                    text = re.sub(r"\\par[d]?", "\n", text)
                    text = re.sub(r"\\'[0-9a-fA-F]{2}", "", text)
                    text = re.sub(r"\\[a-zA-Z]+-?\d* ?", "", text)
                    text = re.sub(r"[{}]", "", text)
                    return _normalize_text_preserve_lines(text)
                return text
            except Exception:
                continue
    except OSError:
        return ""
    except (KeyError, zipfile.BadZipFile):
        return ""

    return ""


def read_text_file_sample(path_name: str, max_chars: int = 20000) -> str:
    text = _read_text_content(path_name)
    return text[:max_chars] if text else ""


def read_text_file_full(path_name: str) -> str:
    return _read_text_content(path_name)
