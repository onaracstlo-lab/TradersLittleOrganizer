"""Per-TLOHome startup preferences for TLO Main, Search, and child windows."""

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import os
import hashlib
from pathlib import Path
import re
import tempfile

from tlo_options import GUI_CHECKBOX_OPTIONS

FILENAME = 'tlo-preferences.ini'
MAX_BYTES = 128 * 1024
_EDIT_WINDOWS = {}

_BOOLEAN_DEFAULTS = {option.config_field: bool(option.default) for option in GUI_CHECKBOX_OPTIONS}
DEFAULTS = {
    'general': {'auto_update': False},
    'main': {
        **_BOOLEAN_DEFAULTS,
        'dry_run': False,
        'performance_mode': 'balanced',
        'max_workers': 0,
        'corrupt_files': 'keep',
        'corrupt_folders': 'never',
        'corrupt_folder_threshold': 100,
        'search_path': '',
        'font_family': 'system',
        'font_size': 0,
        'heading_font_size': 0,
        'fixed_font_size': 0,
    },
    'search': {
        'deep': False,
        'clipboard_prefill': False,
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
    ('general', 'auto_update'), ('main', 'dry_run'), ('search', 'deep'), ('search', 'clipboard_prefill'),
    ('manual_updates', 'update_tags'), ('add_new_shows', 'check_for_duplicates'),
}
FONT_SIZES = {('main', field) for field in ('font_size', 'heading_font_size', 'fixed_font_size')} | {
    ('search', field) for field in ('font_size', 'heading_font_size', 'fixed_font_size')
}


# Lists mirror the Main GUI pull-downs. Use the INI keys, not the GUI labels.
CHOICES = {
    ('main', 'performance_mode'): ('gentle', 'balanced', 'fast', 'extreme'),
    ('main', 'corrupt_files'): ('keep', 'delete'),
    ('main', 'corrupt_folders'): ('never', 'all', 'threshold'),
}
BOOLEAN_WORDS = {
    'true': True, 'yes': True, 'on': True, '1': True,
    'false': False, 'no': False, 'off': False, '0': False,
}


def allowed_description(section, key):
    """An INI-side reference for all configurable fields, including pull-down choices."""
    if (section, key) in BOOL_KEYS:
        return 'true | false (also yes/no, on/off, 1/0)'
    if (section, key) in CHOICES:
        suffix = {
            'corrupt_files': ' (keep=Keep and report; delete=Delete corrupt files)',
            'corrupt_folders': ' (never=Never; all=100% corrupt only; threshold=At threshold)',
        }.get(key, '')
        return ' | '.join(CHOICES[section, key]) + suffix
    if (section, key) in FONT_SIZES:
        return '0 (platform default) or 7-40 points'
    if (section, key) == ('main', 'max_workers'):
        return '0 (automatic for Performance Mode) or 1-256'
    if (section, key) == ('main', 'corrupt_folder_threshold'):
        return '0-100 (%)'
    if key == 'font_family':
        return 'system (default) or an installed font family (case-insensitive)'
    if key == 'search_path':
        return 'a path or semicolon-separated paths; leave blank for default (case preserved)'
    if key == 'search_query':
        return 'any query up to 4096 characters; blank runs an empty search (case preserved)'
    raise KeyError((section, key))


# Exact compact layout approved for releases starting in Build 605.
# Keep this embedded copy synchronized with the distributed INI template.
_DEFAULT_TEMPLATE = """# Traders Little Organizer startup preferences
# Edit through hamburger > Edit Preferences. Restart TLO after saving.
# All section names, keys, choice values, and true/false words ignore case.
# Paths and free-text search queries retain their exact capitalization.
# Unavailable font families fall back to the desktop default.
# Do not change the file while a TLO preferences editor is open.

# all items that take true | false also take yes/no, on/off, and 1/0

# Auto Update is shared by Main and Search.
[general]
auto_update = false

# Main window; max_workers=0 uses the Performance Mode ceiling.
[main]
etree_lookup = false
compliant = false
tag_during_inventory = false
artist_in_album = true
setlistfm_lookup = false
rename_compliantly = false
tag_copy_during_inventory = false
convert_shn = false
setlistfm_upgrade = false
as_is_artist_name = false
tag_copy_and_delete_enabled = false
thorough_setlist_matching = false
proper_grammar = false
delete_extra_tags = false
deep_audio_check = false
dry_run = false
# performance_mode: gentle | balanced | fast | extreme
performance_mode = balanced
# max_workers: 0 (automatic for Performance Mode) or 1-256
max_workers = 0
# corrupt_files: keep | delete (keep=Keep and report; delete=Delete corrupt files)
corrupt_files = keep
# corrupt_folders: never | all | threshold (never=Never; all=100% corrupt only; threshold=At threshold)
corrupt_folders = never
# corrupt_folder_threshold: 0-100 (%)
corrupt_folder_threshold = 100
# search_path: a path or semicolon-separated paths; leave blank for default (case preserved)
search_path = 
# font_family: system (default) or an installed font family (case-insensitive)
font_family = system
# font_size: 0 (platform default) or 7-40 points
font_size = 0
# heading_font_size: 0 (platform default) or 7-40 points
heading_font_size = 0
# fixed_font_size: 0 (platform default) or 7-40 points
fixed_font_size = 0

# Search window; clipboard prefill defaults off for privacy.
[search]
deep = false
# Clipboard prefill is opt-in; --find and search_query take precedence.
clipboard_prefill = false
# search_query: any query up to 4096 characters; blank stays empty unless clipboard_prefill=true (case preserved)
search_query = 
font_family = system
font_size = 0
heading_font_size = 0
fixed_font_size = 0

# Manual Tweaks window.
[manual_updates]
update_tags = true

# Add New Shows window.
[add_new_shows]
check_for_duplicates = true
"""


def default_text(*, auto_update=False):
    """Create the approved concise INI layout without duplicating boolean help."""
    if not auto_update:
        return _DEFAULT_TEMPLATE
    return re.sub(
        r'(?m)^(auto_update\s*=\s*)false$',
        lambda match: match.group(1) + 'true',
        _DEFAULT_TEMPLATE,
        count=1,
    )


def _read_entries(text):
    """Read simple INI assignments, collecting *all* syntax/name errors with line numbers.

    Case-fold only section/key identifiers, never path or query values. Using a
    small explicit INI grammar avoids ConfigParser stopping at its first error.
    """
    errors = []
    entries = []
    current = None
    seen_sections = set()
    seen_keys = set()
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(('#', ';')):
            continue
        if stripped.startswith('['):
            match = re.fullmatch(r'\[([A-Za-z][A-Za-z0-9_]*)\]\s*(?:[;#].*)?', stripped)
            if not match:
                errors.append(f'Line {number}: Invalid section header {stripped!r}; expected [section]')
                current = None
                continue
            current = match.group(1).casefold()
            if current in seen_sections:
                errors.append(f'Line {number}: Duplicate section [{current}]')
            seen_sections.add(current)
            if current not in DEFAULTS:
                errors.append(f'Line {number}: Unknown preferences section [{current}]; allowed: {", ".join(DEFAULTS)}')
            continue
        match = re.fullmatch(r'\s*([A-Za-z][A-Za-z0-9_]*)\s*[=:]\s*(.*?)\s*', line)
        if not match:
            errors.append(f'Line {number}: Invalid preference assignment {stripped!r}; expected key = value')
            continue
        key, value = match.group(1).casefold(), match.group(2).strip()
        # Inline comments are accepted only after horizontal whitespace.  An
        # embedded '#' in a path or a search query is left untouched.
        value = re.split(r'[ \t]+[;#]', value, maxsplit=1)[0].rstrip()
        if current is None:
            errors.append(f'Line {number}: [{"no section"}] {key}: key is not inside a valid section')
            continue
        if current not in DEFAULTS:
            continue  # Unknown section was already reported with its line number.
        if key not in DEFAULTS[current]:
            errors.append(f'Line {number}: Unknown preference [{current}] {key}; allowed keys: {", ".join(DEFAULTS[current])}')
            continue
        identity = current, key
        if identity in seen_keys:
            errors.append(f'Line {number}: Duplicate preference [{current}] {key}')
            continue
        seen_keys.add(identity)
        entries.append((number, current, key, value))
    return entries, errors


def _parse_value(section, key, raw):
    """Validate/normalize enum and boolean values, leaving path/query case intact."""
    value = raw.strip()
    if (section, key) in BOOL_KEYS:
        try:
            return BOOLEAN_WORDS[value.casefold()]
        except KeyError as exc:
            raise ValueError(f'expected {allowed_description(section, key)}') from exc
    if (section, key) in CHOICES:
        normalized = value.casefold()
        if normalized not in CHOICES[section, key]:
            raise ValueError(f'expected {allowed_description(section, key)}')
        return normalized
    if (section, key) in FONT_SIZES or (section, key) in {
        ('main', 'max_workers'), ('main', 'corrupt_folder_threshold'),
    }:
        try:
            number = int(value)
        except ValueError as exc:
            raise ValueError(f'expected {allowed_description(section, key)}') from exc
        if (section, key) in FONT_SIZES and number != 0 and not 7 <= number <= 40:
            raise ValueError(f'expected {allowed_description(section, key)}')
        if (section, key) == ('main', 'max_workers') and not 0 <= number <= 256:
            raise ValueError(f'expected {allowed_description(section, key)}')
        if (section, key) == ('main', 'corrupt_folder_threshold') and not 0 <= number <= 100:
            raise ValueError(f'expected {allowed_description(section, key)}')
        return number
    if key == 'font_family':
        if not value or len(value) > 100 or any(ord(char) < 32 for char in value):
            raise ValueError(f'expected {allowed_description(section, key)}')
        return 'system' if value.casefold() == 'system' else value
    if key in ('search_path', 'search_query'):
        if len(value) > 4096 or any(ord(char) < 32 for char in value):
            raise ValueError(f'expected {allowed_description(section, key)}')
        return value
    raise ValueError('unsupported preference')


def validation_errors(text):
    """Return a complete, ordered list of actionable INI diagnostics."""
    entries, errors = _read_entries(text)
    result = {section: dict(values) for section, values in DEFAULTS.items()}
    locations = {}
    for number, section, key, raw in entries:
        try:
            result[section][key] = _parse_value(section, key, raw)
            locations[section, key] = number
        except ValueError as exc:
            errors.append(f'Line {number}: Invalid [{section}] {key} = {raw!r}: {exc}')

    main = result['main']
    def conflict(fields, reason):
        detail = ', '.join(f'[main] {field} (line {locations.get(("main", field), "default")})'
                           for field in fields)
        errors.append(f'Conflicting preferences: {detail}: {reason}')

    if main['compliant'] and main['rename_compliantly']:
        conflict(('compliant', 'rename_compliantly'), 'cannot both be true')
    tag_modes = ('tag_during_inventory', 'tag_copy_during_inventory', 'tag_copy_and_delete_enabled')
    active_modes = tuple(field for field in tag_modes if main[field])
    if len(active_modes) > 1:
        conflict(active_modes, 'select no more than one tagging mode')
    if main['setlistfm_lookup'] and not main['etree_lookup']:
        conflict(('setlistfm_lookup', 'etree_lookup'), 'setlistfm_lookup requires etree_lookup=true')
    if main['setlistfm_upgrade'] and not main['setlistfm_lookup']:
        conflict(('setlistfm_upgrade', 'setlistfm_lookup'), 'setlistfm_upgrade requires setlistfm_lookup=true')
    if main['delete_extra_tags'] and not active_modes:
        conflict(('delete_extra_tags',) + tag_modes, 'delete_extra_tags requires a tagging mode')
    if main['corrupt_files'] == 'keep' and main['corrupt_folders'] != 'never':
        conflict(('corrupt_files', 'corrupt_folders'),
                 'corrupt_files=keep requires corrupt_folders=never (no deletion)')
    return errors


def parse_text(text):
    """Validate ALL settings, then return typed defaults with explicit overrides."""
    errors = validation_errors(text)
    if errors:
        raise ValueError(f'Preferences contain {len(errors)} error(s):\n' +
                         '\n'.join(f'  • {item}' for item in errors))
    result = {section: dict(values) for section, values in DEFAULTS.items()}
    for _line, section, key, raw in _read_entries(text)[0]:
        result[section][key] = _parse_value(section, key, raw)
    return result


def resolve_font_family(requested, families):
    """Return canonical installed font casing for case-insensitive INI selection."""
    if requested.casefold() == 'system':
        return 'system'
    return next((family for family in families if family.casefold() == requested.casefold()), 'system')

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


def save_text(tlo_home, new_text, *, expected_digest=None):
    """Validate then atomically replace; invalid edits never damage the saved file."""
    if len(new_text.encode('utf-8')) > MAX_BYTES:
        raise ValueError('Preferences file exceeds 128 KB')
    validated = parse_text(new_text)
    path = path_for(tlo_home)
    if not path.is_file() or path.is_symlink():
        raise ValueError('Preferences file is missing or is a symbolic link')
    def check_expected_version():
        if expected_digest is not None:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected_digest:
                raise ValueError('Preferences changed since this editor opened. Cancel and reopen to review newer settings; no changes saved.')
    check_expected_version()
    fd, temp_path = tempfile.mkstemp(prefix='.tlo-preferences-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8', newline='\n') as stream:
            stream.write(new_text)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp_path, path.stat().st_mode & 0o777)
        check_expected_version()
        os.replace(temp_path, path)
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)
    return validated


def set_auto_update(tlo_home, enabled):
    """Update the [general] setting in place, preserving its syntax/comments.

    The editor accepts either '=' or ':'; use the same parsed line rather
    than a second, narrower grammar.  Validation is performed before write.
    """
    path = path_for(tlo_home)
    original_bytes = path.read_bytes()
    original = original_bytes.decode('utf-8-sig')
    parse_text(original)
    matches = [(line_no, sec, key) for line_no, sec, key, _ in _read_entries(original)[0]
               if (sec, key) == ('general', 'auto_update')]
    if len(matches) != 1:
        raise ValueError('Preferences must contain exactly one [general] auto_update entry')
    lines = original.splitlines(keepends=True)
    index = matches[0][0] - 1
    pattern = re.compile(r'^(\s*auto_update\s*[=:]\s*)(true|false|yes|no|on|off|0|1)(?=\s*(?:[;#].*)?$)', re.I)
    updated_line, count = pattern.subn(
        lambda match: match.group(1) + str(bool(enabled)).lower(),
        lines[index], count=1,
    )
    if count != 1:
        raise ValueError('Invalid [general] auto_update assignment')
    lines[index] = updated_line
    save_text(tlo_home, ''.join(lines), expected_digest=hashlib.sha256(original_bytes).hexdigest())


def __getattr__(name):
    # Preserve the public pref.messagebox interface for GUI callers/tests while
    # allowing a fully headless process to import pure preference validation.
    if name == 'messagebox':
        from tkinter import messagebox
        return messagebox
    raise AttributeError(name)


def edit(root, tlo_home):
    """Load Tk only when the editor is opened; pure preferences stay headless."""
    import tkinter as tk
    from tkinter import messagebox, ttk
    path = path_for(tlo_home)
    key = os.path.normcase(os.path.abspath(str(path)))
    previous = _EDIT_WINDOWS.get(key)
    if previous is not None:
        try:
            if previous.winfo_exists():
                previous.lift()
                previous.focus_force()
                return previous
        except (AttributeError, tk.TclError):
            pass
        _EDIT_WINDOWS.pop(key, None)
    original_bytes = path.read_bytes()
    original = original_bytes.decode('utf-8-sig')
    expected_digest = hashlib.sha256(original_bytes).hexdigest()
    window = tk.Toplevel(root)
    _EDIT_WINDOWS[key] = window
    window.title('TLO Edit Preferences')
    window.transient(root)
    window.geometry('850x680')
    window.columnconfigure(0, weight=1)
    window.rowconfigure(1, weight=1)
    ttk.Label(window, text=f'{path}\nChanges take effect after restarting TLO Main and Search. Current settings remain unchanged.',
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

    def destroy_editor():
        _EDIT_WINDOWS.pop(key, None)
        window.destroy()

    def close():
        if editor.get('1.0', 'end-1c') != original:
            if not messagebox.askyesno('Unsaved preferences', 'Discard unsaved preferences changes?', parent=window):
                return
        destroy_editor()

    def save_and_close():
        updated = editor.get('1.0', 'end-1c')
        if updated == original:
            destroy_editor()
            return
        try:
            save_text(tlo_home, updated, expected_digest=expected_digest)
        except (OSError, ValueError) as exc:
            messagebox.showerror('Invalid preferences', str(exc), parent=window)
            return  # Keep the editor and current session unchanged.
        # A preferences edit changes the file for the NEXT launch only.
        # Never mutate the owning app's in-memory defaults or GUI variables.
        destroy_editor()
        messagebox.showinfo('Restart required',
            'Preferences saved. Restart TLO Main and Search to apply the changes. '
            'The currently running app and its selected settings are unchanged.', parent=root)

    buttons = ttk.Frame(window, padding=10)
    buttons.grid(row=2, column=0, sticky='e')
    ttk.Button(buttons, text='Save & Close', command=save_and_close).pack(side='left', padx=5)
    ttk.Button(buttons, text='Cancel', command=close).pack(side='left', padx=5)
    window.protocol('WM_DELETE_WINDOW', close)
    return window
