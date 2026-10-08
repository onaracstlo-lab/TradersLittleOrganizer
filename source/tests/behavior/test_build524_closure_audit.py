"""Build 524 closure-audit regressions.

Build 524 changes no TLO runtime behavior. It closes the remaining T-02
working-directory dependency found by the independent Build 524 audit.
"""

from __future__ import annotations


import os
from pathlib import Path
import subprocess
import sys

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_build524_remediated_tests_run_from_outside_bundle_root(tmp_path):
    """The tests implicated by T-02 must not depend on process CWD."""
    rels = [
        "tests/behavior/test_build485_copy_requests.py",
        "tests/behavior/test_build486_copy_requests_hamburger.py",
        "tests/behavior/test_build487_redundancy_groups.py",
        "tests/behavior/test_build488_redundancy_close_label.py",
        "tests/behavior/test_build503_copy_request_direct_paths_volumes.py",
        "tests/behavior/test_build511_copy_request_paths_input.py",
        "tests/behavior/test_build512_main_gui_workers_copy_wildcards.py",
    ]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *[str(ROOT / rel) for rel in rels]],
        cwd=tmp_path,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=90,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert "48 passed" in completed.stdout


def test_build524_no_known_current_root_test_paths_are_cwd_relative():
    """Guard the concrete relative-path patterns exposed by the closure audit."""
    bad_patterns = (
        'Path("tlo-main.py")',
        "Path('tlo-main.py')",
        'Document(RA.REQUIREMENTS_FILENAME)',
        'Path(RA.MANUAL_FILENAME)',
        'Path("TLO-FAQ.txt")',
        "Path('TLO-FAQ.txt')",
    )
    offenders = []
    for path in (ROOT / "tests").rglob("*.py"):
        if path == Path(__file__):
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in bad_patterns:
            if pattern in text:
                offenders.append(f"{path.relative_to(ROOT)}: {pattern}")
    assert not offenders, "\n".join(offenders)
