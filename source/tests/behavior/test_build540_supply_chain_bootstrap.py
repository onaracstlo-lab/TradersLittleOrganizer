from tests import _release_artifacts as RA
from pathlib import Path
import re
import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _requirements_entries(text: str):
    logical=[]
    current=''
    for raw in text.splitlines():
        line=raw.strip()
        if not line or line.startswith('#'):
            continue
        current += (' ' if current else '') + line.rstrip('\\').strip()
        if not line.endswith('\\'):
            logical.append(current)
            current=''
    assert not current
    return logical


def test_build540_version_and_audit_lock_contract():
    lock=(ROOT/'requirements-audit.txt').read_text(encoding='utf-8')
    entries=_requirements_entries(lock)
    assert len(entries) >= 20
    names=set()
    for entry in entries:
        pin=entry.split()[0]
        assert '==' in pin and not pin.startswith(('-', '.', '/', 'git+'))
        name=pin.split('==',1)[0].lower()
        names.add(name)
        assert re.search(r'--hash=sha256:[0-9a-f]{64}', entry)
    assert {'pip-audit','pip-api','cachecontrol','msgpack','charset-normalizer'} <= names
    msgpack=next(e for e in entries if e.startswith('msgpack=='))
    charset=next(e for e in entries if e.startswith('charset-normalizer=='))
    assert msgpack.count('--hash=sha256:') >= 4
    assert charset.count('--hash=sha256:') >= 3


def test_build540_audit_helper_is_fail_closed_and_does_not_delegate_resolution():
    text=(ROOT/'audit_build_requirements.py').read_text(encoding='utf-8')
    assert 'EXPECTED_BOOTSTRAP_PIP_VERSION = "26.2.1"' in text
    assert 'AUDIT_REQUIREMENTS = Path(__file__).with_name("requirements-audit.txt")' in text
    for token in ('"--no-deps"','"--require-hashes"','"--only-binary=:all:"','"pip", "--isolated", "check"','"--disable-pip"'):
        assert token in text
    assert '_installed_version(python, "pip-audit"' in text
    assert 'PIP_AUDIT_VERSION = "2.10.1"' in text
    assert 'pip-audit==' not in text


def test_build540_current_documents_record_process_v108_without_runtime_change():
    assert (ROOT/RA.REQUIREMENTS_FILENAME).is_file()
    assert (ROOT/RA.MANUAL_FILENAME).is_file()
    changes=(ROOT/RA.CHANGES_FILENAME).read_text(encoding='utf-8')
    assert 'Build 540' in changes and 'GitHub Build Process v108' in changes
    assert 'Application runtime behavior is unchanged' in changes
    assert 'requirements-audit.txt' in changes
