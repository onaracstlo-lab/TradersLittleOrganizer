#!/usr/bin/env python3
"""
tlo_setlistfm_lookup.py

setlist.fm venue/location lookup helper for TLO Inventory.

The lookup is intentionally small and dependency-free. It is based on the
standalone setlistFM.py utility supplied earlier, but returns structured
results for the inventory engine and enforces a cross-process minimum interval
between API requests.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple

__version__ = "v321"
# TLO-GI package version: v321
__version_summary__ = 'Hardens cleanup on forced GUI/CLI exits, SHN conversion timeouts, and setlist file reads.'
API_BASE = "https://api.setlist.fm/rest/1.0"
ENV_API_KEY = "SETLISTFM_API_KEY"
MIN_REQUEST_INTERVAL_SECONDS = 0.600
MAX_REQUESTS_PER_RUN = 1400
USER_AGENT = "tlo-setlistfm-venue-lookup/1.1"


class SetlistFMError(RuntimeError):
    pass


@dataclass(frozen=True)
class SetlistFMResult:
    artist: str
    event_date: str
    venue: str
    location: str
    city: str
    state: str
    state_code: str
    country: str
    country_code: str
    setlist_url: str
    venue_url: str
    setlists: Tuple[str, ...] = ()

    @property
    def setlists_in_order(self) -> List[str]:
        return [text for text in self.setlists if str(text or "").strip()]


_US_COUNTRY_NAMES = {
    "us",
    "u s",
    "u s a",
    "usa",
    "u.s.",
    "u.s.a.",
    "united states",
    "united states of america",
    "america",
}


def _compact_ws(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _norm_country(value: str) -> str:
    text = (value or "").casefold().strip()
    text = text.replace(".", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return _compact_ws(text)


def is_us_country(country: str, country_code: str = "") -> bool:
    if (country_code or "").strip().upper() == "US":
        return True
    return _norm_country(country) in _US_COUNTRY_NAMES


def normalize_name(value: str) -> str:
    value = (value or "").casefold().strip()
    value = value.replace("&", " and ")
    value = re.sub(r"^the\s+", "", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return _compact_ws(value)


def convert_date_for_api(date_text: str) -> str:
    try:
        parsed = datetime.strptime((date_text or "").strip(), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError(f"date must be yyyy-mm-dd, got: {date_text!r}") from exc
    return parsed.strftime("%d-%m-%Y")


def get_api_key() -> str:
    api_key = os.environ.get(ENV_API_KEY, "").strip()
    if not api_key:
        raise SetlistFMError(f"Missing API key. Set {ENV_API_KEY} before enabling setlist.fm lookup.")
    return api_key


def _rate_limit_state_file() -> str:
    root = os.path.join(tempfile.gettempdir(), "tlo_inventory_setlistfm_rate_limit")
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, "state.json")


def _rate_limit_lock_dir() -> str:
    return _rate_limit_state_file() + ".lock"


def _safe_run_id(run_id: str = "") -> str:
    text = str(run_id or "default").strip() or "default"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text)[:80] or "default"


def _read_rate_state(state_file: str) -> Dict[str, Any]:
    try:
        with open(state_file, "r", encoding="utf-8") as fh:
            raw = fh.read().strip()
    except Exception:
        return {"last_request": 0.0, "counts": {}}

    if not raw:
        return {"last_request": 0.0, "counts": {}}

    # Backward compatibility with older rate-limit files, which contained only a
    # timestamp as plain text.
    try:
        return {"last_request": float(raw), "counts": {}}
    except Exception:
        pass

    try:
        data = json.loads(raw)
    except Exception:
        return {"last_request": 0.0, "counts": {}}

    if not isinstance(data, dict):
        return {"last_request": 0.0, "counts": {}}
    counts = data.get("counts")
    if not isinstance(counts, dict):
        counts = {}
    try:
        last_request = float(data.get("last_request", 0.0) or 0.0)
    except Exception:
        last_request = 0.0
    return {"last_request": last_request, "counts": counts}


def _write_rate_state(state_file: str, state: Dict[str, Any]) -> None:
    with open(state_file, "w", encoding="utf-8") as fh:
        json.dump(state, fh, sort_keys=True)


def wait_for_rate_limit(
    min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
    *,
    max_calls: int = MAX_REQUESTS_PER_RUN,
    run_id: str = "",
) -> int:
    """Reserve one setlist.fm API request slot.

    The reservation enforces both requirements across local worker processes:
    one request every ``min_interval_seconds`` and no more than ``max_calls``
    requests for the current inventory run. A mkdir-based lock is used because
    os.mkdir is atomic on Windows and POSIX. If a stale lock is encountered, it
    is removed after a short grace period.
    """
    state_file = _rate_limit_state_file()
    lock_dir = _rate_limit_lock_dir()
    stale_after = 10.0
    safe_run_id = _safe_run_id(run_id)
    max_calls = int(max_calls or 0)

    while True:
        try:
            os.mkdir(lock_dir)
            break
        except FileExistsError:
            try:
                age = time.time() - os.path.getmtime(lock_dir)
                if age > stale_after:
                    os.rmdir(lock_dir)
                    continue
            except Exception:
                pass
            time.sleep(0.01)

    try:
        state = _read_rate_state(state_file)
        counts = state.setdefault("counts", {})
        try:
            current_count = int(counts.get(safe_run_id, 0) or 0)
        except Exception:
            current_count = 0

        if max_calls > 0 and current_count >= max_calls:
            raise SetlistFMError(
                f"setlist.fm call limit reached for this inventory run: {current_count}/{max_calls}"
            )

        last_request = float(state.get("last_request", 0.0) or 0.0)
        now = time.time()
        wait_time = float(min_interval_seconds) - (now - last_request)
        if wait_time > 0:
            time.sleep(wait_time)

        call_number = current_count + 1
        counts[safe_run_id] = call_number
        state["last_request"] = time.time()

        # Keep the file from growing forever if several test/manual runs use
        # unique run ids. The active run id and most recent known ids are kept.
        if len(counts) > 32:
            keep = list(counts.keys())[-31:]
            if safe_run_id not in keep:
                keep.append(safe_run_id)
            state["counts"] = {key: counts[key] for key in keep if key in counts}

        _write_rate_state(state_file, state)
        return call_number
    finally:
        try:
            os.rmdir(lock_dir)
        except Exception:
            pass

def api_get(
    path: str,
    params: Dict[str, str],
    api_key: str,
    timeout_seconds: int = 30,
    *,
    min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
    max_calls: int = MAX_REQUESTS_PER_RUN,
    run_id: str = "",
) -> Dict[str, Any]:
    wait_for_rate_limit(
        min_interval_seconds,
        max_calls=max_calls,
        run_id=run_id,
    )
    query = urllib.parse.urlencode(params)
    url = f"{API_BASE}{path}?{query}"

    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Accept-Language": "en",
            "x-api-key": api_key,
            "User-Agent": USER_AGENT,
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SetlistFMError(f"setlist.fm API request failed: HTTP {exc.code} {exc.reason}: {detail[:500]}") from exc
    except urllib.error.URLError as exc:
        raise SetlistFMError(f"setlist.fm API request failed: {exc.reason}") from exc

    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise SetlistFMError(f"setlist.fm returned non-JSON response: {body[:500]}") from exc


def ensure_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def compact_join(parts: Iterable[str], separator: str = ", ") -> str:
    return separator.join(part for part in (_compact_ws(p) for p in parts) if part)


def _setlistfm_song_name(song: Dict[str, Any]) -> str:
    name = str((song or {}).get("name") or "").strip()
    if not name:
        return ""
    # setlist.fm can include empty placeholders or section labels.  Keep real
    # song names only; comments/info are intentionally not folded into titles.
    if re.fullmatch(r"(?i)encore\s*\d*", name):
        return ""
    return _compact_ws(name)


def extract_normalized_setlists(setlist: Dict[str, Any]) -> Tuple[str, ...]:
    """Return numbered setlist text already present in one setlist.fm payload.

    This function does not make another API request.  It only uses the ``sets``
    object returned by the existing ``/search/setlists`` venue/location lookup.
    Each setlist.fm performance is kept as its own candidate, while song rows
    inside all sets/encores for that performance are combined in order.
    """
    sets = (setlist or {}).get("sets") or {}
    if not isinstance(sets, dict):
        return ()
    set_blocks = ensure_list(sets.get("set"))
    next_number = 1
    lines: List[str] = []
    for set_block in set_blocks:
        if not isinstance(set_block, dict):
            continue
        for song in ensure_list(set_block.get("song")):
            if not isinstance(song, dict):
                continue
            title = _setlistfm_song_name(song)
            if not title:
                continue
            lines.append(f"{next_number:02d} {title}")
            next_number += 1
    if not lines:
        return ()
    return ("\n".join(lines),)


def parse_result(setlist: Dict[str, Any]) -> SetlistFMResult:
    artist = setlist.get("artist") or {}
    venue = setlist.get("venue") or {}
    city = venue.get("city") or {}
    country = city.get("country") or {}

    city_name = str(city.get("name") or "").strip()
    state = str(city.get("state") or "").strip()
    state_code = str(city.get("stateCode") or "").strip()
    country_name = str(country.get("name") or "").strip()
    country_code = str(country.get("code") or "").strip()

    if is_us_country(country_name, country_code):
        location = compact_join([city_name, state_code or state], " ")
    else:
        location = compact_join([city_name, country_name], " ")

    return SetlistFMResult(
        artist=str(artist.get("name") or "").strip(),
        event_date=str(setlist.get("eventDate") or "").strip(),
        venue=str(venue.get("name") or "").strip(),
        location=location,
        city=city_name,
        state=state,
        state_code=state_code,
        country=country_name,
        country_code=country_code,
        setlist_url=str(setlist.get("url") or "").strip(),
        venue_url=str(venue.get("url") or "").strip(),
        setlists=extract_normalized_setlists(setlist),
    )


def search_setlists(
    artist: str,
    date_yyyy_mm_dd: str,
    api_key: Optional[str] = None,
    *,
    min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
    max_calls: int = MAX_REQUESTS_PER_RUN,
    run_id: str = "",
) -> List[SetlistFMResult]:
    api_key = api_key or get_api_key()
    api_date = convert_date_for_api(date_yyyy_mm_dd)
    payload = api_get(
        "/search/setlists",
        {
            "artistName": artist,
            "date": api_date,
            "p": "1",
        },
        api_key,
        min_interval_seconds=min_interval_seconds,
        max_calls=max_calls,
        run_id=run_id,
    )

    raw_setlists = ensure_list(payload.get("setlist"))
    results = [parse_result(item) for item in raw_setlists if isinstance(item, dict)]

    wanted = normalize_name(artist)
    exact_artist_results = [result for result in results if normalize_name(result.artist) == wanted]
    return exact_artist_results or results


def lookup_venue_and_location(
    artist: str,
    date_yyyy_mm_dd: str,
    debug: bool = False,
    *,
    min_interval_seconds: float = MIN_REQUEST_INTERVAL_SECONDS,
    max_calls: int = MAX_REQUESTS_PER_RUN,
    run_id: str = "",
) -> List[SetlistFMResult]:
    if not artist or not date_yyyy_mm_dd:
        return []
    return search_setlists(
        artist,
        date_yyyy_mm_dd,
        min_interval_seconds=min_interval_seconds,
        max_calls=max_calls,
        run_id=run_id,
    )


def collect_setlists_by_performance(results: List[SetlistFMResult]) -> List[Tuple[SetlistFMResult, List[str]]]:
    """Return cached setlist.fm setlist candidates from already-fetched results.

    The caller is responsible for obtaining ``results`` via the normal
    venue/location lookup.  This helper intentionally performs no API access.
    """
    candidates: List[Tuple[SetlistFMResult, List[str]]] = []
    for result in results or []:
        setlists = result.setlists_in_order
        if setlists:
            candidates.append((result, setlists))
    return candidates
