"""Build 488 Redundancy Groups dismiss-button wording."""

__version__ = "v493"

from pathlib import Path
import pytest

pytestmark = pytest.mark.behavior


def _redundancy_window_source():
    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    start = source.index("class RedundancyGroupsWindow:")
    end = source.index("class CopyRequestsWindow:", start)
    return source[start:end]


def test_build488_redundancy_groups_uses_close_not_cancel():
    snippet = _redundancy_window_source()
    assert 'ttk.Button(buttons, text="Close", command=self._close)' in snippet
    assert 'ttk.Button(buttons, text="Cancel", command=self._close)' not in snippet
    assert 'ttk.Button(buttons, text="Save", command=self._save)' in snippet


def test_build488_redundancy_groups_layout_and_behavior_unchanged():
    snippet = _redundancy_window_source()
    assert 'buttons.grid(row=4, column=0, sticky="e")' in snippet
    assert 'text="Save", command=self._save).grid(row=0, column=0, padx=4)' in snippet
    assert 'text="Close", command=self._close).grid(row=0, column=1, padx=(4, 0))' in snippet


def test_build488_docs_describe_label_only_change():
    from docx import Document
    req = "\n".join(p.text for p in Document("TLO_Inventory_Requirements_Working_v493.docx").paragraphs)
    manual = Path("TLO_Inventory_User_Manual_v493.rtf").read_text(encoding="utf-8", errors="ignore")
    assert "Current document version: v493 (v1.7 Build 493)." in req
    assert "Build 488 - Redundancy Groups Close label" in req
    assert "labeled Close rather than Cancel" in req
    assert "Build 488 Redundancy Groups Close label" in manual
    assert "Close instead of Cancel" in manual
