#!/usr/bin/env bash
set -Eeuo pipefail
[[ $# -eq 3 ]] || { echo 'Usage: build_audio_ffmpeg.sh SOURCE OUTPUT BUILD_DIR' >&2; exit 2; }
source_dir="$1"; output="$2"; build_dir="$3"
[[ -f "${source_dir}/configure" ]] || { echo 'FFmpeg configure missing' >&2; exit 1; }
mkdir -p -- "$build_dir" "$(dirname -- "$output")"
source_dir="$(cd -- "$source_dir" && pwd -P)"
build_dir="$(cd -- "$build_dir" && pwd -P)"
# Fail early with a useful path diagnostic if a source extraction was incomplete.
[[ -f "$source_dir/Makefile" ]] || {
  echo "FFmpeg source Makefile not found through POSIX path: $source_dir/Makefile" >&2
  exit 1
}
# Do not resolve Make through PATH: hosted Windows injects a Git/MinGW Make
# into /c/mingw64/bin which may be selected even by a scoped `command -v`.
# GitHub installs the MSYS2 'make' package under the *same MSYS2 root* as
# the bash.exe used to execute this script. Use only its POSIX-aware binary.
make_command=make
if [[ "${MSYSTEM:-}" == UCRT64 ]]; then
  if [[ -x /usr/bin/make.exe ]]; then
    make_command=/usr/bin/make.exe
  elif [[ -x /usr/bin/make ]]; then
    make_command=/usr/bin/make
  else
    echo "MSYS2 POSIX GNU Make missing at /usr/bin/make[.exe] in the executing Bash root: $(cygpath -w /usr/bin 2>/dev/null || printf '%s' /usr/bin). Ensure TLO_MSYS2_BASH points to the MSYS2 instance where setup-msys2 installed make." >&2
    exit 1
  fi
  # Ignore all PATH-provided Make variants. Neither mingw32-make nor Git for
  # Windows' mingw64 make can interpret POSIX-only FFmpeg source includes.
  make_real="$(readlink -f -- "$make_command")"
  case "$make_real" in
    /usr/bin/make|/usr/bin/make.exe) ;;
    *) echo "MSYS2 POSIX Make path escaped trusted /usr/bin: $make_real" >&2; exit 1 ;;
  esac
  make_version="$("$make_command" --version 2>&1)" || {
    echo "MSYS2 POSIX GNU Make could not execute: $make_command" >&2
    exit 1
  }
  [[ "$make_version" == GNU\ Make* ]] || {
    echo "MSYS2 POSIX Make identity check failed: $make_command" >&2
    exit 1
  }
  echo "FFmpeg GNU Make: $make_command (${make_version%%$'\n'*})"
fi
# The source release has been independently SHA-256 verified by ffmpeg_source_build.py.
# On Windows, build in the extracted source directory. FFmpeg's out-of-tree
# Makefile includes an absolute /d/... source Makefile; Build 579 proved that
# path fails on the Windows runner even after the POSIX Make was selected.
# In-tree `./configure` generates relative Makefile includes and avoids this
# Windows/MSYS2 mount boundary. Linux/macOS retain their proven out-of-tree
# build layout. Both trees are temporary, extracted from a verified tarball.
if [[ "${MSYSTEM:-}" == UCRT64 ]]; then
  cd -- "$source_dir"
  configure_command=./configure
else
  cd -- "$build_dir"
  configure_command="${source_dir}/configure"
fi
"$configure_command" \
  --disable-autodetect --disable-everything --enable-small \
  --disable-network --disable-ffplay --disable-ffprobe \
  --disable-doc --disable-debug --disable-avdevice \
  --disable-swscale --disable-iconv --disable-bzlib --disable-lzma \
  --disable-zlib --disable-x86asm --enable-ffmpeg \
  --enable-static --disable-shared \
  --enable-demuxer=shorten,flac,wav,aiff,mp3,ogg,mov,ape,wv,aac,asf,matroska,au,caf,tta,tak \
  --enable-decoder=shorten,flac,mp3,aac,alac,ape,wavpack,opus,vorbis,wmav1,wmav2,tta,tak,pcm_s16le,pcm_s24le,pcm_s32le,pcm_s16be,pcm_s24be,pcm_s32be,pcm_u8,pcm_f32le,pcm_f64le \
  --enable-encoder=flac,pcm_s16le \
  --enable-muxer=flac,null,framemd5 \
  --enable-parser=aac,flac,mpegaudio,opus,vorbis \
  --enable-filter=abuffer,abuffersink,anull,aresample,aformat \
  --enable-protocol=file,pipe
[[ -f Makefile ]] || {
  echo "FFmpeg configure did not produce build Makefile in $(pwd -P)" >&2
  exit 1
}
# FFmpeg 9.0.2's executable target includes $(EXESUF) on MinGW/UCRT64
# (ffmpeg.exe), but is "ffmpeg" on Linux/macOS.  Requesting the literal
# "ffmpeg" target therefore fails on Windows even after configure succeeds.
# Use the upstream Makefile's platform-independent "all" target instead;
# --disable-everything/--enable-ffmpeg above strictly bound what it builds.
# Confirm the generator emitted configuration and the platform's expected
# output filename before beginning the expensive compilation. The runtime
# validator in prepare_ffmpeg.py separately enforces version/license/codecs.
[[ -f ffbuild/config.mak && -f ffbuild/config.log ]] || {
  echo "FFmpeg configure did not produce complete build configuration in $(pwd -P)" >&2
  exit 1
}
if [[ "${MSYSTEM:-}" == UCRT64 ]]; then
  # Avoid a repeat of Build 582: on MinGW the build target has EXESUF=.exe.
  grep -Eq '^[[:space:]]*EXESUF[[:space:]]*=[[:space:]]*\.exe[[:space:]]*$' ffbuild/config.mak || {
    echo 'Native Windows FFmpeg configure did not select EXESUF=.exe; refusing mismatched build' >&2
    exit 1
  }
fi
"$make_command" -j "${TLO_FFMPEG_MAKE_JOBS:-2}" all
if [[ "${MSYSTEM:-}" == UCRT64 ]]; then
  binary=ffmpeg.exe
else
  binary=ffmpeg
fi
[[ -f "$binary" ]] || {
  echo "FFmpeg expected executable $binary missing after make all; refusing to package an incorrect platform binary" >&2
  exit 1
}
cp -- "$binary" "$output"
# Keep build configuration for post-build and source-provenance receipt.
cp -- ffbuild/config.log "${output}.config.log"
printf '%s\n' "${source_dir}/configure" '--disable-autodetect --disable-everything --enable-small --disable-network --disable-ffplay --disable-ffprobe --disable-doc --disable-debug --disable-avdevice --disable-swscale --disable-iconv --disable-bzlib --disable-lzma --disable-zlib --disable-x86asm --enable-ffmpeg --enable-static --disable-shared' > "${output}.build-recipe.txt"
