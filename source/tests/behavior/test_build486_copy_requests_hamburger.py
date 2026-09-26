"""Build 486 moves Copy Requests from the main action row to the hamburger menu."""

from pathlib import Path
from docx import Document
import pytest

pytestmark = pytest.mark.behavior

__version__ = "v493"


def test_build486_copy_requests_is_hamburger_command_not_main_button():
    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    assert 'label="Copy Requests",\n            command=lambda: self._run_after_menu_closes(self._open_copy_requests),' in source
    assert 'text="Copy\\nRequests"' not in source
    assert 'self.copy_requests_button = ttk.Button(' not in source


def test_build486_existing_main_action_button_positions_are_unchanged():
    source = Path("tlo-ggi.py").read_text(encoding="utf-8")
    assert 'self.tag_button.grid(row=0, column=0, padx=4, sticky="nsw")' in source
    assert 'self.add_shows_button.grid(row=0, column=1, padx=4, sticky="nsw")' in source
    assert 'self.research_button.grid(row=0, column=2, padx=4, sticky="nsw")' in source
    assert 'self.manual_tweaks_button.grid(row=0, column=3, padx=4, sticky="nsw")' in source
    assert 'text="Quit",\n            command=self._on_quit,' in source
    assert 'self.inventory_button = ttk.Button(' in source


def test_build486_docs_place_copy_requests_under_hamburger():
    requirements = Document("TLO_Inventory_Requirements_Working_v493.docx")
    requirement_text = "\n".join(p.text for p in requirements.paragraphs)
    assert "Build 486 - Copy Requests moved to hamburger menu" in requirement_text
    assert "removes the Copy Requests button from the main action row" in requirement_text
    assert "upper-right hamburger menu" in requirement_text

    manual = Path("TLO_Inventory_User_Manual_v493.rtf").read_text(encoding="utf-8")
    assert "Open the upper-right hamburger menu, choose Copy Requests" in manual
    assert "Build 486 Copy Requests menu placement" in manual

    faq = Path("TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "Open the upper-right hamburger menu in the Inventory window and choose Copy Requests" in faq
