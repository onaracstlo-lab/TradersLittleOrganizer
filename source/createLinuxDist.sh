#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

usage() {
    cat <<'USAGE'
Usage:
  createLinuxDist.sh BUNDLE_NUMBER [SOURCE_ROOT] [DIST_ROOT]

Arguments:
  BUNDLE_NUMBER  Numeric bundle number supplied at run time.
  SOURCE_ROOT    Directory containing the TLO Python sources. Defaults to the
                 directory containing this script.
  DIST_ROOT      Output release tree. Defaults to:
                 $HOME/tloDist-V1.0Build<BUNDLE_NUMBER>
USAGE
}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

[[ "$(uname -s)" == "Linux" ]] || fail "createLinuxDist.sh must run on Linux."
[[ $# -ge 1 && $# -le 3 ]] || { usage; exit 2; }

BUNDLE_NUMBER="$1"
[[ "$BUNDLE_NUMBER" =~ ^[0-9]+$ ]] || fail "BUNDLE_NUMBER must contain digits only."

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
SOURCE_ROOT="${2:-$SCRIPT_DIR}"
DIST_ROOT="${3:-$HOME/tloDist-V1.0Build${BUNDLE_NUMBER}}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

[[ -d "$SOURCE_ROOT" ]] || fail "SOURCE_ROOT does not exist: $SOURCE_ROOT"
SOURCE_ROOT="$(cd -- "$SOURCE_ROOT" && pwd -P)"
mkdir -p -- "$DIST_ROOT"
DIST_ROOT="$(cd -- "$DIST_ROOT" && pwd -P)"

TARGET_DIR="${DIST_ROOT}/apps/Linux"
REPORT_DIR="${DIST_ROOT}/scan-reports"
REPORT_PATH="${REPORT_DIR}/linux.json"
SCAN_SCRIPT="${SOURCE_ROOT}/scan_release_artifacts.py"
BUILD_ROOT="${DIST_ROOT}/.build-Linux"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python executable not found: $PYTHON_BIN"
"$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1 || fail "PyInstaller is not installed for $PYTHON_BIN."
[[ -f "$SCAN_SCRIPT" ]] || fail "Required scan utility not found: $SCAN_SCRIPT"

find_script() {
    local name="$1"
    local candidate
    for candidate in "${SOURCE_ROOT}/${name}" "${SOURCE_ROOT}/searchApps/${name}"; do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    fail "Required source script not found: $name"
}

cleanup() {
    rm -rf -- "$BUILD_ROOT"
}
trap cleanup EXIT

rm -rf -- "$TARGET_DIR" "$BUILD_ROOT"
mkdir -p -- "$TARGET_DIR" "$REPORT_DIR" "$BUILD_ROOT"

build_one() {
    local script_path="$1"
    shift
    local base
    base="$(basename -- "$script_path" .py)"
    local work_dir="${BUILD_ROOT}/${base}"
    mkdir -p -- "$work_dir"

    "$PYTHON_BIN" -m PyInstaller \
        --noconfirm --clean --onefile --noupx \
        --workpath "${work_dir}/work" \
        --specpath "$work_dir" \
        --distpath "$TARGET_DIR" \
        --paths "$SOURCE_ROOT" \
        "$@" "$script_path"

    [[ -f "${TARGET_DIR}/${base}" && -x "${TARGET_DIR}/${base}" ]] || \
        fail "Expected Linux executable was not created: ${TARGET_DIR}/${base}"
}

build_one "$(find_script search-artist-db.py)" --windowed
build_one "$(find_script tlo-gsi.py)" --windowed
build_one "$(find_script tlo-gi.py)"
build_one "$(find_script tlo-ggi.py)" --windowed \
    --collect-all mutagen \
    --collect-all imageio_ffmpeg \
    --collect-all tkinterdnd2
build_one "$(find_script tlo-tag.py)" \
    --collect-all mutagen \
    --collect-all imageio_ffmpeg

"$PYTHON_BIN" "$SCAN_SCRIPT" \
    --platform linux \
    --artifact-dir "$TARGET_DIR" \
    --report "$REPORT_PATH"

[[ -s "$REPORT_PATH" ]] || fail "Clean scan receipt was not created: $REPORT_PATH"

echo "Linux executables built and scanned clean: $TARGET_DIR"
echo "Scan receipt: $REPORT_PATH"
