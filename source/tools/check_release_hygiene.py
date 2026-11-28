#!/usr/bin/env python3
"""Conservative local release hygiene preflight (Ruff remains authoritative)."""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET


# The independently versioned release-readiness gate (Process v170) reserves
# this exact map for the Build 681 review. New reviews use separate sections.
BUILD_681_FINDINGS = frozenset(
    ('H1', 'H2', 'H3')
    + tuple(f'M{i}' for i in range(1, 9))
    + tuple(f'L{i}' for i in range(1, 11))
    + tuple(f'T{i}' for i in range(1, 5))
)


def remediation_evidence_errors(evidence: object, root: Path, build: int) -> list[str]:
    """Catch source-owned remediation mistakes before packaging/upload."""
    if not isinstance(evidence, dict):
        return ['Remediation evidence must be a JSON object']
    errors = []
    if evidence.get('build') != build:
        errors.append('Remediation evidence build mismatch')
    records = evidence.get('findings')
    if not isinstance(records, dict):
        return errors + ['Remediation findings must be a JSON object']
    if set(records) != BUILD_681_FINDINGS:
        missing = sorted(BUILD_681_FINDINGS - set(records))
        extra = sorted(set(records) - BUILD_681_FINDINGS)
        errors.append(f'Each Build 681 review ID needs an explicit disposition; missing={missing}, extra={extra}')
    for issue in sorted(BUILD_681_FINDINGS):
        rec = records.get(issue)
        if not isinstance(rec, dict):
            errors.append(f'{issue}: disposition must be a JSON object')
            continue
        status = rec.get('status')
        if status not in ('fixed', 'deferred', 'accepted-design'):
            errors.append(f'{issue}: invalid status')
        elif issue in ('H1', 'H2', 'H3') and status != 'fixed':
            errors.append(f'{issue}: high-severity safety issue must be fixed')
        if status in ('deferred', 'accepted-design'):
            if not isinstance(rec.get('rationale'), str) or not rec['rationale'].strip():
                errors.append(f'{issue}: document rationale for {status}')
            continue
        if status != 'fixed':
            continue
        node = rec.get('test')
        match = re.fullmatch(r'(tests/[^:]+\.py)::(test_[A-Za-z0-9_]+)', node) if isinstance(node, str) else None
        if not match:
            errors.append(f'{issue}: fixed finding needs an executable pytest node ID')
            continue
        path = (root / match[1]).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append(f'{issue}: missing cited regression test file {match[1]}')
            continue
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'))
        except (OSError, UnicodeError, SyntaxError) as exc:
            errors.append(f'{issue}: cannot parse cited regression: {exc}')
            continue
        if not any(isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == match[2]
                   for n in ast.walk(tree)):
            errors.append(f'{issue}: missing actual pytest function {match[2]}')
    return errors


def verify(root: Path, build: int) -> list[str]:
    errors = []
    try:
        evidence = json.loads((root / 'TLO_RELEASE_REMEDIATION.json').read_text(encoding='utf-8'))
    except (OSError, ValueError, UnicodeError) as exc:
        errors.append(f'Cannot read remediation evidence: {exc}')
    else:
        errors.extend(remediation_evidence_errors(evidence, root, build))
    suffix = f'v{build}'
    for pattern in ('TLO_Inventory_Requirements_Working_v*.docx',
                    'TLO_Inventory_User_Manual_v*.rtf',
                    'TLO_Requirements_Catalog_v*.csv',
                    'BUILD_VERIFICATION_v*.txt', 'CHANGES_v*.txt',
                    'REGRESSION_RESULTS_v*.txt', 'SOURCE_BUNDLE_README_v*.txt',
                    'RELEASE_NOTES_v*.txt', 'SHA256SUMS_v*.txt'):
        for path in root.glob(pattern):
            if suffix not in path.name:
                errors.append(f'stale current-root filename: {path.name}')
    requirements = root / f'TLO_Inventory_Requirements_Working_{suffix}.docx'
    manual = root / f'TLO_Inventory_User_Manual_{suffix}.rtf'
    if not (requirements.exists() and manual.exists()):
        errors.append('missing current Requirements or User Manual')
    else:
        with ZipFile(requirements) as arc:
            doc = ET.fromstring(arc.read('word/document.xml'))
            ns = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
            text = '\n'.join(''.join(t.text or '' for t in p.iter(ns + 't')) for p in doc.iter(ns+'p'))
            core = ET.fromstring(arc.read('docProps/core.xml'))
        manual_text = manual.read_bytes().decode('latin-1')
        if f'Current document version: {suffix}' not in text:
            errors.append('requirements current version content mismatches build')
        if f'Build {build}' not in ''.join(core.itertext()):
            errors.append('requirements core properties mismatch build')
        if f'Version v1.7 Build {build}' not in manual_text:
            errors.append('manual current version content mismatches build')
        if f'TLO Inventory User Manual {suffix}' not in manual_text:
            errors.append('manual metadata mismatches build')
        # The RTF core properties can be stale even when title and body are
        # updated. The GUI/build readers do not check this metadata for us.
        keywords = re.search(r'\\keywords[^}]*', manual_text)
        if keywords and re.search(r'Build,\s*\d+', keywords.group()) and f'Build, {build}' not in keywords.group():
            errors.append('manual keyword metadata references another build')
        property_version = re.search(r'OOXMLCorePropertyVersion}.*?\\staticval\s+(\d+)', manual_text, flags=re.S)
        if property_version and property_version.group(1) != str(build):
            errors.append('manual revision metadata references another build')
        for label,contents in [('requirements',text),('manual',manual_text)]:
            if re.search(rf'(?<!\d)(?:v{build-1}|Build {build-1})(?!\d)',contents):
                errors.append(f'{label}: previous-build reference in current text')
    # This AST check catches ordinary unused imports in test modules in an
    # offline environment. Ruff F401 is still mandatory on Windows CI.
    for path in sorted((root/'tests').rglob('test_*.py')):
        try:
            tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        except (SyntaxError,UnicodeError) as exc:
            errors.append(f'{path}: {exc}')
            continue
        used = {n.id for n in ast.walk(tree) if isinstance(n,ast.Name) and isinstance(n.ctx,ast.Load)}
        for node in tree.body:
            if isinstance(node,ast.Import):
                imported=[(alias.asname or alias.name.split('.')[0],node.lineno) for alias in node.names]
            elif isinstance(node,ast.ImportFrom) and node.module != '__future__':
                imported=[(alias.asname or alias.name,node.lineno) for alias in node.names if alias.name!='*']
            else:
                continue
            for name,line in imported:
                if name not in used:
                    errors.append(f'{path.relative_to(root)}:{line}: possibly unused import {name}')
    return errors


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root',type=Path,required=True)
    parser.add_argument('--build-number',type=int,required=True)
    args=parser.parse_args()
    errors=verify(args.source_root,args.build_number)
    for problem in errors:
        print('FAIL: '+problem)
    if errors:
        return 1
    print(f'PASS: Build {args.build_number} current documents/metadata, root version names and test import-use AST check; Ruff still required in native CI')
    return 0


if __name__=='__main__':
    sys.exit(main())
