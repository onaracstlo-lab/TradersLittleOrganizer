"""Pre-mutation audio corruption threshold handling for TLO."""
from __future__ import annotations

__version__ = "v394"
# TLO-GI package version: v394
__version_summary__ = 'Harden Linux CI regression tests so synthetic FLAC fixtures explicitly opt out of corruption removal; runtime behavior is unchanged.'
# TLO-GI version summary: Harden Linux CI regression tests so synthetic FLAC fixtures explicitly opt out of corruption removal; runtime behavior is unchanged.
import ctypes, os, subprocess, sys
from pathlib import Path
from mutagen import File as MutagenFile
try:
    from mutagen.flac import FLAC
except Exception:
    FLAC = None
MEDIA_EXTENSIONS={".flac",".mp3",".m4a",".mp4",".ogg",".oga",".opus",".wav",".aif",".aiff",".ape",".wv",".tta",".wma"}

def group_audio_files(group):
    out=[]; seen=set()
    for directory in group.get("music_dirs") or [group.get("main_dir_path","")]:
        try: names=os.listdir(directory)
        except OSError: continue
        for name in names:
            path=os.path.join(directory,name)
            if os.path.isfile(path) and Path(name).suffix.lower() in MEDIA_EXTENSIONS:
                key=os.path.normcase(os.path.normpath(path))
                if key not in seen: seen.add(key); out.append(path)
    return sorted(out,key=str.lower)

def corrupt_audio_files(group):
    bad=[]
    for path in group_audio_files(group):
        try:
            if path.lower().endswith(".flac") and FLAC is not None:
                FLAC(path)
            else:
                audio=MutagenFile(path)
                if audio is None: raise ValueError("unrecognized audio")
        except Exception:
            bad.append(path)
    return bad

def exceeds_threshold(total,bad,acceptable_percent):
    return total>0 and bad*100>int(acceptable_percent)*total

def _trash_windows(path):
    from ctypes import wintypes
    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_=[("hwnd",wintypes.HWND),("wFunc",wintypes.UINT),("pFrom",wintypes.LPCWSTR),("pTo",wintypes.LPCWSTR),("fFlags",ctypes.c_ushort),("fAnyOperationsAborted",wintypes.BOOL),("hNameMappings",ctypes.c_void_p),("lpszProgressTitle",wintypes.LPCWSTR)]
    op=SHFILEOPSTRUCTW(); op.wFunc=3; op.pFrom=str(path)+"\0\0"; op.fFlags=0x0040|0x0010|0x0400
    rc=ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if rc or op.fAnyOperationsAborted: raise OSError(f"Recycle Bin operation failed ({rc})")

def move_to_trash(path):
    path=os.path.abspath(path)
    if sys.platform.startswith("win"):
        return _trash_windows(path)
    if sys.platform=="darwin":
        escaped=path.replace("\\","\\\\").replace('"','\\"')
        subprocess.run(["osascript","-e",f'tell application "Finder" to delete POSIX file "{escaped}"'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
        return
    subprocess.run(["gio","trash",path],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True)
