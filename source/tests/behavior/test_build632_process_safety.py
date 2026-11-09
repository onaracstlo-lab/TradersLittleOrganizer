import pytest
"""Build 632: absolute ps, cross-process settings and current User-Agent."""
import os
import subprocess
import sys
from pathlib import Path
import tlo_run_settings as R
import tlo_etree_lookup as E
import tlo_version as V


def test_run_settings_os_lock(tmp_path):
    R.append_run_settings(str(tmp_path), 'first', ['one'])
    log = Path(R.run_settings_log_path(str(tmp_path)))
    assert log.exists() and Path(str(log) + '.lock').exists()


def test_run_settings_two_processes_atomic(tmp_path):
    script = "from tlo_run_settings import append_run_settings\nimport sys\nfor i in range(12):\n append_run_settings(sys.argv[1], sys.argv[2], [sys.argv[2] + ':' + str(i)] * 10)\n"
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(Path(__file__).resolve().parents[2]))
    a = subprocess.Popen([sys.executable, '-c', script, str(tmp_path), 'A'], env=env)
    b = subprocess.Popen([sys.executable, '-c', script, str(tmp_path), 'B'], env=env)
    assert a.wait(timeout=20) == b.wait(timeout=20) == 0
    contents = Path(R.run_settings_log_path(str(tmp_path))).read_text()
    assert contents.count('Action: A') == contents.count('Action: B') == 12
    for entry in contents.strip().split('\n\n'):
        lines = entry.splitlines()
        label = lines[0].split('Action: ')[1][0]
        assert len(lines) == 11
        assert all(line.startswith(label + ':') for line in lines[1:])


def test_etree_user_agent_tracks_version():
    assert 'DISPLAY_VERSION' in Path(E.__file__).read_text()
    assert V.DISPLAY_VERSION.startswith('v1.7 Build ')


def test_copy_request_ps_absolute():
    source = (Path(__file__).resolve().parents[2] / 'tlo_copy_requests.py').read_text()
    assert '["/bin/ps", "-o", "lstart=", "-p", str(pid)]' in source
    assert '["ps", "-o", "lstart=", "-p", str(pid)]' not in source


pytestmark = pytest.mark.behavior
