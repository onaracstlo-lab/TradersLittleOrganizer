#!/usr/bin/env python3
"""Mandatory source verification: refuse to issue a release without Ruff and pytest.

Run with a clean vN source tree and the pinned dependency environment. This
script reports actual subprocess exit statuses; no success report is fabricated.
"""
from __future__ import annotations
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    # City master must be a real TLO_DBs file, never an embedded Python copy.
    try:
        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        from tools.stage_city_database import validate
        if (ROOT / 'tlo_cities_embedded.py').exists():
            raise ValueError('embedded city reference present')
        validate(ROOT / 'TLO_DBs' / 'cities.sqlite')
    except (OSError, ValueError) as exc:
        print(f'BLOCKED: physical TLO_DBs/cities.sqlite invalid: {exc}', file=sys.stderr)
        return 1
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["TLO_RELEASE_VERIFY"] = "1"
    commands = (
        [sys.executable, "-m", "ruff", "check", "."],
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
    )
    for command in commands:
        print("RELEASE GATE:", " ".join(command), flush=True)
        completed = subprocess.run(command, cwd=ROOT, env=env, check=False)
        if completed.returncode:
            print(f"BLOCKED: command exited {completed.returncode}", file=sys.stderr)
            return 1
    from docx import Document
    # Invoked as `python tools/verify_release_gates.py` (and from a clean
    # source ZIP); Python adds tools/, not the source root, to sys.path.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tlo_version import DISPLAY_VERSION, VERSION
    requirement = ROOT / f"TLO_Inventory_Requirements_Working_{VERSION}.docx"
    properties = Document(requirement).core_properties
    if properties.title != f"TLO Inventory Requirements - {DISPLAY_VERSION}" or properties.subject != f"Current testable technical and functional requirements, TLO {DISPLAY_VERSION}":
        print("BLOCKED: requirements document title/subject metadata mismatch", file=sys.stderr)
        return 1
    # These are local SOURCE gates only. Native Windows signing and hosted
    # packaging must still pass independently before any promotion.
    print("RELEASE SOURCE CHECKS PASSED (native signing NOT ATTESTED)", flush=True)
    return 0

if __name__ == '__main__':
    sys.exit(main())
