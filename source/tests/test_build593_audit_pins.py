import pytest
pytestmark = pytest.mark.contract
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def test_affected_audit_tool_pins_have_expected_hashes():
    lock = (ROOT / 'requirements-audit.txt').read_text(encoding='utf-8')
    expected = {
      'certifi==2026.10.18': '73191c47aaa79da394e8fee2dbc2ec827432cab56311122c9e47abf79e390f62',
      'filelock==4.2.1': '7be2662e9e826b9bba28afc0f843a123280d799a2ea44bb5d35ccec67905ae44',
      'msgpack==1.2.3': 'bb89b5dc30469c84bbf8684826eb851d82412ca95690e111b9ac5e8fb343961a',
    }
    for pin, digest in expected.items():
      assert pin in lock and digest in lock
    for old in ('certifi==2026.6.17', 'filelock==3.29.5', 'msgpack==1.2.1'):
      assert old not in lock
    for digest in ('07c9733089d1b176c3dd2f7fa268452f9d5d784d076473499d754a58e8d1fbbb', 'db84203b13aecc222f465061397fdd5b53b7ae73d2c95ffc1c8dc5be0153a709'):
      assert digest in lock
