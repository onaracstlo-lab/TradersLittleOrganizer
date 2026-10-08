from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

import tlo_inventory_update as IU

pytestmark = pytest.mark.behavior


def _outside_double_quotes(line: str) -> str:
    """Return only cmd.exe source characters that are outside quoted literals."""
    outside: list[str] = []
    quoted = False
    index = 0
    while index < len(line):
        char = line[index]
        if char == '"':
            if quoted and index + 1 < len(line) and line[index + 1] == '"':
                # _batch_escape_literal doubles a literal quote.  Keep the pair
                # inside the surrounding quoted display field.
                index += 2
                continue
            quoted = not quoted
        elif not quoted:
            outside.append(char)
        index += 1
    assert quoted is False, f"unbalanced double quotes: {line!r}"
    return "".join(outside)


def test_build533_cleanup_batch_quotes_metacharacter_volume_labels(tmp_path: Path):
    script = tmp_path / "deleteReplacedFolders.bat"
    path = r"D:\Shows\gd1977-05-08 100%"
    label = 'Trade&Box|Pipe<In>Out^Caret(One) 50% "Quoted"'

    assert IU._append_delete_command(str(script), path, label) is True

    text = script.read_text(encoding="utf-8")
    safe_path = IU._batch_escape_literal(path)
    safe_label = IU._batch_escape_literal(label)
    # The recorded label remains human-readable in a comment. The live probe
    # uses only a Base64 value, never raw label syntax in an executable line.
    line = f'REM "[{safe_label}]" "{safe_path}"'
    assert line in text
    assert not any(char in _outside_double_quotes(line) for char in "&|<>^%()")
    assert "100%%" in text
    assert "50%%" in text
    assert "TLO_DELETE_LABEL_B64=" in text
    assert 'if errorlevel 1 goto :TLO_SKIP_' in text
    assert 'after volume-label verification' in text
    assert 'rmdir /s /q "' in text
    # Compare occurs before any active delete, never only after it.
    assert text.index('if errorlevel 1 goto :TLO_SKIP_') < text.index('  rmdir /s /q')


@pytest.mark.skipif(os.name != "nt", reason="native cmd.exe confirmation requires Windows")
def test_build533_cleanup_batch_label_cannot_execute_cmd_metacharacters(tmp_path: Path):
    script = tmp_path / "deleteReplacedFolders.bat"
    # The target deliberately does not exist so only the informational ELSE
    # branch executes.  An unquoted ampersand would set the sentinel variable.
    label = "Trade&set TLO_BUILD533_INJECTED=1&Box(1)|echo harmless>nul^"
    assert IU._append_delete_command(
        str(script), r"Z:\TLO_Build533_Definitely_Missing", label
    ) is True
    with script.open("a", encoding="utf-8", newline="") as handle:
        handle.write("if defined TLO_BUILD533_INJECTED exit /b 97\r\n")
        handle.write("exit /b 0\r\n")

    comspec = os.environ.get("ComSpec", r"C:\Windows\System32\cmd.exe")
    completed = subprocess.run(
        [comspec, "/d", "/c", str(script)],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
