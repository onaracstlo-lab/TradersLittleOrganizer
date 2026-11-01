"""Per-TLOHome startup preferences for TLO Main, Search, and child windows."""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import configparser
import os
from pathlib import Path
import re
import tempfile
import tkinter as tk
from tkinter import messagebox, ttk

from tlo_options import GUI_CHECKBOX_OPTIONS

FILENAME = 'tlo-preferences.ini'
MAX_BYTES = 128 * 1024

_BOOLEAN_DEFAULTS = {option.config_field: bool(option.default) for option in GUI_CHECKBOX_OPTIONS}
DEFAULTS = {
    'general': {'auto_update': False},
    'main': {
        **_BOOLEAN_DEFAULTS,
        'dry_run': False,
        'performance_mode': 'balanced',
        'max_workers': 0,
        'corrupt_files': 'delete',
        'corrupt_folders': 'all',
        'corrupt_folder_threshold': 100,
        'search_path': '',
        'font_family': 'system',
        'font_size': 0,
        'heading_font_size': 0,
        'fixed_font_size': 0,
    },
    'search': {
        'deep': False,
        'search_query': '',
        'font_family': 'system',
        'font_size': 0,
        'heading_font_size': 0,
        'fixed_font_size': 0,
    },
    'manual_updates': {'update_tags': True},
    'add_new_shows': {'check_for_duplicates': True},
}

BOOL_KEYS = {('main', field) for field in _BOOLEAN_DEFAULTS} | {
    ('general', 'auto_update'), ('main', 'dry_run'), ('search', 'deep'),
    ('manual_updates', 'update_tags'), ('add_new_shows', 'check_for_duplicates'),
}
FONT_SIZES = {('main', field) for field in ('font_size', 'heading_font_size', 'fixed_font_size')} | {
    ('search', field) for field in ('font_size', 'heading_font_size', 'fixed_font_size')
}


def default_text(*, auto_update=False):
    """Human-readable, version-independent template retaining existing startup defaults."""
    comments = {
        'general': 'Auto Update is shared by Main and Search; changing it in a menu also updates this file.',
        'main': 'Main window: max_workers=0 selects the current Performance Mode ceiling.\n# font_size=0 uses the existing Tk default + 2 points.',
        'search': 'Search: empty search_query keeps clipboard startup; 0 font sizes keep Tk defaults.',
        'manual_updates': 'Manual Tweaks window.',
        'add_new_shows': 'Add New Shows window.',
    }
    lines = [
        '# Traders Little Organizer startup preferences',
        '# Edit through hamburger > Edit Preferences. Save changes, then restart TLO.',
        '# Unavailable font families fall back to the desktop default.',
        '# Do not change the file while a TLO preferences editor is open.',
        '',
    ]
    for section, entries in DEFAULTS.items():
        lines.extend(('# ' + comments[section], f'[{section}]'))
        for name, value in entries.items():
            if section == 'general' and name == 'auto_update':
                value = bool(auto_update)
            if isinstance(value, bool):
                value = str(value).lower()
            lines.append(f'{name} = {value}')
        lines.append('')
    return '\n'.join(lines)


def parse_text(text):
    """Validate every preference, with safe defaults for absent keys/sections."""
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    try:
        parser.read_string(text)
    except configparser.Error as exc:
        raise ValueError(f'Invalid preferences syntax: {exc}') from exc
    unexpected_sections = set(parser.sections()) - set(DEFAULTS)
    if unexpected_sections:
        raise ValueError(f'Unknown preferences section: {sorted(unexpected_sections)[0]}')
    result = {section: dict(entries) for section, entries in DEFAULTS.items()}
    for section in parser.sections():
        for key, raw in parser.items(section):
            if key not in DEFAULTS[section]:
                raise ValueError(f'Unknown preference: [{section}] {key}')
            value = raw.strip()
            try:
                if (section, key) in BOOL_KEYS:
                    value = parser.getboolean(section, key)
                elif (section, key) in FONT_SIZES:
                    value = int(value)
                    if value != 0 and not 7 <= value <= 40:
                        raise ValueError('must be 0 or between 7 and 40')
                elif (section, key) == ('main', 'max_workers'):
                    value = int(value)
                    if value < 0 or value > 256:
                        raise ValueError('must be 0 through 256')
                elif (section, key) == ('main', 'corrupt_folder_threshold'):
                    value = int(value)
                    if not 0 <= value <= 100:
                        raise ValueError('must be 0 through 100')
                elif (section, key) == ('main', 'performance_mode'):
                    if value not in ('gentle', 'balanced', 'fast', 'extreme'):
                        raise ValueError('choose gentle, balanced, fast, or extreme')
                elif (section, key) == ('main', 'corrupt_files'):
                    if value not in ('keep', 'delete'):
                        raise ValueError('choose keep or delete')
                elif (section, key) == ('main', 'corrupt_folders'):
                    if value not in ('never', 'all', 'threshold'):
                        raise ValueError('choose never, all, or threshold')
                elif key == 'font_family':
                    if not value or len(value) > 100 or any(ord(char) < 32 for char in value):
                        raise ValueError('must name a font or use system')
                elif key in ('search_path', 'search_query') and len(value) > 4096:
                    raise ValueError('entry is too long')
            except (ValueError, configparser.Error) as exc:
                raise ValueError(f'Invalid [{section}] {key}: {exc}') from exc
            result[section][key] = value
    main = result['main']
    if main['compliant'] and main['rename_compliantly']:
        raise ValueError('[main] compliant and rename_compliantly cannot both be true')
    tag_modes = ('tag_during_inventory', 'tag_copy_during_inventory', 'tag_copy_and_delete_enabled')
    if sum(bool(main[field]) for field in tag_modes) > 1:
        raise ValueError('[main] select no more than one tagging mode')
    if main['setlistfm_lookup'] and not main['etree_lookup']:
        raise ValueError('[main] setlistfm_lookup requires etree_lookup')
    if main['setlistfm_upgrade'] and not main['setlistfm_lookup']:
        raise ValueError('[main] setlistfm_upgrade requires setlistfm_lookup')
    if main['delete_extra_tags'] and not any(main[field] for field in tag_modes):
        raise ValueError('[main] delete_extra_tags requires a tagging mode')
    return result


def path_for(tlo_home):
    return Path(tlo_home) / FILENAME


def load(tlo_home, *, initial_auto_update=False):
    """Create on first launch, never overwrite an existing preference file."""
    file_path = path_for(tlo_home)
    if not file_path.parent.is_dir():
        raise FileNotFoundError(f'TLOHome does not exist: {file_path.parent}')
    if not file_path.exists():
        try:
            with file_path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(default_text(auto_update=initial_auto_update))
        except FileExistsError:
            pass
    if file_path.stat().st_size > MAX_BYTES:
        raise ValueError('Preferences file exceeds 128 KB')
    return parse_text(file_path.read_text(encoding='utf-8-sig'))


def save_text(tlo_home, new_text):
    """Validate then atomically replace; invalid edits never damage the saved file."""
    if len(new_text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Preferences file exceeds 128 KB')
    validated = parse_text(new_text)
    path = path_for(tlo_home)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Preferences file is missing or is a symbolic link')
    fd, temp_path = tempfile.mkstemp(prefix='.tlo-preferences-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(new_text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, path.stat().st_mode & 0o777)
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return validated


def set_auto_update(tlo_home, enabled):
    """Keep the shared Auto Update checkbox and editable defaults consistent."""
    path = path_for(tlo_home)
    original = path.read_text(encoding='utf-8-sig')
    matcher = re.compile(r'(?im)^(\s*auto_update\s*=\s*)(true|false|yes|no|on|off|0|1)(\s*)$')
    matches = list(matcher.finditer(original))
    if len(matches) != 1:
        raise ValueError('Preferences must contain exactly one [general] auto_update entry')
    updated = original[:matches[0].start(2)] + str(bool(enabled)).lower() + original[matches[0].end(2):]
    save_text(tlo_home, updated)


def edit(root, tlo_home):
    """Editable built-in text window; no external editor or file association needed."""
    path = path_for(tlo_home)
    original = path.read_text(encoding='utf-8-sig')
    window = tk.Toplevel(root)
    window.title('TLO Edit Preferences')
    window.transient(root)
    window.geometry('850x680')
    window.columnconfigure(0, weight=1)
    window.rowconfigure(1, weight=1)
    ttk.Label(window, text=f'{path}\nSave your changes, then restart TLO Main and Search to apply startup defaults.',
              padding=10).grid(row=0, column=0, sticky='w')
    container = ttk.Frame(window)
    container.grid(row=1, column=0, sticky='nsew', padx=10)
    container.rowconfigure(0, weight=1)
    container.columnconfigure(0, weight=1)
    editor = tk.Text(container, wrap='none', undo=True, font='TkFixedFont')
    scrollbar_y = ttk.Scrollbar(container, orient='vertical', command=editor.yview)
    scrollbar_x = ttk.Scrollbar(container, orient='horizontal', command=editor.xview)
    editor.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
    editor.grid(row=0, column=0, sticky='nsew')
    scrollbar_y.grid(row=0, column=1, sticky='ns')
    scrollbar_x.grid(row=1, column=0, sticky='ew')
    editor.insert('1.0', original)
    editor.edit_modified(False)

    def close():
        if editor.get('1.0', 'end-1c') != original:
            if not messagebox.askyesno('Unsaved preferences', 'Discard unsaved preferences changes?', parent=window):
                return
        window.destroy()

    def save():
        nonlocal original
        updated = editor.get('1.0', 'end-1c')
        if updated == original:
            return
        try:
            save_text(tlo_home, updated)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Invalid preferences', str(exc), parent=window)
            return
        original = updated
        editor.edit_modified(False)
        messagebox.showinfo('Restart required', 'Preferences saved. Restart TLO Main and TLO Search for the new startup defaults to take effect.', parent=window)

    buttons = ttk.Frame(window, padding=10)
    buttons.grid(row=2, column=0, sticky='e')
    ttk.Button(buttons, text='Save', command=save).pack(side='left', padx=5)
    ttk.Button(buttons, text='Close', command=close).pack(side='left', padx=5)
    window.protocol('WM_DELETE_WINDOW', close)
    return window
