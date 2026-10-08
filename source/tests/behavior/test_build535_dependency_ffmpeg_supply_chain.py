
import hashlib
import importlib.util
import re
import zipfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.behavior

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_build535_ffmpeg_release_is_exact_and_checksum_pinned():
    prep = _load("tlo_prepare_ffmpeg_535", "prepare_ffmpeg.py")
    assert prep.FFMPEG_VERSION == "9.0.2"
    assert "releases/download/v9.0.2" in prep.PROVIDER_RELEASE
    assert len(prep.ASSETS) == 8
    for (platform_name, arch), (asset, digest) in prep.ASSETS.items():
        assert platform_name in {"linux", "macos", "windows"}
        assert arch in {"x64", "arm64", "x86"}
        assert asset.startswith("ffmpeg-") and asset.endswith(".zip")
        assert re.fullmatch(r"[0-9a-f]{64}", digest)


def test_build535_ffmpeg_archive_extraction_rejects_traversal_and_extracts_only_binary(tmp_path):
    prep = _load("tlo_prepare_ffmpeg_extract_535", "prepare_ffmpeg.py")
    good = tmp_path / "good.zip"
    with zipfile.ZipFile(good, "w") as zf:
        zf.writestr("release/bin/ffmpeg", b"ffmpeg-binary")
        zf.writestr("release/README.txt", b"ignored")
    out = tmp_path / "out" / "ffmpeg"
    prep._extract_ffmpeg(good, out, windows=False)
    assert out.read_bytes() == b"ffmpeg-binary"
    assert out.stat().st_mode & 0o111

    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../escape", b"x")
        zf.writestr("release/bin/ffmpeg", b"ffmpeg-binary")
    with pytest.raises(RuntimeError, match="unsafe ffmpeg archive member"):
        prep._extract_ffmpeg(bad, tmp_path / "bad-out" / "ffmpeg", windows=False)


def test_build535_runtime_resolver_has_no_imageio_or_environment_fallback():
    text = (ROOT / "tlo_ffmpeg.py").read_text(encoding="utf-8")
    assert "tlo_ffmpeg_bin" in text
    assert "imageio_ffmpeg" not in text
    assert "get_ffmpeg_exe" not in text
    assert "IMAGEIO_FFMPEG_EXE" not in text
    assert "shutil.which" not in text
    assert "os.environ" not in text


def test_build535_native_build_scripts_prepare_exact_ffmpeg_and_add_it_as_binary():
    for filename in ("createLinuxDist.sh", "createMacOSDist.sh", "createWindowsDist.ps1"):
        text = (ROOT / filename).read_text(encoding="utf-8")
        assert "verify_build_environment.py" in text
        assert "prepare_ffmpeg.py" in text
        assert "--add-binary" in text
        assert "tlo_ffmpeg_bin" in text
        assert "build-tool-versions.txt" in text
        assert "--collect-all imageio_ffmpeg" not in text
        assert "'imageio_ffmpeg'" not in text
        assert '"imageio_ffmpeg"' not in text
        assert "IMAGEIO_FFMPEG_EXE" in text  # hostile smoke-test override must be ignored


def test_build535_build_lock_is_exact_hashed_and_drops_imageio_ffmpeg():
    text = (ROOT / "requirements-build.txt").read_text(encoding="utf-8")
    assert "--only-binary=:all:" in text
    for token in (
        "pyinstaller==6.22.3",
        "pyinstaller-hooks-contrib==2026.8",
        "mutagen==1.48.1",
        "tkinterdnd2==0.6.3",
        "pytest==9.1.1",
        "python-docx==1.2.0",
        "lxml==6.1.3",
        "ruff==0.16.10",
    ):
        assert token in text
    assert "imageio-ffmpeg" not in text.casefold()
    blocks = [block for block in re.split(r"\n\s*\n", text) if "==" in block and not block.lstrip().startswith("#")]
    assert blocks
    assert all("--hash=sha256:" in block for block in blocks)


def test_build535_build_environment_pin_is_python_31316_and_pyinstaller_6223():
    verifier = _load("tlo_verify_build_env_535", "verify_build_environment.py")
    assert verifier.EXPECTED_PYTHON == (3, 13, 16)
    assert verifier.EXPECTED_PACKAGES["PyInstaller"] == "6.22.3"
    assert verifier.RELEASE_CHECK_PACKAGES["lxml"] == "6.1.3"
    assert verifier.RELEASE_CHECK_PACKAGES["ruff"] == "0.16.10"


def test_build535_audit_helper_is_exact_and_isolated():
    text = (ROOT / "audit_build_requirements.py").read_text(encoding="utf-8")
    assert 'PIP_AUDIT_VERSION = "2.10.1"' in text
    assert "TemporaryDirectory" in text
    assert "venv.EnvBuilder" in text
    assert '"--require-hashes"' in text
    assert '"--no-deps"' in text
    assert '"--strict"' in text


def test_build535_ffmpeg_source_notice_matches_preparation_manifest():
    notice = (ROOT / "FFMPEG_BUILD_SOURCE.txt").read_text(encoding="utf-8")
    prep = _load("tlo_prepare_ffmpeg_notice_535", "prepare_ffmpeg.py")
    assert f"Version: FFmpeg {prep.FFMPEG_VERSION}" in notice
    assert "boul2gom/ffmpeg-builds" in notice
    assert hashlib.sha256((ROOT / "requirements-build.txt").read_bytes()).hexdigest()
