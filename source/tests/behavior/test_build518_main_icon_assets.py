
import pytest

pytestmark = pytest.mark.behavior

"""Build 518 artwork remains present under the canonical Build 522 Main icon names."""

from pathlib import Path
import hashlib
import struct

ROOT = Path(__file__).resolve().parents[2]
ICON_DIR = ROOT / "icons"
SOURCE_MAIN_ICON = ICON_DIR / "tlo-main-icon.png"


def test_build518_main_png_is_present():
    assert SOURCE_MAIN_ICON.is_file()
    assert hashlib.sha256(SOURCE_MAIN_ICON.read_bytes()).digest()


def test_build518_main_ico_is_dib_based_and_multi_image():
    data = (ICON_DIR / "tlo-main-icon.ico").read_bytes()
    reserved, icon_type, count = struct.unpack_from("<HHH", data, 0)
    assert reserved == 0
    assert icon_type == 1
    assert count >= 5
    png_signature = b"\x89PNG\r\n\x1a\n"
    offset = 6
    for index in range(count):
        *_prefix, size, image_offset = struct.unpack_from("<BBBBHHII", data, offset + index * 16)
        blob = data[image_offset:image_offset + size]
        assert not blob.startswith(png_signature), f"entry {index} is PNG-compressed"


def test_build518_main_icns_exists():
    assert (ICON_DIR / "tlo-main-icon.icns").is_file()
