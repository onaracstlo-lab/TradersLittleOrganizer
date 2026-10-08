"""Current versioned source-bundle artifact names for tests."""

import tlo_version as V

REQUIREMENTS_FILENAME = f"TLO_Inventory_Requirements_Working_{V.VERSION}.docx"
MANUAL_FILENAME = f"TLO_Inventory_User_Manual_{V.VERSION}.rtf"
SOURCE_README_FILENAME = f"SOURCE_BUNDLE_README_{V.VERSION}.txt"
CHANGES_FILENAME = f"CHANGES_{V.VERSION}.txt"
BUILD_VERIFICATION_FILENAME = f"BUILD_VERIFICATION_{V.VERSION}.txt"


def release_history() -> str:
    """Full historical build notes belong to CHANGES, not the end-user manual."""
    from pathlib import Path
    root = Path(__file__).resolve().parents[1]
    from zipfile import ZipFile
    with ZipFile(root / "old-change-logs.zip") as archive:
        older = archive.read("Manual_selected_build_history_v564.txt").decode("utf-8")
    return (root / CHANGES_FILENAME).read_text(encoding="utf-8") + "\n" + older
