"""Safety-checked Manual Tweaks undo using *metadata-only* journals.

No media payload is copied, embedded, archived or stored in the journal.  For
mutagen-supported formats, only their tag metadata is retained, including ID3
frames when present.  Undo is intentionally conservative: later file/catalog
changes or a broken journal prevent an automatic reversal.
"""
from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import base64
import hashlib
import hmac
import io
import json
import os
import re
import secrets
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from mutagen import File as MutagenFile
from mutagen.id3 import ID3
from mutagen.apev2 import APEValue, APETextValue, APEBinaryValue, APEExtValue
from tlo_tag_lib import TAGGABLE_AUDIO_EXTENSIONS
from tlo_folder_rename import rename_folder_exact_case


class ManualUndoError(RuntimeError):
    pass


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode('ascii')


def _from_b64(value: str) -> bytes:
    return base64.b64decode(value.encode('ascii'), validate=True)


def _encode(value: Any) -> Any:
    """JSON-safe encoding of native mutagen values, never Python pickle."""
    if value is None or type(value) in (str, bool, int, float):
        return value
    if isinstance(value, (APETextValue, APEBinaryValue, APEExtValue)):
        return {'__ape__': _b64(bytes(value)), 'kind': int(value.kind)}
    if isinstance(value, bytes):
        kind = type(value).__name__
        return {"__binary__": _b64(bytes(value)), "kind": kind,
                "format": getattr(value, 'imageformat', getattr(value, 'dataformat', None))}
    if isinstance(value, tuple):
        return {"__tuple__": [_encode(v) for v in value]}
    if isinstance(value, list):
        return [_encode(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _encode(v) for k, v in value.items()}
    # APEv2 values are bytes-like but need explicit conversion, not repr().
    try:
        return {"__binary__": _b64(bytes(value)), "kind": "bytes", "format": None}
    except (TypeError, ValueError) as exc:
        raise ManualUndoError(f"Cannot record tag value type {type(value).__name__}; use Manual Tweaks without Update Tags") from exc


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(v) for v in value]
    if isinstance(value, dict):
        if '__ape__' in value:
            return APEValue((_from_b64(value['__ape__']) if value['kind'] == 1 else
                             _from_b64(value['__ape__']).decode('utf-8')), value['kind'])
        if '__tuple__' in value:
            return tuple(_decode(v) for v in value['__tuple__'])
        if '__binary__' in value:
            raw = _from_b64(value['__binary__'])
            if value.get('kind') == 'MP4Cover':
                from mutagen.mp4 import MP4Cover
                return MP4Cover(raw, imageformat=value['format'])
            if value.get('kind') == 'MP4FreeForm':
                from mutagen.mp4 import MP4FreeForm
                return MP4FreeForm(raw, dataformat=value['format'])
            return raw
        return {k: _decode(v) for k, v in value.items()}
    return value


def _tag_state(file_name: str) -> dict:
    try:
        audio = MutagenFile(file_name, easy=False)
    except Exception:
        audio = None
    if audio is None:
        # Invalid media is not taggable. If unchanged, folder/bootlist undo is
        # still safe. If its bytes change, the file manifest blocks undo.
        return {'type': 'opaque'}
    tags = getattr(audio, 'tags', None)
    if tags is None:
        return {'type': 'none'}
    if isinstance(tags, ID3):
        # WAVE/AIFF attach container-specific subclasses of ID3 whose .save()
        # expects a RIFF/AIFF header; serialize a fresh stand-alone ID3 tag.
        memory = io.BytesIO()
        portable = ID3()
        for frame in tags.values():
            portable.add(frame)
        portable.save(memory)
        return {'type': 'id3', 'frames': _b64(memory.getvalue()),
                'version': 3 if tags.version[1] == 3 else 4}
    if isinstance(tags, list) and hasattr(tags, 'as_dict'):
        return {'type': 'vorbis', 'pairs': [[str(k), str(v)] for k, v in tags]}
    if not hasattr(tags, 'items'):
        raise ManualUndoError(f"Cannot safely record tags for {file_name}; run without Update Tags")
    return {'type': 'mapping', 'values': {str(k): _encode(v) for k, v in tags.items()}}


def _restore_tags(file_name: str, state: dict) -> None:
    kind = state['type']
    if kind == 'opaque':
        return
    audio = MutagenFile(file_name, easy=False)
    if audio is None:
        raise ManualUndoError(f"Audio is unreadable during tag undo: {file_name}")
    if kind == 'none':
        if getattr(audio, 'tags', None) is not None:
            audio.delete()
        return
    if getattr(audio, 'tags', None) is None:
        audio.add_tags()
    tags = audio.tags
    tags.clear()
    if kind == 'id3':
        restored = ID3(io.BytesIO(_from_b64(state['frames'])))
        for frame in restored.values():
            tags.add(frame)
    elif kind == 'vorbis':
        tags.extend([(key, value) for key, value in state['pairs']])
    elif kind == 'mapping':
        for key, value in state['values'].items():
            tags[key] = _decode(value)
    else:
        raise ManualUndoError(f"Unrecognized recorded tag format: {kind}")
    if kind == 'id3' and state.get('version') == 3:
        audio.save(v2_version=3)
    else:
        audio.save()


def _bytes_state(path_name: str) -> dict:
    if not os.path.isfile(path_name):
        return {'exists': False}
    with open(path_name, 'rb') as stream:
        return {'exists': True, 'content': _b64(stream.read())}


def _file_digest(path_name: str) -> dict:
    if not os.path.isfile(path_name):
        return {'exists': False}
    digest = hashlib.sha256()
    with open(path_name, 'rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(part)
    return {'exists': True, 'sha256': digest.hexdigest()}


def _atomic_bytes(path_name: str, payload: bytes) -> None:
    parent = os.path.dirname(path_name) or '.'
    os.makedirs(parent, exist_ok=True)
    descriptor, temp = tempfile.mkstemp(prefix='.tlo-undo-', dir=parent)
    try:
        with os.fdopen(descriptor, 'wb') as output:
            output.write(payload)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temp, path_name)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def _restore_bytes(path_name: str, state: dict) -> None:
    if state['exists']:
        _atomic_bytes(path_name, _from_b64(state['content']))
    elif os.path.isfile(path_name):
        os.unlink(path_name)


def _tree_stats(root: str) -> dict:
    """File identity without reading/duplicating media payloads."""
    if not os.path.isdir(root) or os.path.islink(root):
        raise ManualUndoError(f"Expected a real folder: {root}")
    found = {}
    for current, folders, files in os.walk(root, followlinks=False):
        for leaf in folders + files:
            path = os.path.join(current, leaf)
            if os.path.islink(path):
                raise ManualUndoError(f"Manual Tweaks undo cannot journal symlinked entries: {path}")
            relative = os.path.relpath(path, root).replace('\\', '/')
            stat = os.stat(path, follow_symlinks=False)
            found[relative] = {'dir': os.path.isdir(path)} if os.path.isdir(path) else {
                'size': stat.st_size, 'mtime_ns': stat.st_mtime_ns,
                'inode': getattr(stat, 'st_ino', 0),
            }
    return found


def _tag_files(root: str) -> dict:
    result = {}
    for current, _folders, files in os.walk(root, followlinks=False):
        for leaf in files:
            if Path(leaf).suffix.lower() not in TAGGABLE_AUDIO_EXTENSIONS:
                continue
            path = os.path.join(current, leaf)
            if os.path.islink(path):
                raise ManualUndoError(f"Cannot journal symlinked audio: {path}")
            result[os.path.relpath(path, root).replace('\\', '/')] = _tag_state(path)
    return result


def _journal_dir(home: str) -> str:
    return os.path.join(home, 'logs', 'manual-updates-undo')


def _key_path(home: str) -> str:
    """A separate per-user key; TLOHome alone cannot authorize forged journals."""
    base = (os.environ.get('LOCALAPPDATA') if os.name == 'nt' else
            os.environ.get('XDG_STATE_HOME'))
    if not base:
        base = (os.path.join(os.path.expanduser('~'), 'AppData', 'Local') if os.name == 'nt'
                else os.path.join(os.path.expanduser('~'), '.local', 'state'))
    token = hashlib.sha256(os.path.realpath(home).encode('utf-8')).hexdigest()
    return os.path.join(base, 'TradersLittleOrganizer', 'manual-undo-keys', token + '.key')


def _protect_windows_undo_key(path: str) -> None:
    """Remove inherited Everyone/Users access from the per-user HMAC secret.

    LocalAppData is normally private, but Windows installers, redirection and
    inherited ACLs can change that assumption. Windows chmod is not an ACL
    operation: enforce the current user's SID plus SYSTEM explicitly instead.
    A failure must prevent creating or using new undo records.
    """
    if os.name != 'nt':
        return
    try:
        who = subprocess.run(['whoami.exe', '/user', '/fo', 'csv', '/nh'],
                             capture_output=True, text=True, timeout=15, check=True)
        found = re.findall(r'S-1-\d+(?:-\d+)+', who.stdout)
        if len(found) != 1:
            raise ManualUndoError('Cannot resolve current Windows SID for undo key protection')
        sid = '*' + found[0]
        for target, grants in (
            (os.path.dirname(path), [f'{sid}:(OI)(CI)F', '*S-1-5-18:(OI)(CI)F']),
            (path, [f'{sid}:F', '*S-1-5-18:F']),
        ):
            result = subprocess.run(['icacls.exe', target, '/inheritance:r',
                                     '/grant:r', *grants], capture_output=True,
                                    text=True, timeout=15, check=False)
            if result.returncode:
                raise ManualUndoError('Could not enforce private Windows ACL on Manual Tweaks key: '
                                      + (result.stderr.strip() or result.stdout.strip()))
    except (OSError, subprocess.SubprocessError) as exc:
        raise ManualUndoError('Could not enforce private Windows ACL on Manual Tweaks key') from exc


def _secret(home: str, *, create: bool) -> bytes:
    path = _key_path(home)
    legacy = os.path.join(home, 'logs', '.manual-updates-undo-key')
    if os.path.islink(path) or os.path.islink(legacy):
        raise ManualUndoError('Refusing a symlinked Manual Tweaks undo key')
    if not os.path.isfile(path) and (create or os.path.isfile(legacy)):
        directory = os.path.dirname(path)
        os.makedirs(directory, mode=0o700, exist_ok=True)
        if os.name != 'nt':
            os.chmod(directory, 0o700)
        # Preserve the exact key used by older journals for upgrade-safe undo.
        # A missing legacy key starts a new journal key only on creation.
        if os.path.isfile(legacy):
            with open(legacy, 'rb') as previous:
                old_key = previous.read(33)
            if len(old_key) != 32:
                raise ManualUndoError('Legacy Manual Tweaks undo key is invalid')
            material = old_key
        else:
            material = secrets.token_bytes(32)
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            with os.fdopen(descriptor, 'wb') as output:
                output.write(material)
                output.flush()
                os.fsync(output.fileno())
        # Protect the key before retiring the legacy copy. A failed ACL
        # operation does not silently weaken recovery authorization.
        _protect_windows_undo_key(path)
        if os.path.isfile(legacy):
            with open(path, 'rb') as current:
                if current.read(33) == material:
                    os.unlink(legacy)
    try:
        if os.path.islink(path):
            raise ManualUndoError('Refusing a symlinked Manual Tweaks undo key')
        with open(path, 'rb') as stream:
            key = stream.read(33)
    except OSError as exc:
        raise ManualUndoError('Manual Tweaks undo key is missing; no automatic reversal is safe') from exc
    if len(key) != 32:
        raise ManualUndoError('Manual Tweaks undo key is invalid')
    return key


def _canonical(entry: dict) -> bytes:
    return json.dumps(entry, sort_keys=True, ensure_ascii=True, separators=(',', ':')).encode('ascii')


_MAX_JOURNAL_BYTES = 64 * 1024 * 1024


def _write_journal(home: str, path: str, record: dict) -> None:
    signature = hmac.new(_secret(home, create=True), _canonical(record), hashlib.sha256).hexdigest()
    serialized = _canonical({'record': record, 'hmac_sha256': signature}) + b'\n'
    if len(serialized) > _MAX_JOURNAL_BYTES:
        raise ManualUndoError('Manual Tweaks tag metadata exceeds the 64 MiB undo journal limit; no commit is safe')
    _atomic_bytes(path, serialized)
    if os.name != 'nt':
        os.chmod(path, 0o600)


def _load_journal(home: str, path: str) -> dict:
    if not os.path.isfile(path) or os.path.islink(path) or os.path.getsize(path) > 64 * 1024 * 1024:
        raise ManualUndoError('Manual Tweaks undo journal is missing or exceeds the metadata-only size limit')
    with open(path, 'rb') as stream:
        payload = json.load(stream)
    record = payload['record']
    expected = hmac.new(_secret(home, create=False), _canonical(record), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, payload['hmac_sha256']):
        raise ManualUndoError('Manual Tweaks undo journal integrity check failed; no changes made')
    if record.get('schema') != 1 or os.path.realpath(record.get('home', '')) != os.path.realpath(home):
        raise ManualUndoError('Manual Tweaks undo journal belongs to a different home/schema')
    return record


def begin_manual_undo(home: str, source: str, destination: str, *, mode: str,
                      update_tags: bool, setlist_paths: list[str]) -> str:
    root = source if mode == 'inventory' and os.path.isdir(source) else destination
    if not os.path.isdir(root):
        raise ManualUndoError(f"Cannot journal missing folder: {root}")
    output = _journal_dir(home)
    os.makedirs(output, exist_ok=True)
    journal = os.path.join(output, f'manual-update-{secrets.token_hex(16)}.json')
    paths = sorted({os.path.abspath(path) for path in setlist_paths})
    # Validate user-provided generated-setlist paths *before* reading bytes.
    _validate_restore_targets(home, {'setlists_before': {p: {} for p in paths},
        'setlists_after': {}, 'bootlist_before': {}, 'bootlist_after': {},
        'unidentified_before': {}, 'unidentified_after': {}})
    record = {
        'schema': 1, 'home': os.path.realpath(home), 'source': os.path.abspath(source),
        'destination': os.path.abspath(destination), 'mode': mode, 'update_tags': bool(update_tags),
        'state': 'prepared',
        'source_parent_real': os.path.realpath(os.path.dirname(source)),
        'destination_parent_real': os.path.realpath(os.path.dirname(destination)),
        'bootlist_before': _bytes_state(os.path.join(home, 'bootlist.csv')),
        'unidentified_before': _bytes_state(os.path.join(home, 'unidentifiedShows.txt')),
        'setlists_before': {path: _bytes_state(path) for path in paths},
        'tree_before': _tree_stats(root),
        'tags_before': _tag_files(root) if update_tags else {},
    }
    _write_journal(home, journal, record)
    return journal


def finish_manual_undo(home: str, journal: str, *, generated: str = '') -> None:
    record = _load_journal(home, journal)
    if record['state'] != 'prepared':
        raise ManualUndoError('Manual Tweaks undo record was already finalized')
    destination = record['destination']
    record['tree_after'] = _tree_stats(destination)
    after_states = _tag_files(destination) if record['update_tags'] else {}
    record['tags_after'] = {name: hashlib.sha256(_canonical(value)).hexdigest()
                            for name, value in after_states.items()}
    if record['update_tags'] and set(record['tags_before']) != set(record['tags_after']):
        raise ManualUndoError('Taggable media paths changed during Manual Tweaks; cannot safely record undo')
    # Opaque/unreadable media may not be modified, because original tags could
    # not have been captured. Check the filesystem stat again after tagging.
    for relative, tags in record['tags_before'].items():
        if tags.get('type') == 'opaque':
            if record['tree_after'].get(relative) != record['tree_before'].get(relative):
                raise ManualUndoError(f'Previously unreadable media changed during Manual Tweaks: {relative}')
            # Any mutagen-unsupported file written by the tagger is forbidden.
            if after_states[relative] != tags:
                raise ManualUndoError(f'Previously unreadable media became taggable: {relative}')
    previous = record['setlists_before']
    paths = sorted(set(previous) | ({os.path.abspath(generated)} if generated else set()))
    record['setlists_after'] = {path: _file_digest(path) for path in paths}
    record['bootlist_after'] = _file_digest(os.path.join(home, 'bootlist.csv'))
    record['unidentified_after'] = _file_digest(os.path.join(home, 'unidentifiedShows.txt'))
    record['state'] = 'committed'
    _write_journal(home, journal, record)


def rollback_manual_tags(home: str, journal: str, folder: str) -> None:
    record = _load_journal(home, journal)
    if not record.get('update_tags'):
        return
    for relative, state in record['tags_before'].items():
        file_name = os.path.join(folder, *relative.split('/'))
        if os.path.isfile(file_name):
            _restore_tags(file_name, state)


def _matching_journals(home: str, path: str) -> list[str]:
    root = _journal_dir(home)
    if not os.path.isdir(root):
        return []
    requested = os.path.normcase(os.path.abspath(path))
    matches = []
    for name in os.listdir(root):
        if not (name.startswith('manual-update-') and name.endswith('.json')):
            continue
        journal = os.path.join(root, name)
        try:
            record = _load_journal(home, journal)
        except (ManualUndoError, OSError, ValueError, KeyError, TypeError):
            # A corrupt unrelated journal must not block all other reversals.
            continue
        if record['state'] in ('committed', 'reversing') and requested in (
            os.path.normcase(record['source']), os.path.normcase(record['destination'])
        ):
            matches.append(journal)
    return matches


def _validate_restore_targets(home: str, record: dict) -> None:
    """Never let a journal redirect restoration outside owned catalog/setlists."""
    root = os.path.realpath(home)
    setlists_root = os.path.join(root, 'setlists')
    for name in set(record.get('setlists_before', {})) | set(record.get('setlists_after', {})):
        absolute = os.path.abspath(name)
        if (os.path.islink(absolute) or os.path.islink(os.path.dirname(absolute))
                or os.path.commonpath((os.path.realpath(absolute), setlists_root)) != setlists_root):
            raise ManualUndoError(f'Undo setlist target is outside TLOHome/setlists: {name}')
    for name in ('bootlist_before', 'bootlist_after', 'unidentified_before', 'unidentified_after'):
        if name not in record:
            raise ManualUndoError(f'Manual Tweaks undo journal missing {name}')


def _digest_of_recorded_bytes(state: dict) -> dict:
    if not state['exists']:
        return {'exists': False}
    return {'exists': True, 'sha256': hashlib.sha256(_from_b64(state['content'])).hexdigest()}


def plan_manual_updates_batch(tlo_home: str, count: int) -> list[dict]:
    """Select an unambiguous newest-first chain without making any changes.

    Each previous catalog state must match the next journal's committed state.
    This prevents a batch from silently overwriting intervening inventories.
    If a later ordinary inventory changed the catalog, the chain is broken and
    the user must resolve it; no speculative rebase/merge is attempted.
    """
    if count < 1 or count > 100:
        raise ManualUndoError('Manual Tweaks batch count must be between 1 and 100')
    home = os.path.realpath(tlo_home)
    directory = _journal_dir(home)
    if not os.path.isdir(directory):
        raise ManualUndoError('No Manual Tweaks undo journals found')
    available = []
    for filename in os.listdir(directory):
        if not (filename.startswith('manual-update-') and filename.endswith('.json')):
            continue
        journal = os.path.join(directory, filename)
        try:
            record = _load_journal(home, journal)
        except (ManualUndoError, OSError, ValueError, TypeError, KeyError):
            continue  # Unrelated invalid journals cannot authorize reversal.
        if record.get('state') == 'committed':
            available.append((journal, record))
    boot = _file_digest(os.path.join(home, 'bootlist.csv'))
    unidentified = _file_digest(os.path.join(home, 'unidentifiedShows.txt'))
    selected = []
    for _position in range(count):
        candidates = [(journal, record) for journal, record in available
                      if record.get('bootlist_after') == boot
                      and record.get('unidentified_after') == unidentified]
        if len(candidates) != 1:
            raise ManualUndoError(
                f'Batch undo preflight requires one unambiguous next journal, found {len(candidates)} '
                f'at step {len(selected) + 1}/{count}; no changes made'
            )
        journal, record = candidates[0]
        selected.append({'journal': journal, 'path': record['destination'],
                         'source': record['source'], 'destination': record['destination']})
        available.remove((journal, record))
        boot = _digest_of_recorded_bytes(record['bootlist_before'])
        unidentified = _digest_of_recorded_bytes(record['unidentified_before'])
    return selected


def reverse_manual_updates_batch(tlo_home: str, count: int, *, dry_run: bool = False, emit=None) -> dict:
    """Replay one verified chain in reverse order under the caller's inventory lock.

    No media file is copied. Each step still performs the ordinary full folder,
    tag and catalog integrity validation immediately before mutation; on a
    conflict or write error, stop without touching earlier operations.
    """
    plan = plan_manual_updates_batch(tlo_home, count)
    if dry_run:
        # A chain of snapshots is not a guarantee about current folder states.
        # Preview the first operation with the ordinary strict validator.
        reverse_manual_update(plan[0]['path'], tlo_home=tlo_home,
                              log_path=plan[0]['journal'], dry_run=True)
        if emit:
            for step in plan:
                emit(f"WOULD UNDO: {step['destination']} -> {step['source']} | {step['journal']}")
        return {'reversed': 0, 'planned': len(plan), 'dry_run': True}
    completed = 0
    for step in plan:
        reverse_manual_update(step['path'], tlo_home=tlo_home,
                              log_path=step['journal'], emit=emit)
        completed += 1
    return {'reversed': completed, 'planned': len(plan), 'dry_run': False}


def list_manual_updates(tlo_home: str) -> list[dict]:
    """List signed journals, newest first; never trust or execute their contents."""
    home = os.path.realpath(tlo_home)
    directory = _journal_dir(home)
    if not os.path.isdir(directory):
        return []
    paths = [os.path.join(directory, name) for name in os.listdir(directory)
             if name.startswith('manual-update-') and name.endswith('.json')]
    paths.sort(key=lambda path: os.path.getmtime(path), reverse=True)
    results = []
    for path in paths:
        try:
            record = _load_journal(home, path)
            eligible = (record.get('state') == 'committed' and
                        _file_digest(os.path.join(home, 'bootlist.csv')) == record.get('bootlist_after'))
            results.append({'journal': path, 'state': record['state'],
                            'source': record['source'], 'destination': record['destination'],
                            'inventory_unchanged': eligible})
        except (ManualUndoError, ValueError, TypeError, OSError, KeyError) as exc:
            results.append({'journal': path, 'state': 'invalid', 'error': str(exc),
                            'inventory_unchanged': False})
    return results


def reverse_manual_update(path: str, *, tlo_home: str, log_path: str = '',
                          dry_run: bool = False, emit=None) -> dict:
    """Undo a committed Manual Tweaks operation, refusing any later changes.

    Reversal is not a filesystem snapshot restore: it replays the original tag
    values into the existing audio containers, without duplicating media data.
    """
    home = os.path.realpath(tlo_home)
    candidates = [_journal_dir(home) + os.sep + os.path.basename(log_path)] if log_path else _matching_journals(home, path)
    if len(candidates) != 1:
        raise ManualUndoError(f"Expected exactly one matching Manual Tweaks undo journal, found {len(candidates)}; use --log to select one")
    journal = candidates[0]
    record = _load_journal(home, journal)
    if record['state'] not in ('committed', 'reversing'):
        raise ManualUndoError(f"Cannot undo journal in state {record['state']}")
    resuming = record['state'] == 'reversing'
    if os.path.normcase(os.path.abspath(path)) not in (
        os.path.normcase(record['source']), os.path.normcase(record['destination'])
    ):
        raise ManualUndoError('Requested path does not match the signed Manual Tweaks undo journal')
    _validate_restore_targets(home, record)
    destination = record['destination']
    source = record['source']
    if (os.path.realpath(os.path.dirname(destination)) != record['destination_parent_real']
            or os.path.realpath(os.path.dirname(source)) != record['source_parent_real']):
        raise ManualUndoError('Folder parent was replaced or redirected since Manual Tweaks; no changes made')
    already_renamed = bool(record['mode'] == 'inventory' and source != destination
                           and os.path.isdir(source) and not os.path.lexists(destination))
    if resuming and not already_renamed:
        raise ManualUndoError('Interrupted undo has an unexpected folder layout; manual reconciliation required')
    if not resuming and record['mode'] == 'inventory' and source != destination and os.path.lexists(source):
        raise ManualUndoError(f"Original folder already exists: {source}")
    active_check = source if already_renamed else destination
    if not resuming:
        if _tree_stats(active_check) != record['tree_after']:
            raise ManualUndoError('Manual Tweaks audio/folder content changed after the operation; no changes made')
        if record['update_tags'] and {name: hashlib.sha256(_canonical(state)).hexdigest()
                                      for name, state in _tag_files(active_check).items()} != record['tags_after']:
            raise ManualUndoError('Manual Tweaks audio tags changed after the operation; no changes made')
    else:
        # Compare every file still awaiting replay with its expected post-state;
        # compare completed entries to their original value. A later user edit
        # must never be blindly overwritten by resuming the transaction.
        tags_now = _tag_files(active_check) if record['update_tags'] else {}
        if set(tags_now) != set(record['tags_before']):
            raise ManualUndoError('Audio files changed while undo was interrupted')
        for name, state in tags_now.items():
            original = record['tags_before'][name]
            after = record['tags_after'][name]
            current = hashlib.sha256(_canonical(state)).hexdigest()
            if current not in (after, hashlib.sha256(_canonical(original)).hexdigest()):
                raise ManualUndoError(f'Audio tags changed after interrupted undo: {name}')
    for filename, before, after in (
        (os.path.join(home, 'bootlist.csv'), record['bootlist_before'], record['bootlist_after']),
        (os.path.join(home, 'unidentifiedShows.txt'), record['unidentified_before'], record['unidentified_after']),
        *((name, record['setlists_before'].get(name, {'exists': False}), digest)
          for name, digest in record['setlists_after'].items()),
    ):
        actual = _file_digest(filename)
        before_digest = (hashlib.sha256(_from_b64(before['content'])).hexdigest()
                         if before['exists'] else None)
        already_reversed = actual == ({'exists': True, 'sha256': before_digest} if before['exists'] else {'exists': False})
        if actual != after and not (resuming and already_reversed):
            raise ManualUndoError(f"Manual Tweaks inventory/setlist changed since the operation: {filename}; no changes made")
    message = f"MANUAL_TWEAKS_UNDO: {destination} -> {source} | tags={'yes' if record['update_tags'] else 'no'} | journal={journal}"
    if emit:
        emit(message)
    if dry_run:
        return {'reversed': 0, 'dry_run': True, 'journal': journal, 'message': message}

    # Rename first: if Windows or an open file refuses it, nothing else has
    # been altered, and a normal retry can still pass the original preflight.
    if record['mode'] == 'inventory' and source != destination and not already_renamed:
        try:
            rename_folder_exact_case(destination, source)
        except OSError as exc:
            raise ManualUndoError(f'Cannot rename folder for undo; no tags/catalog changed: {exc}') from exc
    active = source if record['mode'] == 'inventory' and source != destination else destination
    # Mark the operation for assisted recovery if a later metadata write fails.
    record['state'] = 'reversing'
    _write_journal(home, journal, record)
    try:
        if record['update_tags']:
            for relative, state in record['tags_before'].items():
                _restore_tags(os.path.join(active, *relative.split('/')), state)
        for path_name, state in record['setlists_before'].items():
            _restore_bytes(path_name, state)
        for path_name in record['setlists_after']:
            if path_name not in record['setlists_before'] and os.path.isfile(path_name):
                os.unlink(path_name)
        _restore_bytes(os.path.join(home, 'bootlist.csv'), record['bootlist_before'])
        _restore_bytes(os.path.join(home, 'unidentifiedShows.txt'), record['unidentified_before'])
    except Exception as exc:  # A failed mutagen save must not lose recovery instructions.
        raise ManualUndoError(f'Undo interrupted; journal {journal} remains in reversing state. '
                              f'Retry with --manual-updates once the write blocker is resolved: {exc}') from exc
    record['state'] = 'reversed'
    _write_journal(home, journal, record)
    return {'reversed': 1, 'dry_run': False, 'journal': journal, 'message': message}
