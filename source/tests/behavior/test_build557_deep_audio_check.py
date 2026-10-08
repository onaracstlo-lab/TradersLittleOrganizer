"""Build 557 regressions for opt-in complete-stream audio decoding."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
from mutagen.flac import FLAC

import tlo_corruption as corruption
import tlo_options
import tlo_tag_lib as taglib
from tlo_ux import main_window_checkbox_values, operation_review_lines

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]
FLAC_FIXTURE = ROOT / "tests" / "fixtures" / "build543_silence.flac"


def _load_script(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _copy_flac(tmp_path: Path, name: str = "track.flac") -> Path:
    target = tmp_path / name
    shutil.copy2(FLAC_FIXTURE, target)
    return target


def test_build557_option_is_default_off_and_positioned_under_proper_grammar():
    proper = tlo_options.OPTIONS_BY_FIELD["proper_grammar"]
    deep = tlo_options.OPTIONS_BY_FIELD["deep_audio_check"]
    artist_album = tlo_options.OPTIONS_BY_FIELD["artist_in_album"]
    assert deep.flag == "--deep-audio-check"
    assert deep.default is False
    assert deep.gui_label == "Deep Audio Check"
    assert deep.gui_col == proper.gui_col == 1
    assert deep.gui_row == proper.gui_row + 1
    checked_defaults = {
        option.config_field for option in tlo_options.GUI_CHECKBOX_OPTIONS if bool(option.default)
    }
    assert checked_defaults == {artist_album.config_field}


def test_build557_main_and_standalone_tag_cli_accept_deep_audio_check():
    main = _load_script("tlo_main_build557", "tlo-main.py")
    args = main._parse_gui_command_line(["--deep-audio-check"])
    assert args.deep_audio_check is True

    tag = _load_script("tlo_tag_build557", "tlo-tag.py")
    args = tag._parse_args(["--deep-audio-check", "/tmp"])
    assert args.deep_audio_check is True


def test_build557_review_operation_and_run_settings_source_show_deep_audio_check(tmp_path):
    config = SimpleNamespace(
        deep_audio_check=True,
        artist_in_album=True,
        corrupt_files="keep",
        corrupt_folders="never",
        corrupt_folder_threshold=100,
        performance_mode="balanced",
        max_workers=2,
        search_path_override=str(tmp_path),
    )
    values = main_window_checkbox_values(config, dry_run=False)
    assert values["deep_audio_check"] is True
    lines = operation_review_lines(config, operation="Full Inventory", dry_run=False)
    assert "  Deep Audio Check: Yes" in lines


def test_build557_deep_disabled_never_calls_decoder(monkeypatch, tmp_path):
    path = _copy_flac(tmp_path)
    monkeypatch.setattr(
        corruption,
        "_deep_audio_stream_status",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("decoder must stay off")),
    )
    bad, unverifiable = corruption.classify_audio_paths([str(path)], deep_audio_check=False)
    assert bad == []
    assert unverifiable == []


def test_build557_deep_decode_failure_is_corruption(monkeypatch, tmp_path):
    path = _copy_flac(tmp_path)
    monkeypatch.setattr(corruption, "_deep_audio_stream_status", lambda *_args, **_kwargs: False)
    bad, unverifiable = corruption.classify_audio_paths([str(path)], deep_audio_check=True)
    assert bad == [str(path)]
    assert unverifiable == []


def test_build557_decoder_unavailable_is_unverifiable(monkeypatch, tmp_path):
    path = _copy_flac(tmp_path)
    monkeypatch.setattr(corruption, "_deep_audio_stream_status", lambda *_args, **_kwargs: None)
    bad, unverifiable = corruption.classify_audio_paths([str(path)], deep_audio_check=True)
    assert bad == []
    assert len(unverifiable) == 1
    assert unverifiable[0][0] == str(path)
    assert "DeepAudioCheckUnverifiable" in unverifiable[0][1]


def test_build557_tagging_plus_deep_runs_tag_probe_then_decoder(monkeypatch, tmp_path):
    path = _copy_flac(tmp_path)
    calls = []
    monkeypatch.setattr(corruption, "_validate_tag_write_round_trip", lambda p: calls.append(("tag", p)))
    monkeypatch.setattr(corruption, "_deep_audio_stream_status", lambda p: calls.append(("deep", p)) or True)
    bad, unverifiable = corruption.classify_audio_paths(
        [str(path)], check_tag_write=True, deep_audio_check=True
    )
    assert bad == []
    assert unverifiable == []
    assert calls == [("tag", str(path)), ("deep", str(path))]


def test_build557_ffmpeg_command_is_local_file_only_and_full_stream(tmp_path):
    path = _copy_flac(tmp_path)
    captured = {}

    class Proc:
        returncode = 0
        def poll(self):
            return 0
        def communicate(self):
            return ("", "")
        def kill(self):
            raise AssertionError("clean decoder should not be killed")

    def fake_popen(command, **kwargs):
        captured["command"] = list(command)
        captured["kwargs"] = kwargs
        # Build 566 emits a framehash sample record for FLAC so successful
        # decoding alone does not falsely accept missing final frames.
        samples = FLAC(path).info.total_samples
        kwargs["stdout"].write(
            f"#tb 0: 1/44100\n#codec_id 0: pcm_s16le\n"
            f"0, 0, 0, {samples}, {samples * 2}, abcdef\n".encode("ascii")
        )
        return Proc()

    status = corruption._deep_audio_stream_status(
        str(path), ffmpeg_executable="/app/ffmpeg", popen_factory=fake_popen,
        cancel_check=lambda: False, timeout_seconds=10,
    )
    assert status is True
    command = captured["command"]
    input_index = command.index("-i")
    assert command[input_index - 2:input_index] == ["-protocol_whitelist", "file"]
    assert command[command.index("-protocol_whitelist") + 1] == "file"
    assert command[input_index + 1] == str(path.resolve())
    assert command[command.index("-map") + 1] == "0:a:0"
    assert command[-3:] == ["-f", "framemd5", "-"]
    assert "-xerror" in command
    assert captured["kwargs"]["env"]["LC_ALL"] == "C"


def test_build557_real_truncated_flac_passes_header_but_fails_full_decode(tmp_path):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        pytest.skip("system ffmpeg unavailable for independent deep-decode regression")
    intact = tmp_path / "tone.flac"
    subprocess.run(
        [ffmpeg, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=2", "-c:a", "flac", str(intact)],
        check=True,
    )
    truncated = tmp_path / "truncated.flac"
    data = intact.read_bytes()
    truncated.write_bytes(data[: len(data) // 2])

    # The Build 553 finding: Mutagen can still parse this truncated file.
    FLAC(truncated)
    assert corruption._deep_audio_stream_status(
        str(intact), ffmpeg_executable=ffmpeg, cancel_check=lambda: False, timeout_seconds=20
    ) is True
    assert corruption._deep_audio_stream_status(
        str(truncated), ffmpeg_executable=ffmpeg, cancel_check=lambda: False, timeout_seconds=20
    ) is False


def test_build557_inventory_and_standalone_tagger_propagate_deep_flag(monkeypatch, tmp_path):
    # Inventory propagation is kept at the direct pre-mutation boundary.
    source = (ROOT / "tlo_phase23_v2.py").read_text(encoding="utf-8")
    assert 'deep_audio_check=bool(getattr(config, "deep_audio_check", False))' in source

    captured = {}
    record = SimpleNamespace(main_dir_path=str(tmp_path), artist="", show_name="")
    config = taglib.build_tagger_config(tlo_home=str(tmp_path), corrupt_files="keep", deep_audio_check=True)
    monkeypatch.setattr(taglib, "_extract_metadata_for_group", lambda *_args, **_kwargs: (record, [], []))

    class RemovedOutcome:
        show_removed = True
        unverifiable = False

    import tlo_corruption
    def fake_handle(_config, _group, _record, **kwargs):
        captured.update(kwargs)
        return RemovedOutcome()
    monkeypatch.setattr(tlo_corruption, "handle_group_corruption", fake_handle)
    stats = taglib.process_tagging_group(
        config, {"main_dir_path": str(tmp_path), "music_dirs": [str(tmp_path)]}, object(), emit=lambda _text: None
    )
    assert stats["skipped"] == 1
    assert captured["check_tag_write"] is True
    assert captured["deep_audio_check"] is True
