"""Build 670: artist/date collisions and trusted MSI update helpers."""
from __future__ import annotations
import hashlib
import ntpath
import subprocess
from pathlib import Path
import sys

import pytest
from tlo_artist_db import ArtistMatcher
import tlo_phase23_v2 as phase
import tlo_msi_install_mode as install

pytestmark = pytest.mark.behavior


def _matcher():
    names = ('Bruno Mars', '30 Seconds to Mars', 'Brian May', 'Juli', 'Ott', 'Gen')
    matcher = ArtistMatcher(db_path='fixture')
    matcher.exact_map = {name.casefold(): {name} for name in names}
    matcher.master_aliases = {name: [name] for name in names}
    return matcher


@pytest.mark.parametrize('folder', [
    'Bruno Mars 2013 Moonshine Jungle Tour',
    '30 Seconds to Mars 2007 Bootleg',
    'Brian May 1993 Back to the Light',
    'Juli 2005 Hamburg', 'Ott 2009 Glastonbury', 'Gen 2004 Tokyo',
])
def test_artist_alias_month_year_not_interpreted_as_date(folder):
    matcher = _matcher()
    assert phase._find_date_matches(folder, artist_matcher=matcher) == []
    assert not phase._compliant_string_date_matches(folder, allow_string2=True, artist_matcher=matcher)
    group = {'main_dir_path': str(Path('/shows') / folder), 'main_dir_name': folder}
    assert not any(row['date_norm'].endswith('-xx') for row in sum(phase._collect_pattern_matches_for_group(group, matcher), []))
    assert not any(row['normalized'].endswith('-xx') for row in phase._collect_path_date_matches(group, matcher))


@pytest.mark.parametrize('text,expected', [
    ('Bruno Mars 2013-03-22 London', '2013-03-22'),
    ('30 Seconds to Mars 2007-05-02 Paris', '2007-05-02'),
    ('01. Juni 2022', '2022-06-01'),
    ('1er juin 2022', '2022-06-01'),
    ('1° maggio 2022', '2022-05-01'),
    ('Kinks Mai 1993', '1993-05-xx'),
])
def test_real_dates_remain_recognized(text, expected):
    assert expected in {row['normalized'] for row in phase._find_date_matches(text, artist_matcher=_matcher())}


def test_system32_helper_never_uses_path(monkeypatch):
    import tlo_security
    monkeypatch.setattr(tlo_security, 'windows_directory_from_api', lambda: r'C:\Windows')
    assert install._trusted_system32_executable('msiexec.exe') == ntpath.join(r'C:\Windows', 'System32', 'msiexec.exe')
    with pytest.raises(ValueError):
        install._trusted_system32_executable('anything.exe')


def test_portable_msi_uses_trusted_installer(monkeypatch, tmp_path):
    import tlo_security
    msi = tmp_path/'test.msi'
    msi.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1') + b'example stub')
    digest = hashlib.sha256(msi.read_bytes()).hexdigest()
    calls = []
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(tlo_security, 'windows_directory_from_api', lambda: r'C:\Windows')
    monkeypatch.setattr(subprocess, 'Popen', lambda args, **kw: calls.append(args))
    assert install.launch_verified_portable_msi_install(msi, digest)
    assert calls[0][0] == ntpath.join(r'C:\Windows', 'System32', 'msiexec.exe')
