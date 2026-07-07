#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

usage() {
    cat <<'USAGE'
Usage:
  createMacOSDist.sh BUNDLE_NUMBER [SOURCE_ROOT] [DIST_ROOT]

Arguments:
  BUNDLE_NUMBER  Numeric bundle number supplied at run time.
  SOURCE_ROOT    Directory containing the TLO Python sources. Defaults to the
                 directory containing this script.
  DIST_ROOT      Output release tree. Defaults to:
                 $HOME/tloDist-V1.0Build<BUNDLE_NUMBER>

Environment variables:
  PYTHON_BIN                    Python executable to use. Default: python3
  TLO_MACOS_CODESIGN_IDENTITY  Optional Apple code-signing identity.
  TLO_MACOS_ENTITLEMENTS       Optional path to a macOS entitlements file.
  TLO_MACOS_TARGET_ARCH        Optional: x86_64, arm64, or universal2.
USAGE
}

fail() {
    echo "ERROR: $*" >&2
    exit 1
}

[[ "$(uname -s)" == "Darwin" ]] || fail "createMacOSDist.sh must run on macOS."
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

TARGET_DIR="${DIST_ROOT}/apps/macOS"
REPORT_DIR="${DIST_ROOT}/scan-reports"
REPORT_PATH="${REPORT_DIR}/macos.json"
SCAN_SCRIPT="${SOURCE_ROOT}/scan_release_artifacts.py"

command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "Python executable not found: $PYTHON_BIN"
"$PYTHON_BIN" -m PyInstaller --version >/dev/null 2>&1 || \
    fail "PyInstaller is not installed for $PYTHON_BIN."
[[ -f "$SCAN_SCRIPT" ]] || fail "Required scan utility not found: $SCAN_SCRIPT"

if [[ -n "${TLO_MACOS_ENTITLEMENTS:-}" && ! -f "$TLO_MACOS_ENTITLEMENTS" ]]; then
    fail "TLO_MACOS_ENTITLEMENTS does not name a file: $TLO_MACOS_ENTITLEMENTS"
fi

case "${TLO_MACOS_TARGET_ARCH:-}" in
    ""|x86_64|arm64|universal2) ;;
    *) fail "TLO_MACOS_TARGET_ARCH must be x86_64, arm64, or universal2." ;;
esac

find_script() {
    local name="$1"
    local candidate
    for candidate in \
        "${SOURCE_ROOT}/${name}" \
        "${SOURCE_ROOT}/searchApps/${name}"
    do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    fail "Required source script not found: $name"
}

find_optional_icon() {
    local name="$1"
    local candidate
    for candidate in \
        "${SOURCE_ROOT}/icons/${name}" \
        "${SOURCE_ROOT}/UtilityData-Apps/iconInfo/${name}"
    do
        if [[ -f "$candidate" ]]; then
            printf '%s\n' "$candidate"
            return 0
        fi
    done
    return 1
}

build_windowed_with_optional_icon() {
    local script_path="$1"
    local icon_path="$2"
    shift 2

    if [[ -n "$icon_path" ]]; then
        build_one "$script_path" yes --icon "$icon_path" "$@"
    else
        build_one "$script_path" yes "$@"
    fi
}

rm -rf -- "$TARGET_DIR"
rm -f -- "$REPORT_PATH"
mkdir -p -- "$TARGET_DIR" "$REPORT_DIR"

BUILD_ROOT="${DIST_ROOT}/.build-macOS"
rm -rf -- "$BUILD_ROOT"
mkdir -p -- "$BUILD_ROOT"

cleanup() {
    rm -rf -- "$BUILD_ROOT"
}
trap cleanup EXIT

COMMON_SIGNING_ARGS=()
if [[ -n "${TLO_MACOS_CODESIGN_IDENTITY:-}" ]]; then
    COMMON_SIGNING_ARGS+=(--codesign-identity "$TLO_MACOS_CODESIGN_IDENTITY")
fi
if [[ -n "${TLO_MACOS_ENTITLEMENTS:-}" ]]; then
    COMMON_SIGNING_ARGS+=(--osx-entitlements-file "$TLO_MACOS_ENTITLEMENTS")
fi
if [[ -n "${TLO_MACOS_TARGET_ARCH:-}" ]]; then
    COMMON_SIGNING_ARGS+=(--target-arch "$TLO_MACOS_TARGET_ARCH")
fi

# build_one SCRIPT WINDOWED_FLAG [additional PyInstaller arguments...]
build_one() {
    local script_path="$1"
    local windowed="$2"
    shift 2

    local base
    base="$(basename -- "$script_path" .py)"
    local work_dir="${BUILD_ROOT}/${base}"
    rm -rf -- "$work_dir"
    mkdir -p -- "$work_dir"

    local args=(
        --noconfirm
        --clean
        --onefile
        --noupx
        --workpath "${work_dir}/work"
        --specpath "$work_dir"
        --distpath "$TARGET_DIR"
        --paths "$SOURCE_ROOT"
    )

    if [[ "$windowed" == "yes" ]]; then
        args+=(--windowed --osx-bundle-identifier "org.traderslittleorganizer.${base}")
    fi

    if [[ ${#COMMON_SIGNING_ARGS[@]} -gt 0 ]]; then
        args+=("${COMMON_SIGNING_ARGS[@]}")
    fi
    args+=("$@")
    args+=("$script_path")

    echo "Building macOS artifact: $base"
    "$PYTHON_BIN" -m PyInstaller "${args[@]}"

    local executable="${TARGET_DIR}/${base}"
    [[ -f "$executable" && -x "$executable" ]] || \
        fail "Expected macOS executable was not created: $executable"

    if [[ "$windowed" == "yes" ]]; then
        local app_bundle="${TARGET_DIR}/${base}.app"
        [[ -d "$app_bundle" ]] || \
            fail "Expected macOS app bundle was not created: $app_bundle"
    fi
}

INVENTORY_ICON=""
SEARCH_ICON=""
TAG_ICON=""
if icon_candidate="$(find_optional_icon tlo-inventory-icon.icns)"; then
    INVENTORY_ICON="$icon_candidate"
fi
if icon_candidate="$(find_optional_icon tlo-search-icon.icns)"; then
    SEARCH_ICON="$icon_candidate"
fi
if icon_candidate="$(find_optional_icon tlo-tag-icon.icns)"; then
    TAG_ICON="$icon_candidate"
fi

build_one "$(find_script search-artist-db.py)" yes
build_windowed_with_optional_icon "$(find_script tlo-gsi.py)" "$SEARCH_ICON"
build_one "$(find_script tlo-gi.py)" no
build_windowed_with_optional_icon "$(find_script tlo-ggi.py)" "$INVENTORY_ICON" \
    --collect-all mutagen \
    --collect-all imageio_ffmpeg \
    --collect-all tkinterdnd2
if [[ -n "$TAG_ICON" ]]; then
    build_one "$(find_script tlo-tag.py)" no \
        --icon "$TAG_ICON" \
        --collect-all mutagen \
        --collect-all imageio_ffmpeg
else
    build_one "$(find_script tlo-tag.py)" no \
        --collect-all mutagen \
        --collect-all imageio_ffmpeg
fi

EXPECTED_EXECUTABLES=(
    search-artist-db
    tlo-gsi
    tlo-gi
    tlo-ggi
    tlo-tag
)
EXPECTED_APP_BUNDLES=(
    search-artist-db.app
    tlo-gsi.app
    tlo-ggi.app
)

for name in "${EXPECTED_EXECUTABLES[@]}"; do
    path="${TARGET_DIR}/${name}"
    [[ -f "$path" && -x "$path" ]] || fail "Required executable missing before scan: $path"
done
for name in "${EXPECTED_APP_BUNDLES[@]}"; do
    path="${TARGET_DIR}/${name}"
    [[ -d "$path" ]] || fail "Required app bundle missing before scan: $path"
done

# PyInstaller performs ad-hoc signing by default on macOS. When a real identity
# is supplied, verify the resulting executables and app bundles before scanning.
if [[ -n "${TLO_MACOS_CODESIGN_IDENTITY:-}" ]]; then
    command -v codesign >/dev/null 2>&1 || fail "codesign was not found."
    for name in "${EXPECTED_EXECUTABLES[@]}"; do
        codesign --verify --strict --verbose=2 "${TARGET_DIR}/${name}"
    done
    for name in "${EXPECTED_APP_BUNDLES[@]}"; do
        codesign --verify --deep --strict --verbose=2 "${TARGET_DIR}/${name}"
    done
fi

"$PYTHON_BIN" "$SCAN_SCRIPT" \
    --platform macos \
    --artifact-dir "$TARGET_DIR" \
    --report "$REPORT_PATH"

[[ -s "$REPORT_PATH" ]] || fail "Clean scan receipt was not created: $REPORT_PATH"

# Recheck after the scanner has had time to quarantine or remove a file.
sleep 2
for name in "${EXPECTED_EXECUTABLES[@]}"; do
    path="${TARGET_DIR}/${name}"
    [[ -f "$path" && -x "$path" ]] || \
        fail "Executable disappeared after scanning, possibly due to quarantine: $path"
done
for name in "${EXPECTED_APP_BUNDLES[@]}"; do
    path="${TARGET_DIR}/${name}"
    [[ -d "$path" ]] || \
        fail "App bundle disappeared after scanning, possibly due to quarantine: $path"
done

printf '\nmacOS build completed successfully.\n'
printf 'Executables and app bundles: %s\n' "$TARGET_DIR"
printf 'Clean scan receipt: %s\n' "$REPORT_PATH"
