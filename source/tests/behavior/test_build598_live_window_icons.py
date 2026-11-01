"""Build 598: Tk window/task-switcher icon matches the TLO executable artwork."""

from pathlib import Path
import sys
import tkinter as tk

import pytest

import tlo_window_icons as icons

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_main_and_search_frozen_packaging_include_correct_runtime_icons():
    windows = (ROOT / 'createWindowsDist.ps1').read_text(encoding='utf-8')
    linux = (ROOT / 'createLinuxDist.sh').read_text(encoding='utf-8')
    mac = (ROOT / 'createMacOSDist.sh').read_text(encoding='utf-8')
    for app in ('main', 'search'):
        stem = f'tlo-{app}-icon'
        assert (ROOT / 'icons' / (stem + '.png')).is_file()
        assert (ROOT / 'icons' / (stem + '.ico')).is_file()
        assert (ROOT / 'icons' / (stem + '.icns')).is_file()
        assert stem + '.png' in windows
        assert stem + '.ico' in windows
        assert f'icons/{stem}.png:icons' in linux
        assert f'icons/{stem}.png:icons' in mac
    assert '$GuiArgs' in windows and '$MainRuntimeIcons' in windows
    assert '$SearchArgs' in windows and '$SearchRuntimeIcons' in windows


def test_boot_paths_load_icons_before_creating_dialogs():
    main = (ROOT / 'tlo-main.py').read_text(encoding='utf-8')
    search = (ROOT / 'tlo-search.py').read_text(encoding='utf-8')
    assert 'install_window_icon(root, "main")' in main
    assert search.count('install_window_icon(root, "search")') == 2
    assert main.index('install_window_icon(root, "main")') < main.index('    app = App(root, cli_args=cli_args)')
    assert search.index('install_window_icon(root, "search")') < search.index('    BootlistSearchApp(root, paths, initial_find)')


def test_frozen_icon_lookup_uses_meipass_without_trusting_cwd(tmp_path, monkeypatch):
    bundle = tmp_path / 'bundle'
    (bundle / 'icons').mkdir(parents=True)
    (bundle / 'icons' / 'tlo-main-icon.png').write_bytes(b'icon contents')
    monkeypatch.setattr(sys, '_MEIPASS', str(bundle), raising=False)
    monkeypatch.chdir(tmp_path)
    assert icons._icon_file('tlo-main-icon', 'png') == bundle / 'icons' / 'tlo-main-icon.png'
    assert icons._icon_file('tlo-search-icon', 'png') is None


def test_windows_iconbitmap_uses_tlo_ico_and_fallback_keeps_gui_alive(monkeypatch):
    class FakeWindow:
        def __init__(self):
            self.calls = []

        def iconphoto(self, default, photo):
            self.calls.append(('iconphoto', default, photo))

        def iconbitmap(self, filename):
            self.calls.append(('iconbitmap', filename))

    fake = FakeWindow()
    monkeypatch.setattr(icons.sys, 'platform', 'win32')
    monkeypatch.setattr(icons.tk, 'PhotoImage', lambda master, file: ('png', file))
    assert icons.install_window_icon(fake, 'main')
    assert fake.calls[0][0:2] == ('iconphoto', True)
    assert fake.calls[0][2][1].endswith('tlo-main-icon.png')
    assert fake.calls[1][0] == 'iconbitmap'
    assert fake.calls[1][1].endswith('tlo-main-icon.ico')
    assert fake._tlo_window_icon_photo == fake.calls[0][2]

    class Failing(FakeWindow):
        def iconphoto(self, *_args):
            raise tk.TclError('missing image support')

        def iconbitmap(self, *_args):
            raise tk.TclError('cannot decode icon')

    assert not icons.install_window_icon(Failing(), 'search')


@pytest.mark.gui
def test_tk_live_icon_installs_and_child_window_inherits_default():
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f'No graphical display: {exc}')
    try:
        assert icons.install_window_icon(root, 'main')
        assert root._tlo_window_icon_photo.width() > 0
        assert root._tlo_window_icon_photo.height() > 0
        popup = tk.Toplevel(root)
        popup.update_idletasks()
        assert popup.winfo_exists()
        popup.destroy()
    finally:
        root.destroy()
