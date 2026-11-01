"""Build 600: source Windows icon preflight and PyInstaller runtime-data wiring."""
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_source_windows_icons_fail_closed_and_wired_to_onefile_executables():
    windows = (ROOT / 'createWindowsDist.ps1').read_text(encoding='utf-8')
    for app in ('main', 'search'):
        assert (ROOT / 'icons' / f'tlo-{app}-icon.png').is_file()
        assert (ROOT / 'icons' / f'tlo-{app}-icon.ico').is_file()
    assert "$MainIconPng = Join-Path $IconRoot 'tlo-main-icon.png'" in windows
    assert "$SearchIconPng = Join-Path $IconRoot 'tlo-search-icon.png'" in windows
    assert 'foreach ($RequiredIcon in @($MainIcon, $SearchIcon, $TagIcon, $MainIconPng, $SearchIconPng))' in windows
    assert "'--add-data', ($MainIconPng + ';icons')" in windows
    assert "'--add-data', ($MainIcon + ';icons')" in windows
    assert "'--add-data', ($SearchIconPng + ';icons')" in windows
    assert "'--add-data', ($SearchIcon + ';icons')" in windows
    assert '$SearchArgs = @(\'--windowed\', "--icon=$SearchIcon") + $SearchRuntimeIcons' in windows
    assert '$GuiArgs = @(\'--windowed\', \'--collect-all\', \'mutagen\', \'--add-binary\', $FfmpegAddBinary, \'--collect-all\', \'tkinterdnd2\', "--icon=$MainIcon") + $MainRuntimeIcons' in windows
