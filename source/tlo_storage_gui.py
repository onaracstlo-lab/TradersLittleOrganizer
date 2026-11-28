"""Simple storage identity manager for tlo-main, using the standard Tk GUI."""
from __future__ import annotations

from tlo_version import VERSION as _TLO_CANONICAL_VERSION
__version__ = _TLO_CANONICAL_VERSION

import tkinter as tk
import uuid
from tkinter import filedialog, messagebox, ttk

from tlo_bootlist_volume_policy import read_bootlist_rows, read_group_log_volume_rows
from tlo_path_inputs import normalize_platform_input_path
from tlo_runtime_control import inventory_operation_lock
from tlo_storage_identities import load_registry, resolve_root, save_registry, StorageIdentityError
from tlo_window_icons import install_window_icon


def manage_storage_identities(parent, home):
    dialog = tk.Toplevel(parent)
    dialog.title("Manage Storage Identities")
    install_window_icon(dialog, "main")
    dialog.transient(parent)
    dialog.grab_set()
    dialog.geometry("820x480")
    dialog.minsize(620, 350)
    text = ("TLO remembers each inventory folder, even when its drive letter or label changes. "
            "Choose an inventory below to reconnect it or identify a backup. "
            "Your music and old inventory records are not deleted here.")
    ttk.Label(dialog, text=text, wraplength=760, padding=10).pack(fill="x")
    frame = ttk.Frame(dialog)
    frame.pack(fill="both", expand=True, padx=10)
    tree = ttk.Treeview(frame, columns=("name", "label", "path"), show="headings", selectmode="browse")
    for col, heading, width in (("name", "Inventory name", 220), ("label", "Last drive label", 160), ("path", "Last folder", 370)):
        tree.heading(col, text=heading)
        tree.column(col, width=width)
    scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=scroll.set)
    tree.pack(side="left", fill="both", expand=True)
    scroll.pack(side="right", fill="y")
    detail = tk.StringVar(value="Choose an inventory for details.")
    ttk.Label(dialog, textvariable=detail, wraplength=760, padding=10).pack(fill="x")
    roots = {}
    legacy = {}

    def refresh():
        roots.clear()
        roots.update(load_registry(home))
        legacy.clear()
        tree.delete(*tree.get_children())
        for ident, item in sorted(roots.items(), key=lambda v: v[1]["name"].casefold()):
            tree.insert("", "end", iid=ident, values=(item["name"], item.get("hardware", {}).get("label", ""), item.get("path", "")))
        names = {item["name"].casefold() for item in roots.values()}
        for row in read_bootlist_rows(home) + read_group_log_volume_rows(home):
            name = row.get("Volume", "")
            if name and name.casefold() not in names and name not in legacy.values():
                key = f"legacy-{len(legacy)}"
                legacy[key] = name
                tree.insert("", "end", iid=key, values=(name, "Older inventory", "Not registered"))
        detail.set("Choose an inventory for details.")

    def selected():
        selection = tree.selection()
        return selection[0] if selection else ""

    def details(_event=None):
        item = roots.get(selected())
        if item:
            hardware = item.get("hardware", {})
            serial = hardware.get("disk_serial", "Not available")
            partition = hardware.get("partition_guid") or hardware.get("partition_offset") or "Not available"
            group = [r["name"] for r in roots.values() if r.get("collection_id") == item.get("collection_id") and r is not item]
            detail.set(f"Drive model: {hardware.get('model', 'Not available')} | Serial: {serial}\n"
                       f"Partition: {partition} | Related copies: {', '.join(group) or 'None'}")
        elif selected() in legacy:
            detail.set("Older inventory: select Connect / Replace and choose the original collection folder.")
        else:
            detail.set("Choose an inventory for details.")

    tree.bind("<<TreeviewSelect>>", details)

    def choose_folder():
        # Entry accepts UNC and WSL paths in addition to the platform chooser.
        picker = tk.Toplevel(dialog)
        picker.title("Choose storage folder")
        picker.transient(dialog)
        picker.grab_set()
        value = tk.StringVar()
        ttk.Label(picker, text="Enter or browse to the inventory folder.").pack(padx=12, pady=8)
        line = ttk.Frame(picker)
        line.pack(fill="x", padx=12)
        entry = ttk.Entry(line, textvariable=value, width=54)
        entry.pack(side="left", fill="x", expand=True)
        ttk.Button(line, text="Browse...", command=lambda: value.set(filedialog.askdirectory(parent=picker) or value.get())).pack(side="left", padx=4)
        result = []
        def accept():
            if value.get().strip():
                result.append(value.get().strip())
                picker.destroy()
        ttk.Button(picker, text="OK", command=accept).pack(side="left", padx=12, pady=12)
        ttk.Button(picker, text="Cancel", command=picker.destroy).pack(side="right", padx=12)
        entry.focus_set()
        picker.wait_window()
        dialog.grab_set()
        return normalize_platform_input_path(result[0]) if result else ""

    def act(mode):
        key = selected()
        if mode != "new" and not key:
            messagebox.showinfo("Storage Identities", "Select an inventory first.", parent=dialog)
            return
        try:
            path = choose_folder()
            if not path:
                return
            if mode == "connect":
                name = legacy.get(key) or roots[key]["name"]
                if not messagebox.askyesno("Connect inventory", f"Use this folder for the existing inventory '{name}'?\n\n{path}\n\nChoose Yes only if it contains the same collection. Old inventory records are retained.",
                                           default=messagebox.NO, parent=dialog):
                    return
                with inventory_operation_lock(home):
                    options = {"legacy_name": name} if key in legacy else {"replacement_id": key}
                    resolve_root(home, path, register=True, **options)
            elif mode == "copy":
                if key in legacy:
                    raise ValueError("Connect the older inventory before registering its backup.")
                if not messagebox.askyesno("Register a separate copy", f"Register {path} as a separate backup of {roots[key]['name']}? Neither inventory will be merged or deleted.",
                                           default=messagebox.NO, parent=dialog):
                    return
                with inventory_operation_lock(home):
                    # A copy may already have its own registered inventory.
                    # Link that identity without regenerating its marker or name.
                    try:
                        existing = resolve_root(home, path)
                    except StorageIdentityError:
                        existing = None
                    if existing:
                        existing_id, existing_item = existing
                        import os
                        if not os.path.samefile(path, existing_item["path"]):
                            raise StorageIdentityError("Choose the backup inventory root itself, not a subfolder.")
                        latest = load_registry(home)
                        latest[existing_id]["collection_id"] = latest[key]["collection_id"]
                        save_registry(home, latest)
                    else:
                        resolve_root(home, path, register=True, separate=True, collection_id=roots[key]["collection_id"])
            else:
                with inventory_operation_lock(home):
                    resolve_root(home, path, register=True, separate=True)
            refresh()
            messagebox.showinfo("Storage Identities", "Storage identity saved. No music or inventory rows were deleted.", parent=dialog)
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Storage Identities", str(exc), parent=dialog)

    def unlink_collection():
        key = selected()
        if key not in roots:
            return
        if messagebox.askyesno("Separate collection", "Remove the relationship to related backup copies? No inventory records will be deleted.", default=messagebox.NO, parent=dialog):
            try:
                with inventory_operation_lock(home):
                    latest = load_registry(home)
                    latest[key]["collection_id"] = str(uuid.uuid4())
                    save_registry(home, latest)
                refresh()
            except (OSError, RuntimeError, ValueError) as exc:
                messagebox.showerror("Storage Identities", str(exc), parent=dialog)

    buttons = ttk.Frame(dialog)
    buttons.pack(fill="x", padx=10, pady=10)
    for label, action in (("Register New", lambda: act("new")), ("Connect / Replace", lambda: act("connect")),
                          ("Register Backup Copy", lambda: act("copy")), ("Separate Collection", unlink_collection),
                          ("Close", dialog.destroy)):
        ttk.Button(buttons, text=label, command=action).pack(side="left", padx=3)
    try:
        refresh()
    except (OSError, RuntimeError, ValueError) as exc:
        messagebox.showerror("Storage Identities", str(exc), parent=dialog)
        dialog.destroy()
        return
    dialog.wait_window()
