"""Test the actual WiX source and read-only runtime contract; runnable with unittest."""
from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import pytest
import xml.etree.ElementTree as ET

from msi.generate_wix import MANAGED_DATABASES, NS, generate, stable_guid
from tlo_cities import catalog_for_tlo, catalog_path_for_tlo
from tlo_city_sqlite import corrected_city, resolve_city
from tlo_db_validation import optional_database_status
from tlo_venue_sqlite import get_matcher
from tlo_version import BUNDLE_BUILD
import tlo_msi_install_mode

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]
NSMAP = {"w": NS}


class TestInstalledDatabaseOwnership(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.program = self.root / "program"
        self.program.mkdir()
        self.home = self.root / "data home"
        self.home.mkdir()

    def generate_xml(self, number):
        stage = self.program
        (stage / "tlo-main.exe").write_bytes(b"signed placeholder")
        db = stage / "TLO_DBs"
        db.mkdir(exist_ok=True)
        for name in MANAGED_DATABASES:
            (db / name).write_bytes(name.encode())
        output = self.root / f"test-{number}.wxs"
        generate(stage, output, f"1.7.{number}")
        return ET.parse(output).getroot()

    def test_installer_file_table_targets_selected_home_not_program(self):
        root = self.generate_xml(BUNDLE_BUILD)
        db = root.find(".//w:Directory[@Id='TLODATAFOLDER']/w:Directory[@Id='TLODATABASEFOLDER']", NSMAP)
        self.assertIsNotNone(db)
        files = db.findall(".//w:File", NSMAP)
        self.assertEqual({Path(node.get("Source")).name for node in files}, set(MANAGED_DATABASES))
        self.assertEqual(len(files), 4)
        program = root.find(".//w:Directory[@Id='INSTALLFOLDER']", NSMAP)
        self.assertFalse(any(Path(node.get("Source")).name in MANAGED_DATABASES
                             for node in program.findall(".//w:File", NSMAP)))
        self.assertFalse(db.findall(".//w:RemoveFile", NSMAP))
        self.assertFalse(root.findall(".//w:RemoveFolder[@Directory='TLODATAFOLDER']", NSMAP))

    def test_database_components_are_migrated_and_have_stable_new_identity(self):
        def components(root):
            db = root.find(".//w:Directory[@Id='TLODATABASEFOLDER']", NSMAP)
            return {Path(c.find("w:File", NSMAP).get("Source")).name: c
                    for c in db.findall("w:Component", NSMAP) if c.find("w:File", NSMAP) is not None}
        first = components(self.generate_xml(BUNDLE_BUILD))
        second = components(self.generate_xml(BUNDLE_BUILD + 1))
        for name, c in first.items():
            self.assertNotEqual(c.get("Guid"), stable_guid("file/TLO_DBs/" + name))
            self.assertEqual(c.get("Guid"), second[name].get("Guid"))
            self.assertNotEqual(c.get("Permanent"), "yes")
            self.assertIsNotNone(c.find("w:RegistryValue[@Root='HKCU'][@KeyPath='yes']", NSMAP))

    def test_install_overwrites_unversioned_owned_files_and_honors_explicit_path(self):
        root = self.generate_xml(BUNDLE_BUILD)
        self.assertEqual(root.find(".//w:Property[@Id='REINSTALLMODE']", NSMAP).get("Value"), "amus")
        self.assertEqual(root.find(".//w:Property[@Id='TLODATAFOLDER']", NSMAP).get("Secure"), "yes")
        for choice in ("Existing", "Legacy", "Default"):
            action = root.find(f".//w:SetDirectory[@Action='SetTLOData{choice}']", NSMAP)
            self.assertIn("NOT TLODATAFOLDER", action.get("Condition"))
        self.assertIn("Installed AND TLOLEGACYHOME", root.find(
            ".//w:SetDirectory[@Action='SetTLODataInstalled']", NSMAP).get("Condition"))

    def test_unexpected_data_payload_rejected(self):
        self.generate_xml(BUNDLE_BUILD)
        (self.program / "TLO_DBs" / "user-inventory.csv").write_text("must not be installed")
        with self.assertRaisesRegex(ValueError, "Unexpected MSI data payload"):
            generate(self.program, self.root / "bad.wxs", f"1.7.{BUNDLE_BUILD}")

    def test_missing_runtime_data_never_uses_executable_or_writes_files(self):
        db = self.program / "TLO_DBs"
        db.mkdir()
        shutil.copyfile(ROOT / "TLO_DBs/cities.sqlite", db / "cities.sqlite")
        shutil.copyfile(ROOT / "TLO_DBs/venues.sqlite", db / "venues.sqlite")
        selected = self.home / "TLO_DBs"
        self.assertEqual(catalog_path_for_tlo(tlo_home=str(self.home)), selected / "cities.sqlite")
        self.assertIsNone(catalog_for_tlo(str(selected)))
        self.assertIsNone(resolve_city("San Fransisco", "CA", str(selected)))
        self.assertIsNone(get_matcher(str(selected)))
        self.assertFalse(selected.exists())
        self.assertFalse(hasattr(tlo_msi_install_mode, "seed_msi_data_home"))
        self.assertFalse(hasattr(tlo_msi_install_mode, "ensure_msi_tlo_home"))
        messages = list(optional_database_status(SimpleNamespace(tlo_dbs_dir=str(selected))))
        self.assertEqual(len(messages), 2)
        self.assertTrue(all("WARNING" in msg and str(selected) in msg for msg in messages))

    def test_both_city_lookups_and_venue_use_installed_home_read_only(self):
        selected = self.home / "TLO_DBs"
        selected.mkdir()
        names = ("cities.sqlite", "venues.sqlite")
        for name in names:
            shutil.copyfile(ROOT / "TLO_DBs" / name, selected / name)
        hashes = {name: hashlib.sha256((selected / name).read_bytes()).hexdigest() for name in names}
        self.assertIsNotNone(catalog_for_tlo(tlo_home=str(self.home)).lookup_exact("London"))
        self.assertEqual(corrected_city("San Fransisco", "CA", "USA", str(selected)), "San Francisco")
        self.assertEqual(corrected_city("Unknownshire", "NH", "USA", str(selected)), "Unknownshire")
        self.assertIsNotNone(get_matcher(str(selected)))
        messages = list(optional_database_status(SimpleNamespace(tlo_dbs_dir=str(selected))))
        self.assertTrue(all("Reference database available" in msg for msg in messages))
        self.assertEqual(hashes, {name: hashlib.sha256((selected / name).read_bytes()).hexdigest() for name in names})
        self.assertEqual({p.name for p in selected.iterdir()}, set(names))
        # Ensure the adapter releases its read-only Windows handle before temp cleanup.
        from tlo_city_sqlite import _THREAD
        if getattr(_THREAD, "matcher", None) is not None:
            _THREAD.matcher.close()
            _THREAD.matcher = None
            _THREAD.identity = None

    def test_diagnostic_cli_reads_active_home(self):
        selected = self.home / "TLO_DBs"
        selected.mkdir()
        shutil.copyfile(ROOT / "TLO_DBs/cities.sqlite", selected / "cities.sqlite")
        result = subprocess.run([sys.executable, "-B", str(ROOT / "match_city.py"),
                                 "--TLOHome", str(self.home), "--city", "San Fransisco",
                                 "--state", "CA", "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"canonical_city": "San Francisco"', result.stdout)


if __name__ == "__main__":
    unittest.main()
