"""Build 450: GUI button labels are centered horizontally and vertically."""

__version__ = "v461"

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def test_shared_ttk_button_style_centers_anchor_and_multiline_justification():
    source = (ROOT / "tlo_gui_shortcuts.py").read_text(encoding="utf-8")
    assert "def configure_centered_ttk_button_text" in source
    assert '("TButton", "TMenubutton")' in source
    assert 'anchor="center"' in source
    assert 'justify="center"' in source


def test_inventory_and_search_apps_apply_shared_centered_button_style():
    inventory = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    search = (ROOT / "tlo-gsi.py").read_text(encoding="utf-8")
    for source in (inventory, search):
        assert "configure_centered_ttk_button_text" in source
    assert 'style.configure("Main.TButton", font=self.main_font, padding=(8, 7), anchor="center", justify="center")' in inventory


def test_main_inventory_one_line_buttons_do_not_use_fake_blank_second_lines():
    source = (ROOT / "tlo-ggi.py").read_text(encoding="utf-8")
    for label in ("Tag", "Research", "Quit", "Pause", "Resume"):
        assert f'text="{label}\\n "' not in source
        assert f'text="{label}"' in source
    # Stretch the one-line buttons vertically to the height of their multi-line row peers;
    # the centered style then places the label in the true vertical middle.
    assert 'self.tag_button.grid(row=0, column=0, padx=4, sticky="nsw")' in source
    assert 'self.research_button.grid(row=0, column=2, padx=4, sticky="nsw")' in source
    assert 'self.pause_button.grid(row=0, column=1, padx=4, sticky="ns")' in source
    assert 'self.resume_button.grid(row=0, column=2, padx=4, sticky="ns")' in source


def test_artist_db_tk_buttons_explicitly_center_their_labels():
    source = (ROOT / "search-artist-db.py").read_text(encoding="utf-8")
    assert 'text="Search", width=12, anchor="center", justify="center"' in source
    assert 'text="Quit", width=12, anchor="center", justify="center"' in source
