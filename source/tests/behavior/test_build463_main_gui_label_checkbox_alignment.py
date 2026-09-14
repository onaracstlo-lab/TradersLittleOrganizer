"""Build 463: Path(s) label and visually aligned main-window checkboxes."""

from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

__version__ = "v463"

ROOT = Path(__file__).resolve().parents[2]


def _source(name: str) -> str:
    return (ROOT / name).read_text(encoding="utf-8")


def test_build463_main_window_uses_paths_label_without_changing_cli_option_name():
    source = _source("tlo-ggi.py")
    build = source[source.index("    def _build(self):"):source.index("    def _enable_search_path_drag_drop", source.index("    def _build(self):"))]
    assert 'text="Path(s)"' in build
    assert 'text="Search Path"' not in build
    options = _source("tlo_options.py")
    assert 'gui="entry", gui_label="Path(s)"' in options
    assert '"search_path_override", "--search-path"' in options


def test_build463_single_line_checkbox_indicator_is_vertically_centered_with_its_label():
    source = _source("tlo-ggi.py")
    start = source.index('style.layout(\n                "Main.Large.TCheckbutton"')
    end = source.index('style.layout(\n                "Main.Multiline.TCheckbutton"', start)
    single = source[start:end]
    assert '("Checkbutton.indicator", {"side": "left", "sticky": ""})' in single


def test_build463_wrapped_checkbox_labels_keep_first_line_alignment():
    source = _source("tlo-ggi.py")
    start = source.index('style.layout(\n                "Main.Multiline.TCheckbutton"')
    end = source.index('        except tk.TclError:', start)
    wrapped = source[start:end]
    assert '("Checkbutton.indicator", {"side": "left", "sticky": "n"})' in wrapped
    assert '"Main.Multiline.TCheckbutton" if "\\n" in checkbox_text else "Main.Large.TCheckbutton"' in source
    assert 'text="Dry run"' in source
    assert 'style="Main.Large.TCheckbutton"' in source
