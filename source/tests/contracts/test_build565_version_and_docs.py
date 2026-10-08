"""The only build-number/current-release contract; historical suites test behavior."""
from __future__ import annotations

import ast
from pathlib import Path
import zipfile

import pytest
from docx import Document

import tlo_version as V
from tests import _release_artifacts as A

pytestmark=pytest.mark.contract
ROOT=Path(__file__).resolve().parents[2]


def test_canonical_version_and_source_stamp_contract():
    assert V.VERSION == f'v{V.BUNDLE_BUILD}'
    assert V.DISPLAY_VERSION == f'v{V.PUBLIC_VERSION} Build {V.BUNDLE_BUILD}'
    assert V.__version__ == V.VERSION
    counted=0
    for file in ROOT.glob('*.py'):
        if file.name in {'conftest.py', 'test_tlo_requirements.py'}:
            continue
        tree=ast.parse(file.read_text(encoding='utf8'))
        if file.name in {'tlo_version.py', 'build_tlo_release.py'}:
            continue
        assert any(isinstance(node,ast.ImportFrom) and node.module=='tlo_version'
                   and any(alias.name=='VERSION' and alias.asname=='_TLO_CANONICAL_VERSION' for alias in node.names)
                   for node in tree.body),file.name
        assert any(isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='__version__' for t in node.targets)
                   and isinstance(node.value,ast.Name) and node.value.id=='_TLO_CANONICAL_VERSION'
                   for node in tree.body),file.name
        counted+=1
    assert counted >= 60


def test_canonical_current_artifacts_and_manual_version():
    assert (ROOT / A.REQUIREMENTS_FILENAME).is_file()
    assert (ROOT / A.MANUAL_FILENAME).is_file()
    assert (ROOT / A.CHANGES_FILENAME).is_file()
    assert (ROOT / A.SOURCE_README_FILENAME).is_file()
    assert (ROOT / A.BUILD_VERIFICATION_FILENAME).is_file()
    requirements='\n'.join(p.text for p in Document(ROOT / A.REQUIREMENTS_FILENAME).paragraphs)
    assert f'Current document version: {V.VERSION} (TLO {"v"+V.PUBLIC_VERSION}).' in requirements
    assert f'21. Revision Index (Build 398-{V.BUNDLE_BUILD})' in requirements
    for appendix in 'ABCDEFGHIJ':
        assert f'Appendix {appendix} -' in requirements
    manual=(ROOT / A.MANUAL_FILENAME).read_text(encoding='utf8')
    assert f'Version {V.DISPLAY_VERSION}' in manual
    assert 'Release history' in manual
    assert 'Build history (selected changes)' not in manual
    assert (ROOT / A.CHANGES_FILENAME).read_text().startswith(f'TLO {V.DISPLAY_VERSION}')


def test_current_bundle_has_no_orphaned_loose_graphics():
    assert not list(ROOT.glob('pict00[1-4].png'))
    with zipfile.ZipFile(ROOT/'old-change-logs.zip') as z:
        assert len(z.namelist())>0
