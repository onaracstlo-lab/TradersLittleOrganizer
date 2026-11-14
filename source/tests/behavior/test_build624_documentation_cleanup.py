"""Build 624: current release documentation, metadata and history hygiene."""
from pathlib import Path
import re

import pytest
from docx import Document

import tlo_version as version

pytestmark = pytest.mark.behavior
ROOT = Path(__file__).resolve().parents[2]


def test_only_one_current_checksum_manifest_and_report():
    for base in ('SHA256SUMS', 'BUILD_VERIFICATION', 'REGRESSION_RESULTS'):
        found = [p.name for p in ROOT.glob(f'{base}_v*.txt')]
        # The checksum manifest is created only after source tests complete.
        assert found == [f'{base}_v{version.BUNDLE_BUILD}.txt'] or (base == 'SHA256SUMS' and not found)


def test_readme_names_the_correct_current_changes_and_separate_build_process():
    text = (ROOT / f'SOURCE_BUNDLE_README_v{version.BUNDLE_BUILD}.txt').read_text(encoding='utf-8')
    assert 'Build 622: Artist, City Date parsing requires positive city-reference evidence' in text
    assert 'Build 623: SHN conversion' in text
    assert 'Build 624 is a documentation-only consolidation' in text
    assert 'GitHub Build Process: v133' in text
    assert 'No GitHub Build Process artifact is included in this source bundle.' in text


def test_ffmpeg_packaging_note_is_source_build_not_precompiled_download():
    text = (ROOT / 'PYINSTALLER_NOTES.txt').read_text(encoding='utf-8')
    assert 'source-built' in text
    assert 'No prebuilt FFmpeg static release asset is downloaded' in text
    assert 'PyInstaller 6.22.3' in text


def test_faq_is_version_neutral_and_manual_rtf_has_no_bad_apostrophe():
    faq = (ROOT / 'TLO-FAQ.txt').read_text(encoding='utf-8')
    assert 'GitHub native build-process note:' in faq
    assert 'TLO GitHub Build Process v122' not in faq
    manual = (ROOT / f'TLO_Inventory_User_Manual_v{version.BUNDLE_BUILD}.rtf').read_text(encoding='utf-8')
    assert r"O\'er" not in manual
    assert "What's New" in manual
    assert f'Version {version.DISPLAY_VERSION}' in manual
    assert rf'\title TLO Inventory User Manual v{version.BUNDLE_BUILD}' in manual
    assert 'Edit Preferences' in manual


def test_requirements_archive_separated_from_current_sections():
    doc = Document(ROOT / f'TLO_Inventory_Requirements_Working_v{version.BUNDLE_BUILD}.docx')
    headings = [(p.style.name, p.text) for p in doc.paragraphs]
    assert ('Heading 1', 'Appendix K - Historical Build Amendments (Reference Only)') in headings
    assert ('Heading 2', '14.8 Persistent Preferences and Edit Preferences') in headings
    assert ('Heading 2', '20.1 Verified SHN conversion and original retention') in headings
    for style, label in headings:
        if re.match(r'Build 55[7-9]:|Build 56[0-4]:', label):
            assert style != 'Heading 1'
    assert doc.core_properties.title == f'TLO Inventory Requirements - {version.DISPLAY_VERSION}'


def test_ffmpeg_redundancy_eliminated_and_archive_preserved():
    doc = Document(ROOT / f'TLO_Inventory_Requirements_Working_v{version.BUNDLE_BUILD}.docx')
    assert sum('FFmpeg redistribution: TLO native packages must not include binaries configured with' in p.text
               for p in doc.paragraphs) == 1
    assert not (ROOT / 'old-change-logs.zip').exists()
    assert 'Historical record: CHANGES_v363.txt' in (ROOT / f'CHANGES_v{version.BUNDLE_BUILD}.txt').read_text(encoding='utf-8')
