"""Build 716: local build lock verifier must never contaminate the source tree."""
from pathlib import Path
import os
import shutil
import subprocess
import sys

import pytest

pytestmark = pytest.mark.contract
ROOT = Path(__file__).resolve().parents[2]


def _cache_neutral_environment():
    env = os.environ.copy()
    env.pop("PYTHONDONTWRITEBYTECODE", None)
    env.pop("PYTHONPYCACHEPREFIX", None)
    return env


def _prepare_source(tmp_path: Path) -> Path:
    for name in ('verify_build_lock.py', 'tlo_version.py', 'requirements-build.txt'):
        shutil.copyfile(ROOT / name, tmp_path / name)
    return tmp_path


def test_plain_python_direct_invocation_does_not_create_pyc(tmp_path):
    source = _prepare_source(tmp_path)
    result = subprocess.run([sys.executable, str(source / 'verify_build_lock.py'),
                             str(source / 'requirements-build.txt')],
                            cwd=source, env=_cache_neutral_environment(), capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert list(source.rglob('*.pyc')) == []
    assert not (source / '__pycache__').exists()


def test_python_no_bytecode_flag_prevents_snapshot_pyc(tmp_path):
    source = _prepare_source(tmp_path)
    result = subprocess.run([sys.executable, '-B', str(source / 'verify_build_lock.py'),
                             str(source / 'requirements-build.txt')],
                            cwd=source, env=_cache_neutral_environment(), capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert list(source.rglob('*.pyc')) == []


def test_bad_pinned_hash_is_rejected_without_bytecode(tmp_path):
    source = _prepare_source(tmp_path)
    lock = source / 'requirements-build.txt'
    lock.write_text(lock.read_text().replace('2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377137d9',
                                             '2363c69b61c4a97c838da3b130dcd6468f4848992b21a82f2a63ec34377147d9'))
    result = subprocess.run([sys.executable, str(source / 'verify_build_lock.py'), str(lock)],
                            cwd=source, env=_cache_neutral_environment(), capture_output=True, text=True, check=False)
    assert result.returncode != 0
    assert 'pin mismatch' in result.stdout
    assert list(source.rglob('*.pyc')) == []


def test_unprotected_import_reproduces_original_cache_defect(tmp_path):
    (tmp_path / 'tlo_version.py').write_text('VERSION="v716"\n')
    (tmp_path / 'old_preflight.py').write_text('from tlo_version import VERSION\nprint(VERSION)\n')
    result = subprocess.run([sys.executable, str(tmp_path / 'old_preflight.py')], cwd=tmp_path,
                            env=_cache_neutral_environment(), capture_output=True, text=True, check=False)
    assert result.returncode == 0
    assert list(tmp_path.rglob('tlo_version.*.pyc')), 'This test must reproduce the Build 715 defect'
