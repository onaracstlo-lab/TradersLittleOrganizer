"""Build 662: MSI license dialog shows the public repo's GNU GPL v3."""
from pathlib import Path
import importlib.util
import xml.etree.ElementTree as ET
import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('tlo_wix_gpl_662', ROOT / 'msi' / 'generate_wix.py')
WIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WIX)


def test_full_gpl_v3_source_and_plain_msi_rtf():
    license_text = (ROOT / 'LICENSE').read_text(encoding='utf-8')
    rtf = (ROOT / 'msi' / 'TLO-GPLv3.rtf').read_text(encoding='ascii')
    for required in (
        'GNU GENERAL PUBLIC LICENSE', 'Version 3, 29 June 2007',
        'TERMS AND CONDITIONS', 'END OF TERMS AND CONDITIONS',
        'How to Apply These Terms to Your New Programs',
    ):
        assert required.casefold() in license_text.casefold()
        assert required.casefold() in rtf.casefold()
    assert license_text.count('Copyright (C) 2007 Free Software Foundation') == 1
    assert len(license_text) > 30000
    assert rtf.startswith(r'{\rtf1\ansi')
    assert rtf.rstrip().endswith('}')
    assert 'Lorem ipsum' not in rtf
    # The actual RTF includes all text (except RTF syntax escaping).
    assert rtf.count(r'\par') >= license_text.count('\n')


def test_wix_license_reference_is_real_rtf_file(tmp_path):
    stage = tmp_path / 'signed'
    stage.mkdir()
    (stage / 'tlo-main.exe').write_bytes(b'fake')
    wxs = tmp_path / 'generated.wxs'
    WIX.generate(stage, wxs, '1.7.662')
    root = ET.parse(wxs).getroot()
    ns = {'w': WIX.NS, 'ui': WIX.UI_NS}
    license_vars = root.findall('.//w:WixVariable[@Id="WixUILicenseRtf"]', ns)
    assert len(license_vars) == 1
    value = license_vars[0].attrib['Value']
    assert Path(value).resolve() == (ROOT / 'msi' / 'TLO-GPLv3.rtf').resolve()
    assert Path(value).is_file()
    assert root.find('.//ui:WixUI[@Id="WixUI_InstallDir"]', ns) is not None


def test_missing_license_must_fail_closed(tmp_path, monkeypatch):
    fake_module = tmp_path / 'msi' / 'generate_wix.py'
    fake_module.parent.mkdir()
    stage = tmp_path / 'stage'
    stage.mkdir()
    (stage / 'tlo-main.exe').write_bytes(b'fake')
    monkeypatch.setattr(WIX, '__file__', str(fake_module))
    with pytest.raises(FileNotFoundError, match='Missing GNU GPL v3 MSI license'):
        WIX.generate(stage, tmp_path / 'out.wxs', '1.7.662')
