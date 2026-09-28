"""Build 505 remediation for the v504 targeted review findings."""

__version__ = "v505"

import os
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

import tlo_copy_requests as CR
import tlo_setlist_file_selection as selection
import tlo_setlist_metadata_lookup as metadata
import tlo_setlistfm_lookup as sfm
import tlo_sibling_collections as siblings
import tlo_tree_compare as tree
from tlo_options import validate_setlistfm_upgrade_environment
from tlo_bootlist_volume_policy import write_bootlist_rows
from tests.behavior.test_build503_copy_request_direct_paths_volumes import _artist_db, _music_folder, _request, _row


def _setup(tmp_path, show_rel="Dead/show-one"):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    volume = tmp_path / "VOLROOT"
    show = "Grateful Dead 1977-05-08 Barton Hall Ithaca, NY"
    _music_folder(volume, show_rel, b"one")
    write_bootlist_rows(str(home), [_row(show, "VOL", show_rel)])
    return home, volume, show


def test_build505_direct_source_destination_overlap_is_rejected(tmp_path):
    home, volume, _show = _setup(tmp_path)
    src = volume / "Dead"
    req = _request(tmp_path, f"{src}\n")

    for destination in (src, volume):
        rid = CR.create_or_open_request(str(home), str(req), str(destination))["request_id"]
        result = CR.copy_available(str(home), rid, roots={"vol": [str(volume)]})
        assert not result.copied
        assert not result.already_satisfied
        assert any("must not overlap" in reason for _item, reason in result.failures)


def test_build505_normal_show_target_equal_to_source_is_not_completed(tmp_path):
    home, volume, show = _setup(tmp_path)
    req = _request(tmp_path, "Grateful Dead\n")
    rid = CR.create_or_open_request(str(home), str(req), str(volume / "Dead"))["request_id"]
    result = CR.copy_available(str(home), rid, roots={"vol": [str(volume)]})
    assert not result.copied
    assert not result.already_satisfied
    assert any("already is the source" in reason for item, reason in result.failures if item == show)
    assert CR.evaluate_request(str(home), rid, roots={"vol": [str(volume)]}).status != CR.STATUS_COMPLETE


def test_build505_volume_artist_collision_requires_brackets(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    show = "Miles Davis 1970-04-10 Fillmore West San Francisco, CA"
    matcher = CR._load_matcher(str(home))

    bare = CR.parse_request_items("Miles\n", [show], matcher, ["Miles"])[0]
    assert bare.kind == "invalid"
    assert "Use [Miles]" in bare.error

    bracketed = CR.parse_request_items("[Miles]\n", [show], matcher, ["Miles"])[0]
    assert bracketed.kind == "volume"


def test_build505_shared_setlist_decoder_handles_even_cp1252_and_scored_readers(tmp_path):
    raw = "Grateful Dead\nCaf\xe9 Wha?, New York, NY\n1977-05-08\n\n".encode("cp1252")
    assert len(raw) % 2 == 0
    path = tmp_path / "s.txt"
    path.write_bytes(raw)

    text, encoding = metadata._read_text_file(str(path))
    assert encoding == "shared"
    assert "Grateful Dead" in text
    assert "Café Wha?" in text

    selected, _quality = selection._decode_text_sample_bytes(raw)
    assert "Grateful Dead" in selected
    assert "Café Wha?" in selected
    assert "Grateful Dead" in siblings._decode_bytes(raw)


def test_build505_date_fallback_uses_bounded_shared_txt_rtf_docx_reader(tmp_path):
    import tlo_phase23_v2 as phase23

    txt = tmp_path / "s.txt"
    txt.write_bytes("Grateful Dead\nCaf\xe9 Wha?, NYC\n1977-05-08\n".encode("cp1252"))
    assert "1977-05-08" in phase23._read_text_for_date_fallback(str(txt))

    rtf = tmp_path / "s.rtf"
    rtf.write_text(r"{\rtf1\ansi Grateful Dead\par 1977-05-08\par}", encoding="ascii")
    rtf_text = phase23._read_text_for_date_fallback(str(rtf))
    assert "1977-05-08" in rtf_text
    assert "\\par" not in rtf_text

    docx = tmp_path / "s.docx"
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
        '<w:p><w:r><w:t>Grateful Dead</w:t></w:r></w:p>'
        '<w:p><w:r><w:t>1977-05-08</w:t></w:r></w:p>'
        '</w:body></w:document>'
    ).encode("utf-8")
    with zipfile.ZipFile(docx, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
    docx_text = phase23._read_text_for_date_fallback(str(docx))
    assert "Grateful Dead" in docx_text
    assert "1977-05-08" in docx_text
    assert not docx_text.startswith("PK")


def test_build505_tree_walks_fail_closed_on_unreadable_subdir(tmp_path, monkeypatch):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    (src / "a").mkdir(parents=True)
    (src / "locked").mkdir()
    (src / "a" / "x.flac").write_bytes(b"1")
    (src / "locked" / "y.flac").write_bytes(b"2")
    (dst / "a").mkdir(parents=True)
    (dst / "locked").mkdir()
    (dst / "a" / "x.flac").write_bytes(b"1")

    real = os.scandir

    def denied(path="."):
        if str(path).endswith("locked"):
            raise PermissionError(13, "denied", str(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", denied)
    assert tree.directory_trees_exactly_match(str(src), str(dst)) is False
    with pytest.raises(CR.CopyRequestError, match="Cannot enumerate source tree"):
        CR._walk_tree_size_and_reject_links(str(src))


def test_build505_whole_volume_excludes_os_root_folders_consistently(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    _artist_db(home)
    volume = tmp_path / "VOLROOT"
    _music_folder(volume, "Dead/show", b"music")
    system = volume / "System Volume Information"
    system.mkdir()
    (system / "secret.bin").write_bytes(b"do-not-copy")
    dest = tmp_path / "dest"
    dest.mkdir()
    req = _request(tmp_path, "[VOL]\n")
    rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]

    real = os.scandir

    def denied(path="."):
        if str(path).endswith("System Volume Information"):
            raise PermissionError(13, "denied", str(path))
        return real(path)

    monkeypatch.setattr(os, "scandir", denied)
    evaluation, required, _free, errors = CR.preview_request(str(home), rid, roots={"vol": [str(volume)]})
    assert not errors
    assert required == len(b"music")
    assert evaluation.preview_notes and "system volume information" in evaluation.preview_notes[0]

    result = CR.copy_available(str(home), rid, roots={"vol": [str(volume)]})
    assert len(result.copied) == 1
    target = dest / "VOL"
    assert (target / "Dead" / "show" / "track01.flac").read_bytes() == b"music"
    assert not (target / "System Volume Information").exists()


def test_build505_upgrade_key_must_match_normal_key_and_is_inert_without_lookup(monkeypatch):
    monkeypatch.setenv(sfm.ENV_API_KEY, "normal")
    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "different")
    assert sfm.upgrade_api_key_available() is False
    with pytest.raises(ValueError, match="same setlist.fm API key"):
        validate_setlistfm_upgrade_environment({"setlistfm_lookup": True, "setlistfm_upgrade": True})

    validate_setlistfm_upgrade_environment({"setlistfm_lookup": False, "setlistfm_upgrade": True})
    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "normal")
    assert sfm.upgrade_api_key_available() is True


def test_build505_process_environment_precedes_persisted_windows_fallback(monkeypatch):
    monkeypatch.setenv(sfm.ENV_API_KEY, "session")
    monkeypatch.setenv(sfm.ENV_UPGRADE_API_KEY, "session")
    persisted = {sfm.ENV_API_KEY: "persisted", sfm.ENV_UPGRADE_API_KEY: "persisted"}
    monkeypatch.setattr(sfm, "_persistent_windows_environment_value", lambda name: persisted.get(name, ""))
    assert sfm.get_api_key() == "session"
    assert sfm.upgrade_api_key_available() is True


def test_build505_stale_copy_temp_is_swept_before_pass(tmp_path):
    home, volume, _show = _setup(tmp_path)
    dest = tmp_path / "dest"
    dest.mkdir()
    stale = dest / ".tlo-copy-stale"
    stale.mkdir()
    (stale / CR.COPY_TEMP_MARKER_FILENAME).write_text('{"request_id":"legacy"}\n', encoding="utf-8")
    (stale / "junk").write_bytes(b"x")
    req = _request(tmp_path, "Grateful Dead\n")
    rid = CR.create_or_open_request(str(home), str(req), str(dest))["request_id"]
    result = CR.copy_available(str(home), rid, roots={"vol": [str(volume)]})
    assert result.copied
    assert not stale.exists()


def test_build505_review_documentation_and_packaging_cleanup():
    from docx import Document
    import re

    root = Path(__file__).resolve().parents[2]
    doc = Document(root / "TLO_Inventory_Requirements_Working_v511.docx")
    paragraphs = [p.text for p in doc.paragraphs]
    sec20 = next(i for i, text in enumerate(paragraphs) if text.startswith("20. Destructive Operations Safety"))
    revision = next(i for i, text in enumerate(paragraphs) if text.startswith("21. Revision Index"))
    appendix_a = next(i for i, text in enumerate(paragraphs) if text.startswith("Appendix A -"))
    assert sec20 < revision < appendix_a
    assert paragraphs[revision] == "21. Revision Index (Build 398-511)"
    assert not any(re.search(r"\bBuild\s+\d+", text) for text in paragraphs[:revision])
    req = "\n".join(paragraphs)
    assert "BOM-marked UTF-16 and NUL-dominant BOM-less UTF-16 LE/BE must be recognized before UTF-8" in req
    assert "must be written explicitly as [Volume]" in req
    assert "Destination must not be the same path as a requested source" in req
    assert "exactly the same API key value as SETLISTFM_API_KEY" in req
    assert "Delete extra tags" not in req

    manual = (root / "TLO_Inventory_User_Manual_v511.rtf").read_text(encoding="utf-8", errors="ignore")
    assert manual.rfind("Build 500:") < manual.rfind("Build 501:") < manual.rfind("Build 502:") < manual.rfind("Build 503:") < manual.rfind("Build 504") < manual.rfind("Build 505")
    assert "ambiguous and you must write [Volume] explicitly" in manual
    assert "System Volume Information" in manual
    assert "Delete extra tags" not in manual

    faq = (root / "TLO-FAQ.txt").read_text(encoding="utf-8")
    assert "Are there Copy Request source/Destination or whole-volume safety rules?" in faq
    assert "Delete extra tags" not in faq

    assert not list(root.glob("SHA256SUMS_v50[0-4].txt"))
    assert not list(root.glob("BUILD_VERIFICATION_v50[0-4].txt"))
    with zipfile.ZipFile(root / "old-change-logs.zip") as zf:
        names = set(zf.namelist())
    for build in range(500, 505):
        assert f"superseded-verification/SHA256SUMS_v{build}.txt" in names
        assert f"superseded-verification/BUILD_VERIFICATION_v{build}.txt" in names
