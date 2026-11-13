#!/usr/bin/env python3
"""Generate WiX v6 source from a signed TLO Windows release staging tree.

The payload is exactly the staged files plus the MSI-only update worker and
installer marker. No network or WiX dependency is needed to generate source.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys
import uuid
import xml.etree.ElementTree as ET

NS = "http://wixtoolset.org/schemas/v4/wxs"
ET.register_namespace("", NS)
# Stable identity. Do NOT change after shipping the first MSI.
UPGRADE_CODE = "{B5B5E48C-0AC6-44F5-8E80-8EB1AE8BA2B2}"
COMPONENT_NAMESPACE = uuid.UUID("96bd23cc-55ca-4916-836d-9b811e5a1556")
PACKAGE_NAME = "Traders Little Organizer"
MANUFACTURER = "Traders Little Organizer"
PER_USER_INSTALL_KEY = r"Software\TradersLittleOrganizer\Installer"
PER_USER_COMPONENTS_KEY = r"Software\TradersLittleOrganizer\Installer\Components"
# Installer payloads contain distributable templates only; user state lives in
# TLOHome, outside the MSI-owned install directory. Uninstall should be clean.
PRESERVE_NAMES = set()


def elt(parent, name, **attrs):
    return ET.SubElement(parent, f"{{{NS}}}{name}", {k: str(v) for k, v in attrs.items()})


def xml_file(path, out):
    ET.ElementTree(path).write(out, encoding="utf-8", xml_declaration=True)


def stable_id(prefix, value):
    # WiX IDs must be stable when packages are upgraded.
    return prefix + hashlib.sha256(value.lower().encode("utf-8")).hexdigest()[:23]


def stable_guid(path):
    return "{" + str(uuid.uuid5(COMPONENT_NAMESPACE, path.casefold())).upper() + "}"


def parse_version(value):
    match = re.fullmatch(r"(\d+)\.(\d+)\.(\d+)", value)
    if not match:
        raise ValueError("Use MSI 3-part version MAJOR.MINOR.BUILD, e.g. 1.7.654")
    major, minor, build = map(int, match.groups())
    if major > 255 or minor > 255 or build > 65535 or build == 0:
        raise ValueError("MSI version out of supported range")
    return f"{major}.{minor}.{build}"


def prepare_stage(src, dest, worker, db_source=None, document_source=None):
    if (src.resolve() == dest.resolve() or src.resolve() in dest.resolve().parents
            or dest.resolve() in src.resolve().parents):
        raise ValueError("Prepared MSI stage and source stage must not contain one another")
    if not src.is_dir():
        raise FileNotFoundError(src)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for path in sorted(src.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Unsafe symlink in staging payload: {path}")
        relative = path.relative_to(src)
        target = dest / relative
        if path.is_dir():
            target.mkdir(exist_ok=True, parents=True)
        elif path.is_file():
            target.parent.mkdir(exist_ok=True, parents=True)
            shutil.copy2(path, target)
    worker_path = dest / "TLO-MSI-Update-Worker.ps1"
    if worker_path.exists():
        raise ValueError("Stage unexpectedly already contains MSI update worker")
    shutil.copy2(worker, worker_path)
    if db_source is not None:
        seed_folder = dest / "TLO_DBs"
        seed_folder.mkdir(exist_ok=False)
        for name in ("artists.sqlite", "venues.txt", "cities.csv"):
            source = db_source / name
            if not source.is_file() or source.stat().st_size == 0:
                raise ValueError(f"Missing required MSI database seed: {source}")
            shutil.copy2(source, seed_folder / name)
    if document_source is not None:
        for name in ("TLO-FAQ.txt", "tlo-preferences.ini"):
            document = document_source / name
            if not document.is_file() or document.stat().st_size == 0:
                raise ValueError(f"Missing required MSI support file: {document}")
            if (dest / name).exists():
                raise ValueError(f"MSI support file already staged: {name}")
            shutil.copy2(document, dest / name)
        for pattern in ("TLO_Inventory_User_Manual_v*.rtf", "TLO_Inventory_Requirements_Working_v*.docx"):
            matches = list(document_source.glob(pattern))
            if len(matches) != 1:
                raise ValueError(f"Expected exactly one current MSI document matching {pattern}")
            shutil.copy2(matches[0], dest / matches[0].name)
    marker = dest / "tlo-install-method.json"
    if marker.exists():
        raise ValueError("Stage unexpectedly already contains MSI install marker")
    marker.write_text(json.dumps({"installer": "msi", "scope": "perUser", "schema": 1}, indent=2) + "\n", encoding="utf-8")


def generate(stage, wxs, version, main_exe=None):
    stage = stage.resolve()
    version = parse_version(version)
    files = sorted((p for p in stage.rglob("*") if p.is_file()), key=lambda p: str(p).lower())
    if not files:
        raise ValueError("MSI staging directory has no files")
    for f in files:
        if f.is_symlink():
            raise ValueError(f"Unsafe staged symlink: {f}")
    main_candidates = [p for p in files if p.name.lower() == "tlo-main.exe"]
    if main_exe:
        required = stage / main_exe
        if required not in files:
            raise ValueError(f"Selected application executable is absent: {required}")
        main_candidates = [required]
    if len(main_candidates) != 1:
        raise ValueError(f"Expected exactly one tlo-main.exe, found {len(main_candidates)}")
    main_rel = main_candidates[0].relative_to(stage).as_posix()
    root = ET.Element(f"{{{NS}}}Wix")
    pkg = elt(root, "Package", Name=PACKAGE_NAME, Manufacturer=MANUFACTURER,
              Version=version, UpgradeCode=UPGRADE_CODE, Scope="perUser", Language="1033")
    elt(pkg, "MajorUpgrade", DowngradeErrorMessage="A newer TLO version is already installed.",
        Schedule="afterInstallInitialize", AllowSameVersionUpgrades="no")
    elt(pkg, "MediaTemplate", EmbedCab="yes")
    local = elt(pkg, "StandardDirectory", Id="LocalAppDataFolder")
    programs = elt(local, "Directory", Id="TLOLocalProgramsDir", Name="Programs")
    install = elt(programs, "Directory", Id="INSTALLFOLDER", Name="Traders Little Organizer")
    directory_nodes = {"": install}
    # A file may be several levels below a directory that contains no files of
    # its own (e.g. THIRD_PARTY/vendor/runtime.dll). Include *every* ancestor,
    # not only the immediate parents of payload files. WiX requires parents to
    # exist before nested Directory elements are attached.
    directory_paths = set()
    for file_path in files:
        parent_parts = file_path.relative_to(stage).parts[:-1]
        for depth in range(1, len(parent_parts) + 1):
            directory_paths.add("/".join(parent_parts[:depth]))
    dir_paths = sorted(directory_paths, key=lambda path: (path.count("/"), path.casefold(), path))
    for directory in dir_paths:
        parts = directory.split("/")
        parent_rel = "/".join(parts[:-1])
        directory_nodes[directory] = elt(directory_nodes[parent_rel], "Directory",
                                         Id=stable_id("Dir", directory), Name=parts[-1])
    feature = elt(pkg, "Feature", Id="Complete", Title=PACKAGE_NAME, Level="1")
    for f in files:
        rel = f.relative_to(stage).as_posix()
        parent_rel = "/".join(rel.split("/")[:-1])
        parent = directory_nodes[parent_rel]
        compid = stable_id("Cmp", rel)
        preserve = f.name.casefold() in PRESERVE_NAMES
        attrs = {"Id": compid, "Guid": stable_guid("file/" + rel)}
        if preserve:
            attrs.update(Permanent="yes", NeverOverwrite="yes")
        component = elt(parent, "Component", **attrs)
        elt(component, "File", Id=stable_id("File", rel), Source=str(f), KeyPath="no")
        elt(component, "RegistryValue", Root="HKCU", Key=PER_USER_COMPONENTS_KEY,
            Name=stable_id("Value", rel), Type="integer", Value="1", KeyPath="yes")
        if f == main_candidates[0]:
            elt(component, "RegistryValue", Root="HKCU", Key=PER_USER_INSTALL_KEY,
                Name="InstallPath", Type="string", Value="[INSTALLFOLDER]")
            elt(component, "RegistryValue", Root="HKCU", Key=PER_USER_INSTALL_KEY,
                Name="InstallMethod", Type="string", Value="msi")
        elt(feature, "ComponentRef", Id=compid)

    # ICE64 requires *every* directory created below a user-profile location
    # to have an entry in the MSI RemoveFile table. Attaching RemoveFolder to
    # file components misses intermediate directories containing only child
    # directories (THIRD_PARTY, runtime containers, etc.). A dedicated HKCU-
    # keyed component owns directory cleanup for the complete payload tree.
    # RemoveFolder only removes EMPTY folders: it never deletes user data or
    # recursively removes files, and does not touch TLOHome.
    cleanup = elt(install, "Component", Id="TLOInstallDirectoryCleanup",
                  Guid=stable_guid("directory-cleanup/install-root"))
    for directory in reversed(dir_paths):
        elt(cleanup, "RemoveFolder", Id=stable_id("Remove", directory),
            Directory=stable_id("Dir", directory), On="uninstall")
    elt(cleanup, "RemoveFolder", Id="RemoveInstallRoot",
        Directory="INSTALLFOLDER", On="uninstall")
    elt(cleanup, "RemoveFolder", Id="RemoveEmptyLocalPrograms",
        Directory="TLOLocalProgramsDir", On="uninstall")
    elt(cleanup, "RegistryValue", Root="HKCU", Key=PER_USER_COMPONENTS_KEY,
        Name="DirectoryCleanup", Type="integer", Value="1", KeyPath="yes")
    elt(feature, "ComponentRef", Id="TLOInstallDirectoryCleanup")

    menu = elt(pkg, "StandardDirectory", Id="ProgramMenuFolder")
    menu_dir = elt(menu, "Directory", Id="TLOProgramsMenu", Name="Traders Little Organizer")
    shortcut = elt(menu_dir, "Component", Id="TLOStartMenuComponent",
                   Guid=stable_guid("shortcut/startmenu/tlo-main"))
    path_in_msi = main_rel.replace("/", "\\")
    elt(shortcut, "Shortcut", Id="TLOStartMenuShortcut", Name="Traders Little Organizer",
        Target="[INSTALLFOLDER]" + path_in_msi, WorkingDirectory="INSTALLFOLDER", Advertise="no")
    # Expose both primary GUIs in the Start Menu; they share one MSI-owned folder.
    search_candidates = [p for p in files if p.name.lower() == "tlo-search.exe"]
    if len(search_candidates) == 1:
        search_rel = search_candidates[0].relative_to(stage).as_posix().replace("/", "\\")
        elt(shortcut, "Shortcut", Id="TLOSearchStartMenuShortcut", Name="TLO Search",
            Target="[INSTALLFOLDER]" + search_rel, WorkingDirectory="INSTALLFOLDER", Advertise="no")
    elt(shortcut, "RemoveFolder", Id="RemoveStartMenu", On="uninstall")
    elt(shortcut, "RegistryValue", Root="HKCU", Key=PER_USER_INSTALL_KEY,
        Name="StartMenuShortcut", Type="integer", Value="1", KeyPath="yes")
    elt(feature, "ComponentRef", Id="TLOStartMenuComponent")
    wxs.parent.mkdir(exist_ok=True, parents=True)
    ET.indent(root, space="  ")
    xml_file(root, wxs)
    return {"version": version, "file_count": len(files), "main_exe": main_rel,
            "stage": str(stage), "wxs": str(wxs), "upgrade_code": UPGRADE_CODE,
            "scope": "perUser", "install_root": "%LOCALAPPDATA%\\Programs\\Traders Little Organizer"}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source-stage", required=True, type=Path)
    p.add_argument("--prepared-stage", required=True, type=Path)
    p.add_argument("--worker", type=Path, required=True)
    p.add_argument("--wxs", required=True, type=Path)
    p.add_argument("--version", required=True)
    p.add_argument("--data-source", type=Path, help="Required physical master databases for first MSI launch")
    p.add_argument("--document-source", type=Path, help="Application source with current FAQ, preferences template and documentation")
    p.add_argument("--main-exe", help="Optional relative path for tlo-main.exe")
    a = p.parse_args(argv)
    try:
        prepare_stage(a.source_stage, a.prepared_stage, a.worker, a.data_source, a.document_source)
        print(json.dumps(generate(a.prepared_stage, a.wxs, a.version, a.main_exe), indent=2))
    except (OSError, ValueError) as ex:
        print(f"MSI generation failed: {ex}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
