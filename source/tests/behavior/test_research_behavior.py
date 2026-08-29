"""Build 375 Research CLI/GUI and log-search behavior."""

__version__ = "v418"

from pathlib import Path
import importlib.util
import os
import sys

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def _load_hyphen_module(filename: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _write_logs(home: Path, *, artist="Grateful Dead", date="1977-05-08", venue="Barton Hall", stem="ShowA"):
    logs = home / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    main_dir = rf"E:\Music\{stem}"
    (logs / "metaA.log").write_text(
        "\n".join(
            [
                f"SHOW_NAME: {artist} {date} {venue}",
                "SHOW_IN_CONFLICT: no",
                f"MAIN_DIR_PATH: {main_dir}",
                f'MUSIC_DIRS_JSON: ["{main_dir.replace(chr(92), chr(92)*2)}"]',
                f"ARTIST: {artist}",
                f"DATE: {date}",
                f"VENUE: {venue}",
                "LOCATION: Ithaca, NY",
                "END_SHOW_METADATA",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (logs / "compA.log").write_text(main_dir + r"\01 - Scarlet Begonias.flac" + "\n", encoding="utf-8")
    return main_dir


def test_research_query_classification():
    import tlo_research_lib as research

    q = research.parse_research_query("1977-05-08")
    assert (q.kind, q.date) == ("date", "1977-05-08")

    q = research.parse_research_query("Grateful Dead 1977-05-08")
    assert (q.kind, q.artist, q.date) == ("artist_date", "Grateful Dead", "1977-05-08")

    q = research.parse_research_query("Barton Hall")
    assert (q.kind, q.venue) == ("venue", "Barton Hall")


@pytest.mark.parametrize(
    "query,kind,artist,normalized",
    [
        ("xxxx-xx-xx", "date", "", "xxxx-xx-xx"),
        ("202x-xx-xx", "date", "", "202x-xx-xx"),
        ("2001-04-1x", "date", "", "2001-04-1x"),
        ("2004-0x-xx", "date", "", "2004-0x-xx"),
        ("14APR01", "date", "", "2001-04-14"),
        ("April 14, 2001", "date", "", "2001-04-14"),
        ("3/9/1972", "date", "", "1972-03-09"),
        ("19981003", "date", "", "1998-10-03"),
        ("November 2020", "date", "", "2020-11-xx"),
        ("96-98", "date", "", "1996-1998"),
        ("1977", "date", "", "1977"),
        ("Grateful Dead xxxx-xx-xx", "artist_date", "Grateful Dead", "xxxx-xx-xx"),
        ("Grateful Dead April 14, 2001", "artist_date", "Grateful Dead", "2001-04-14"),
        ("Grateful Dead 3/9/1972", "artist_date", "Grateful Dead", "1972-03-09"),
        ("Grateful Dead 19981003", "artist_date", "Grateful Dead", "1998-10-03"),
    ],
)
def test_research_accepts_canonical_tlo_date_forms(query, kind, artist, normalized):
    import tlo_research_lib as research

    parsed = research.parse_research_query(query)
    assert parsed.kind == kind
    assert parsed.artist == artist
    assert normalized in parsed.date_candidates


def test_research_ambiguous_date_form_matches_any_canonical_normalization(tmp_path):
    import tlo_research_lib as research

    _write_logs(tmp_path, artist="Artist A", date="2001-02-03", venue="Venue A", stem="A")
    logs = tmp_path / "logs"
    with (logs / "metaB.log").open("w", encoding="utf-8") as handle:
        handle.write(
            "SHOW_NAME: Artist B 2003-01-02 Venue B\n"
            "MAIN_DIR_PATH: E:\\Music\\ShowB\n"
            'MUSIC_DIRS_JSON: ["E:\\\\Music\\\\ShowB"]\n'
            "ARTIST: Artist B\n"
            "DATE: 2003-01-02\n"
            "VENUE: Venue B\n"
            "END_SHOW_METADATA\n"
        )
    (logs / "compB.log").write_text(r"E:\Music\ShowB\01.flac" + "\n", encoding="utf-8")

    output = research.research_logs(str(tmp_path), "01-02-03")
    assert "Type: date" in output
    assert "Matches: 2" in output


def test_research_finds_meta_block_and_corresponding_comp_line(tmp_path):
    import tlo_research_lib as research

    _write_logs(tmp_path)
    output = research.research_logs(str(tmp_path), "Grateful Dead 1977-05-08")
    assert "Matches: 1" in output
    assert "META LOG: metaA.log" in output
    assert "SHOW_NAME: Grateful Dead 1977-05-08 Barton Hall" in output
    assert "ARTIST: Grateful Dead" in output
    assert "DATE: 1977-05-08" in output
    assert "VENUE: Barton Hall" in output
    assert "COMP LOG:" in output
    assert r"compA.log: E:\Music\ShowA\01 - Scarlet Begonias.flac" in output


def test_research_date_and_venue_are_field_aware(tmp_path):
    import tlo_research_lib as research

    _write_logs(tmp_path, artist="Grateful Dead", date="1977-05-08", venue="Barton Hall", stem="ShowA")
    logs = tmp_path / "logs"
    with (logs / "metaB.log").open("w", encoding="utf-8") as handle:
        handle.write(
            "SHOW_NAME: Miles Davis 1977-05-08 Great American Music Hall\n"
            "MAIN_DIR_PATH: E:\\Music\\ShowB\n"
            'MUSIC_DIRS_JSON: ["E:\\\\Music\\\\ShowB"]\n'
            "ARTIST: Miles Davis\n"
            "DATE: 1977-05-08\n"
            "VENUE: Great American Music Hall\n"
            "OBSERVATION: Barton Hall appears only in unrelated prose\n"
            "END_SHOW_METADATA\n"
        )
    (logs / "compB.log").write_text(r"E:\Music\ShowB\01 - Tune.flac" + "\n", encoding="utf-8")

    date_output = research.research_logs(str(tmp_path), "1977-05-08")
    assert "Matches: 2" in date_output
    venue_output = research.research_logs(str(tmp_path), "Barton")
    assert "Matches: 1" in venue_output
    assert "Grateful Dead" in venue_output
    assert "Miles Davis" not in venue_output


def test_research_cli_uses_my_tlo_then_tlohome_then_environment(tmp_path, monkeypatch, capsys):
    cli = _load_hyphen_module("tlo-research.py", "tlo_research_build369_cli")
    env_home = tmp_path / "env"
    tlo_home = tmp_path / "explicit"
    my_home = tmp_path / "my"
    _write_logs(env_home, artist="Env Artist", stem="Env")
    _write_logs(tlo_home, artist="Explicit Artist", stem="Explicit")
    _write_logs(my_home, artist="My Artist", stem="My")
    monkeypatch.setenv("TLOHome", str(env_home))

    assert cli.main(["--TLOHome", str(tlo_home), "--myTLO", str(my_home), "1977-05-08"]) == 0
    output = capsys.readouterr().out
    assert "My Artist" in output
    assert "Explicit Artist" not in output
    assert "Env Artist" not in output

    assert cli.main(["--TLOHome", str(tlo_home), "1977-05-08"]) == 0
    output = capsys.readouterr().out
    assert "Explicit Artist" in output
    assert "Env Artist" not in output

    assert cli.main(["1977-05-08"]) == 0
    output = capsys.readouterr().out
    assert "Env Artist" in output


def test_research_cli_keeps_mytlo_compatibility_hidden_from_help():
    cli = _load_hyphen_module("tlo-research.py", "tlo_research_build369_cli_help")
    help_text = cli.build_parser().format_help()
    assert "--TLOHome" in help_text
    assert "--myTLO" not in help_text


def test_research_cli_rejects_empty_or_missing_logs(tmp_path, capsys):
    cli = _load_hyphen_module("tlo-research.py", "tlo_research_build369_cli_errors")
    assert cli.main(["--TLOHome", str(tmp_path), "Barton Hall"]) == 2
    assert "TLO log directory does not exist" in capsys.readouterr().err


def test_inventory_gui_research_button_opens_input_and_results(tmp_path, monkeypatch):
    try:
        import tkinter as tk
        root = tk.Tk()
    except Exception as exc:
        pytest.skip(f"Tk display unavailable: {exc}")

    gui = _load_hyphen_module("tlo-ggi.py", "tlo_ggi_build369_research_gui")
    _write_logs(tmp_path)
    try:
        root.withdraw()
        args = gui._parse_gui_command_line(["--TLOHome", str(tmp_path)])
        app = gui.App(root, args)
        assert app.research_button is not None
        assert "Research" in app.research_button.cget("text")

        app._open_research()
        root.update()
        research_dialogs = [
            child for child in root.winfo_children()
            if isinstance(child, tk.Toplevel) and "TLO Research" in child.title() and "Results" not in child.title()
        ]
        assert research_dialogs
        dialog = research_dialogs[-1]
        entries = []
        def collect(widget):
            for child in widget.winfo_children():
                if isinstance(child, __import__('tkinter.ttk').ttk.Entry):
                    entries.append(child)
                collect(child)
        collect(dialog)
        assert entries
        entries[0].insert(0, "Barton Hall")
        search_buttons = []
        def collect_buttons(widget):
            for child in widget.winfo_children():
                if isinstance(child, __import__('tkinter.ttk').ttk.Button) and child.cget("text") == "Search":
                    search_buttons.append(child)
                collect_buttons(child)
        collect_buttons(dialog)
        assert search_buttons
        assert str(search_buttons[0].cget("default")) == "active"
        assert dialog.bind("<Return>")

        # Return is bound at the Research Toplevel, so it remains the default
        # Search action even when focus is not in the text-entry widget.
        close_buttons = []
        def collect_close_buttons(widget):
            for child in widget.winfo_children():
                if isinstance(child, __import__('tkinter.ttk').ttk.Button) and child.cget("text") == "Close":
                    close_buttons.append(child)
                collect_close_buttons(child)
        collect_close_buttons(dialog)
        assert close_buttons
        close_buttons[0].focus_set()
        # The Toplevel-level Return binding above is the behavior contract; use
        # direct invocation here to exercise the same run_query callback without
        # depending on window-manager keyboard focus under headless Tk.
        search_buttons[0].invoke()
        root.update()

        result_windows = [
            child for child in root.winfo_children()
            if isinstance(child, tk.Toplevel) and "TLO Research Results" in child.title()
        ]
        assert result_windows
        text_widgets = []
        def collect_text(widget):
            for child in widget.winfo_children():
                if isinstance(child, tk.Text):
                    text_widgets.append(child)
                collect_text(child)
        collect_text(result_windows[-1])
        assert text_widgets

        scrollbars = []
        def collect_scrollbars(widget):
            for child in widget.winfo_children():
                if isinstance(child, __import__('tkinter.ttk').ttk.Scrollbar):
                    scrollbars.append(child)
                collect_scrollbars(child)
        collect_scrollbars(result_windows[-1])
        assert any(str(bar.cget("orient")) == "horizontal" for bar in scrollbars)
        assert text_widgets[0].cget("xscrollcommand")

        result = text_widgets[0].get("1.0", "end")
        assert "Matches: 1" in result
        assert "VENUE: Barton Hall" in result
    finally:
        root.destroy()


def test_research_reports_every_related_raw_meta_and_comp_line(tmp_path):
    """Research must keep scanning after the structured record is identified."""
    import tlo_research_lib as research

    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    query = "1976-05-05 - Pall's Mall - Boston 1976-05-05"
    original = query + " 04 05.Reidsville, NC"
    main_dir = r"E:\Music\Firefall"
    (logs / "metaA.log").write_text(
        "\n".join(
            [
                f"SOURCE_TEXT: {original}",
                "SHOW_NAME: 1976-05-05 - Pall's Mall - Boston 1976-05-05 Paul's Mall Boston, MA",
                f"MAIN_DIR_PATH: {main_dir}",
                'MUSIC_DIRS_JSON: ["E:\\\\Music\\\\Firefall"]',
                "ARTIST: 1976-05-05 - Pall's Mall - Boston",
                "DATE: 1976-05-05",
                "VENUE: Paul's Mall",
                "LOCATION: Boston, MA",
                "END_SHOW_METADATA",
                f"HISTORICAL_INPUT: {original}",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (logs / "compA.log").write_text(
        "\n".join(
            [
                main_dir + r"\01.flac",
                rf"E:\Source\{original}\01.flac",
                rf"E:\Source\{original}\02.flac",
                "",
            ]
        ),
        encoding="utf-8",
    )

    output = research.research_logs(str(tmp_path), query)
    assert "Matches: 1" in output
    assert "===== ALL RELATED RAW LOG LINES =====" in output
    assert "Raw log lines: 6" in output
    assert f"metaA.log:1: SOURCE_TEXT: {original}" in output
    assert f"metaA.log:10: HISTORICAL_INPUT: {original}" in output
    assert rf"compA.log:2: E:\Source\{original}\01.flac" in output
    assert rf"compA.log:3: E:\Source\{original}\02.flac" in output


def test_research_raw_log_hits_are_returned_even_without_structured_meta_match(tmp_path):
    import tlo_research_lib as research

    logs = tmp_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    (logs / "metaA.log").write_text(
        "SOURCE_TEXT: Mystery Artist 1976-05-05 someplace\n",
        encoding="utf-8",
    )
    (logs / "compA.log").write_text(
        r"E:\Source\Mystery Artist 1976-05-05 someplace\01.flac" + "\n",
        encoding="utf-8",
    )

    output = research.research_logs(str(tmp_path), "Mystery Artist 1976-05-05")
    assert "Matches: 0" in output
    assert "No matching metadata records found." in output
    assert "Raw log lines: 2" in output
    assert "metaA.log:1:" in output
    assert "compA.log:1:" in output
