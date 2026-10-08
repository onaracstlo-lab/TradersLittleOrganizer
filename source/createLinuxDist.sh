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
                 $HOME/tloDist-V<PUBLIC_VERSION>Build<BUNDLE_NUMBER>
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
PYTHON_BIN="${PYTHON_BIN:-python3}"

[[ -d "$SOURCE_ROOT" ]] || fail "SOURCE_ROOT does not exist: $SOURCE_ROOT"
SOURCE_ROOT="$(cd -- "$SOURCE_ROOT" && pwd -P)"
VERSION_FILE="${SOURCE_ROOT}/tlo_version.py"
[[ -f "$VERSION_FILE" ]] || fail "Required version module not found: $VERSION_FILE"
PUBLIC_VERSION="$(awk -F'"' '/^PUBLIC_VERSION[[:space:]]*=[[:space:]]*"[0-9]+(\.[0-9]+)*"[[:space:]]*$/ { print $2; exit }' "$VERSION_FILE")"
[[ -n "$PUBLIC_VERSION" ]] || fail "Could not read PUBLIC_VERSION from $VERSION_FILE"
SOURCE_BUNDLE_BUILD="$(awk '/^BUNDLE_BUILD[[:space:]]*=[[:space:]]*[0-9]+[[:space:]]*$/ { print $3; exit }' "$VERSION_FILE")"
[[ -n "$SOURCE_BUNDLE_BUILD" ]] || fail "Could not read BUNDLE_BUILD from $VERSION_FILE"
[[ "$BUNDLE_NUMBER" == "$SOURCE_BUNDLE_BUILD" ]] || fail "Bundle number mismatch: supplied $BUNDLE_NUMBER but tlo_version.BUNDLE_BUILD is $SOURCE_BUNDLE_BUILD."
DIST_ROOT="${3:-$HOME/tloDist-V${PUBLIC_VERSION}Build${BUNDLE_NUMBER}}"

mkdir -p -- "$DIST_ROOT"
DIST_ROOT="$(cd -- "$DIST_ROOT" && pwd -P)"

TARGET_DIR="${DIST_ROOT}/apps/Linux"
REPORT_DIR="${DIST_ROOT}/scan-reports"
REPORT_PATH="${REPORT_DIR}/linux.json"
SCAN_SCRIPT="${SOURCE_ROOT}/scan_release_artifacts.py"
VERIFY_ENV_SCRIPT="${SOURCE_ROOT}/verify_build_environment.py"
PREPARE_FFMPEG_SCRIPT="${SOURCE_ROOT}/prepare_ffmpeg.py"
BUILD_ROOT="${DIST_ROOT}/.build-Linux"
TOOL_RECEIPT="${REPORT_DIR}/linux-build-tool-versions.txt"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python executable not found: $PYTHON_BIN"
[[ -f "$VERIFY_ENV_SCRIPT" ]] || fail "Required build-environment verifier not found: $VERIFY_ENV_SCRIPT"
[[ -f "$PREPARE_FFMPEG_SCRIPT" ]] || fail "Required ffmpeg preparation utility not found: $PREPARE_FFMPEG_SCRIPT"
"$PYTHON_BIN" "$VERIFY_ENV_SCRIPT" || fail "Pinned Linux build environment verification failed."
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

FFMPEG_STAGE="${BUILD_ROOT}/tlo_ffmpeg_bin"
"$PYTHON_BIN" "$PREPARE_FFMPEG_SCRIPT"     --platform linux     --output-dir "$FFMPEG_STAGE"     --cache-dir "${BUILD_ROOT}/ffmpeg-cache" || fail "Pinned ffmpeg preparation failed."
FFMPEG_BINARY="${FFMPEG_STAGE}/ffmpeg"
[[ -f "$FFMPEG_BINARY" && -x "$FFMPEG_BINARY" ]] || fail "Prepared ffmpeg binary is missing: $FFMPEG_BINARY"
FFMPEG_ADD_BINARY="${FFMPEG_BINARY}:tlo_ffmpeg_bin"

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
build_one "$(find_script tlo-search.py)" --windowed
build_one "$(find_script tlo-gi.py)" \
    --collect-all mutagen \
    --add-binary "$FFMPEG_ADD_BINARY"
build_one "$(find_script tlo-research.py)"
build_one "$(find_script tlo-reverse.py)"
build_one "$(find_script tlo-main.py)" --windowed \
    --collect-all mutagen \
    --add-binary "$FFMPEG_ADD_BINARY" \
    --collect-all tkinterdnd2
build_one "$(find_script tlo-tag.py)" \
    --collect-all mutagen \
    --add-binary "$FFMPEG_ADD_BINARY"
build_one "$(find_script tlo-deleteDupes.py)" \
    --add-binary "$FFMPEG_ADD_BINARY"

IMAGEIO_FFMPEG_EXE=/bin/true TLO_PACKAGING_SMOKE_TEST=1 "${TARGET_DIR}/tlo-gi" || fail "Frozen tlo-gi packaging smoke test failed."

{
    "$PYTHON_BIN" --version
    "$PYTHON_BIN" -m PyInstaller --version | sed 's/^/PyInstaller /'
    "$FFMPEG_BINARY" -version | head -n 1
    printf 'requirements-build.txt sha256 %s\n' "$(sha256sum "${SOURCE_ROOT}/requirements-build.txt" | awk '{print $1}')"
} > "$TOOL_RECEIPT"

"$PYTHON_BIN" "$SCAN_SCRIPT" \
    --platform linux \
    --artifact-dir "$TARGET_DIR" \
    --report "$REPORT_PATH"

[[ -s "$REPORT_PATH" ]] || fail "Clean scan receipt was not created: $REPORT_PATH"

echo "Linux executables built and scanned clean: $TARGET_DIR"
echo "Scan receipt: $REPORT_PATH"
