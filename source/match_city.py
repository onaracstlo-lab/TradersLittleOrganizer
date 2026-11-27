#!/usr/bin/env python3
"""Fast SQLite-backed city matcher for the TLO cities.sqlite database.

Usage:
    py -3 match_city.py --city "Abbottsford" --state BC
    py -3 match_city.py --city "San Fransisco" --state CA --json
    py -3 match_city.py --city "Portland" --json

Only the Python standard library is required. The DB stores canonical names,
alternate spellings, location aliases, and reviewed fuzzy-match exclusions.
"""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION

__version__ = _TLO_CANONICAL_VERSION

import argparse
import json
from pathlib import Path
import re
import sqlite3
import sys
import unicodedata

REPLACEMENTS = {"ß": "ss", "æ": "ae", "œ": "oe", "ø": "o", "ł": "l", "ð": "d", "þ": "th"}
GB_LABELS = {"uk", "unitedkingdom", "greatbritain", "england", "scotland", "wales", "northernireland"}
US_STATES = set("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC".split())
CA_PROVS = set("AB BC MB NB NL NS NT NU ON PE QC SK YT".split())


def normalize(text: str) -> str:
    s = str(text).casefold()
    for old, new in REPLACEMENTS.items():
        s = s.replace(old, new)
    s = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]", "", s)


def edit_distance(a: str, b: str, cutoff: int) -> int:
    """Bounded optimal-string-alignment Damerau-Levenshtein distance."""
    if abs(len(a) - len(b)) > cutoff:
        return cutoff + 1
    previous_previous = None
    previous = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        current = [i] + [0] * len(b)
        for j, y in enumerate(b, 1):
            current[j] = min(previous[j] + 1, current[j - 1] + 1,
                             previous[j - 1] + (x != y))
            if i > 1 and j > 1 and x == b[j - 2] and a[i - 2] == y:
                current[j] = min(current[j], previous_previous[j - 2] + 1)
        previous_previous, previous = previous, current
    return previous[-1]


def max_edits(size: int) -> int:
    if size < 5:
        return 0
    if size < 8:
        return 1
    if size < 16:
        return 2
    return 3


class CityMatcher:
    """Reusable SQLite lookup. Keeps one read-only connection open for a batch.

    `resolve()` returns EXACT, ALIAS, FUZZY_HIGH, REVIEW, AMBIGUOUS, NOT_FOUND.
    Only the first three statuses permit automatic replacement.
    """

    def __init__(self, db_path: str | Path):
        self.path = Path(db_path).resolve()
        if not self.path.is_file():
            raise FileNotFoundError(f"Missing cities.sqlite: {self.path}")
        self.connection = sqlite3.connect(self.path.as_uri() + "?mode=ro", uri=True)
        self.connection.row_factory = sqlite3.Row
        try:
            self.connection.execute("PRAGMA query_only=ON")
            self._validate_schema()
        except Exception:
            self.connection.close()
            raise

    def _validate_schema(self) -> None:
        version = self.connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
        if version is None or version[0] != "1":
            raise ValueError("Unsupported cities.sqlite schema version; rebuild with supplied script")

    def __enter__(self) -> "CityMatcher":
        return self

    def __exit__(self, _type, _value, _traceback) -> None:
        self.close()

    def close(self) -> None:
        self.connection.close()

    def _scope(self, city_id: int, state_norm: str) -> int:
        if not state_norm:
            return 0
        matches = self.connection.execute(
            "SELECT region_norm FROM region_names WHERE city_id=? AND "
            "(region_norm=? OR region_norm IN ('uk','unitedkingdom','greatbritain','england','scotland','wales','northernireland'))",
            (city_id, state_norm),
        ).fetchall()
        if any(r[0] == state_norm for r in matches):
            return 3
        if state_norm in GB_LABELS and any(r[0] in GB_LABELS for r in matches):
            return 1
        return -1

    def _no_match(self, city: str, state: str, reason: str) -> dict:
        return {"status": "NOT_FOUND", "input_city": city, "input_state": state,
                "reason": reason, "suggestions": []}

    def resolve(self, city: str, state: str = "", limit: int = 5) -> dict:
        if limit < 1:
            raise ValueError("limit must be at least one")
        city = str(city)
        state = str(state).strip()
        target = normalize(city)
        st = normalize(state)
        if not target:
            return self._no_match(city, state, "Empty city name")
        if state and "," in city:
            first, suffix = city.rsplit(",", 1)
            if normalize(suffix) == st:
                target = normalize(first)
        # Look up exactly normalized city/alias spellings first, using the index.
        matches = self.connection.execute(
            "SELECT DISTINCT c.city_id, c.canonical_city, c.region, "
            "MAX(n.is_canonical) AS canonical_hit "
            "FROM city_names n JOIN cities c USING(city_id) "
            "WHERE n.name_norm=? GROUP BY c.city_id",
            (target,),
        ).fetchall()
        exact = []
        for r in matches:
            scope = self._scope(r["city_id"], st)
            if not state or scope > 0:
                exact.append((r, scope, "EXACT" if r["canonical_hit"] else "ALIAS"))
        if exact:
            best_scope = max(item[1] for item in exact)
            exact = [item for item in exact if item[1] == best_scope]
            exact.sort(key=lambda x: (x[2] != "EXACT", x[0]["canonical_city"].casefold(),
                                      x[0]["region"].casefold()))
            # Multiple master rows with identical city names but different states
            # remain ambiguous when no state was supplied.
            canon = {normalize(item[0]["canonical_city"]) for item in exact}
            if len(canon) == 1 and (state or len(exact) == 1):
                r, _, method = exact[0]
                return {"status": method, "input_city": city, "input_state": state,
                        "canonical_city": r["canonical_city"], "canonical_state": r["region"],
                        "confidence": "HIGH", "reason": "Exact normalized canonical name or explicit alias",
                        "suggestions": []}
            return {"status": "AMBIGUOUS", "input_city": city, "input_state": state,
                    "reason": "Multiple different canonical places share this name/alias",
                    "suggestions": [{"city": r["canonical_city"], "state": r["region"]}
                                    for r, _, _ in exact[:limit]]}

        cutoff = max_edits(len(target))
        if not cutoff:
            return self._no_match(city, state, "Short name has no exact match")
        # The length-indexed scan tests only spellings close enough in length;
        # geography constraints are applied by indexed region_names lookups.
        params: list = [max(1, len(target) - cutoff), len(target) + cutoff]
        sql = (
            "SELECT c.city_id,c.canonical_city,c.region,n.name,n.name_norm,"
            "n.name_length FROM city_names n JOIN cities c USING(city_id) "
            "WHERE n.name_length BETWEEN ? AND ?"
        )
        if state:
            allowed = sorted(GB_LABELS) if st in GB_LABELS else [st]
            sql += (" AND EXISTS (SELECT 1 FROM region_names r WHERE r.city_id=c.city_id "
                    f"AND r.region_norm IN ({','.join('?' for _ in allowed)}))")
            params.extend(allowed)
        candidates = self.connection.execute(sql, params)
        found: dict[int, dict] = {}
        for r in candidates:
            distance = edit_distance(target, r["name_norm"], cutoff)
            if distance > cutoff:
                continue
            similarity = 1 - distance / max(len(target), len(r["name_norm"]))
            if similarity < 0.80:
                continue
            scope = self._scope(r["city_id"], st) if state else 0
            if state and scope < 0:
                continue
            suggestion = {"city": r["canonical_city"], "state": r["region"],
                          "matched_spelling": r["name"], "edit_distance": distance,
                          "similarity": round(similarity, 4), "geography_strength": scope}
            old = found.get(r["city_id"])
            if old is None or (distance, -scope) < (old["edit_distance"], -old["geography_strength"]):
                found[r["city_id"]] = suggestion
        options = sorted(found.values(), key=lambda x: (x["edit_distance"], -x["geography_strength"],
                                                         -x["similarity"], x["city"].casefold(),
                                                         x["state"].casefold()))
        if not options:
            if state and not self.connection.execute(
                "SELECT 1 FROM region_names WHERE region_norm=? LIMIT 1", (st,)
            ).fetchone() and st not in GB_LABELS:
                reason = "State/province/country does not match the master"
            else:
                reason = "No sufficiently similar populated-place names in compatible geography"
            return self._no_match(city, state, reason)
        winner = options[0]
        # A close challenger blocks automatic correction.
        challenger = next((x for x in options[1:] if normalize(x["city"]) != normalize(winner["city"])
                           and x["edit_distance"] <= winner["edit_distance"] + 1), None)
        strict_province = state.upper() in (US_STATES | CA_PROVS)
        auto = bool(state and winner["geography_strength"] >= 3
                    and winner["edit_distance"] == 1 and challenger is None
                    and ((strict_province and len(target) >= 6) or
                         (len(target) >= 8 and winner["similarity"] >= .875)))
        if (state and winner["geography_strength"] >= 3 and winner["edit_distance"] == 2
                and challenger is None and len(target) >= 11 and winner["similarity"] >= .88):
            auto = True
        guard = self.connection.execute(
            "SELECT reason FROM fuzzy_review_guards WHERE city_norm=? AND region_norm=?",
            (target, st),
        ).fetchone()
        if guard:
            auto = False
        reason = ("Unambiguous close spelling in requested location" if auto else
                  "Known geographic or spelling conflict: " + guard[0] if guard else
                  "Fuzzy suggestions require confirmation")
        result = {"status": "FUZZY_HIGH" if auto else "REVIEW", "input_city": city,
                  "input_state": state, "canonical_city": winner["city"] if auto else "",
                  "canonical_state": winner["state"] if auto else "",
                  "confidence": "HIGH" if auto else "REVIEW", "reason": reason,
                  "suggestions": options[:limit]}
        return result


def match_city(db_path: str | Path, city: str, state: str = "", limit: int = 5) -> dict:
    """One-shot API; for multiple shows prefer a shared CityMatcher instance."""
    with CityMatcher(db_path) as matcher:
        return matcher.resolve(city, state, limit)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", "--master", dest="db", type=Path,
                    help="Path to cities.sqlite (the old --master flag remains an alias for the DB path)")
    ap.add_argument("--TLOHome", help="Active data folder (otherwise use TLOHome environment)")
    ap.add_argument("--city", required=True)
    ap.add_argument("--state", default="", help="US state, Canadian province, or country/region label")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    args = ap.parse_args()
    db = args.db
    if db is None:
        from tlo_path_inputs import resolve_tlo_home
        db = Path(resolve_tlo_home(args.TLOHome or "", app_name="match_city")) / "TLO_DBs" / "cities.sqlite"
    with CityMatcher(db) as matcher:
        result = matcher.resolve(args.city, args.state, args.limit)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Status:", result["status"])
        if result.get("canonical_city"):
            print("Master:", result["canonical_city"] + " ^ " + result["canonical_state"])
        print(result["reason"])
        for r in result.get("suggestions", []):
            print("  ", r["city"], r["state"], "distance", r.get("edit_distance", ""))
    return 0 if result["status"] in {"EXACT", "ALIAS", "FUZZY_HIGH"} else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (sqlite3.Error, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
