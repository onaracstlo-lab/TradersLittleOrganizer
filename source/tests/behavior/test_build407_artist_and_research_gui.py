"""Build 407 artist-suffix and Research-results GUI behavior."""

__version__ = "v448"

import importlib.util
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def _load_hyphen_module(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _matcher(mapping):
    from tlo_artist_db import ArtistMatcher

    matcher = ArtistMatcher(db_path="")
    for term, masters in mapping.items():
        values = set(masters if isinstance(masters, (list, tuple, set)) else [masters])
        matcher.exact_map[term.casefold()] = values
        for master in values:
            matcher.master_aliases.setdefault(master, [master, term])
            matcher.master_norms.setdefault(master, {"".join(ch for ch in master.casefold() if ch.isalpha())})
    return matcher


@pytest.mark.parametrize(
    "candidate",
    [
        "Example All Star",
        "Example All Stars",
        "Example All-Star",
        "Example All-Stars",
        "Example AllStar",
        "Example AllStars",
        "Example-AllStar",
        "Example-AllStars",
        "Example all-stars",
    ],
)
def test_all_star_terminal_permutations_use_same_unique_db_fallback_as_band(candidate):
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Example": "Example Master"})
    suffix = candidate[len("Example"):].strip()
    if candidate.startswith("Example-"):
        expected = "Example Master-" + candidate[len("Example-"):]
    else:
        expected = f"Example Master {suffix}"
    assert lookup_artist_master_with_status(candidate, matcher) == ("matched", [expected])


def test_all_star_full_db_match_wins_before_stripped_fallback():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({
        "Example All-Stars": "Example All-Stars",
        "Example": "Different Example Master",
    })
    assert lookup_artist_master_with_status("Example All-Stars", matcher) == (
        "matched",
        ["Example All-Stars"],
    )


def test_all_star_nonterminal_text_does_not_trigger_fallback():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Example": "Example Master"})
    assert lookup_artist_master_with_status("All Stars Example", matcher) == ("no_match", [])


def test_all_star_ambiguous_stripped_lookup_is_not_promoted():
    from tlo_artist_db import lookup_artist_master_with_status

    matcher = _matcher({"Example": ["Example One", "Example Two"]})
    assert lookup_artist_master_with_status("Example AllStars", matcher) == ("no_match", [])


def _collect(widget, cls, *, text=None):
    matches = []
    for child in widget.winfo_children():
        if isinstance(child, cls) and (text is None or str(child.cget("text")) == text):
            matches.append(child)
        matches.extend(_collect(child, cls, text=text))
    return matches


def test_research_results_ctrl_a_find_dialog_direction_and_wrap(tmp_path):
    try:
        import tkinter as tk
        from tkinter import ttk
        root = tk.Tk()
    except Exception as exc:
        pytest.skip(f"Tk display unavailable: {exc}")

    gui = _load_hyphen_module("tlo-ggi.py", "tlo_ggi_build407_research_results_gui")
    try:
        root.withdraw()
        args = gui._parse_gui_command_line(["--TLOHome", str(tmp_path)])
        app = gui.App(root, args)
        app._show_research_results("Example", "alpha one\nmiddle\nalpha two\n")
        root.update()

        windows = [
            child for child in root.winfo_children()
            if isinstance(child, tk.Toplevel) and "TLO Research Results" in child.title()
            and "Search" not in child.title()
        ]
        assert windows
        results = windows[-1]
        texts = _collect(results, tk.Text)
        assert len(texts) == 1
        output = texts[0]

        assert results.bind("<Control-a>")
        assert results.bind("<Control-f>")

        # Ctrl-A is window-level: the behavior must not depend on the text widget
        # being editable or being the widget that currently has focus.
        close_button = _collect(results, ttk.Button, text="Close")[0]
        close_button.focus_set()
        results.event_generate("<Control-a>")
        root.update()
        selected = output.get("sel.first", "sel.last")
        assert selected == "alpha one\nmiddle\nalpha two\n"
        output.tag_remove("sel", "1.0", "end")
        output.mark_set("insert", "1.0")

        result_search = _collect(results, ttk.Button, text="Search")
        assert result_search
        result_search[0].invoke()
        root.update()

        find_windows = [
            child for child in results.winfo_children()
            if isinstance(child, tk.Toplevel) and "Research Results Search" in child.title()
        ]
        assert find_windows
        find_dialog = find_windows[-1]
        labels = _collect(find_dialog, ttk.Label)
        assert any(str(label.cget("text")) == "Search for:" for label in labels)
        radios = _collect(find_dialog, ttk.Radiobutton)
        assert {str(radio.cget("text")) for radio in radios} == {"Forward", "Backwards"}
        variable_name = str(radios[0].cget("variable"))
        assert root.getvar(variable_name) == "forward"

        entries = _collect(find_dialog, ttk.Entry)
        assert len(entries) == 1
        entries[0].insert(0, "alpha")
        find_search = _collect(find_dialog, ttk.Button, text="Search")
        assert len(find_search) == 1

        # Forward searches continue from the previous match and wrap at the end.
        find_search[0].invoke()
        root.update()
        assert output.index("sel.first") == "1.0"
        find_search[0].invoke()
        root.update()
        assert output.index("sel.first") == "3.0"
        find_search[0].invoke()
        root.update()
        assert output.index("sel.first") == "1.0"

        # Backwards from the first match wraps to the last occurrence.
        backward = next(radio for radio in radios if str(radio.cget("text")) == "Backwards")
        backward.invoke()
        find_search[0].invoke()
        root.update()
        assert output.index("sel.first") == "3.0"
    finally:
        root.destroy()
