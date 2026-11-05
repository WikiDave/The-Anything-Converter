#!/usr/bin/env bash
# Haalt ffmpeg, ffprobe, deno en 7-Zip op voor één platform en zet ze in desktop/bin/.
# Gebruik: desktop/fetch_bins.sh win-x64 | mac-arm64 | mac-x64 | linux-x64
set -euo pipefail
PLATFORM="$1"
DENO_VERSION="v2.5.6"
SEVENZIP_VERSION="25.01"   # 7-Zip: RAR, CAB, DMG, WIM, VHD(X), VMDK, MSI, CHM, RPM, ... uitpakken
HERE="$(cd "$(dirname "$0")" && pwd)"
BIN="$HERE/bin"
TMP="$(mktemp -d)"
PY="$(command -v python || command -v python3)"
rm -rf "$BIN"
mkdir -p "$BIN"
get() { curl -fsSL --retry 4 --retry-delay 5 -o "$2" "$1"; }
unzip_to() { "$PY" -m zipfile -e "$1" "$2"; }

case "$PLATFORM" in
  win-x64)
    get https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip "$TMP/ff.zip"
    unzip_to "$TMP/ff.zip" "$TMP/ff"
    cp "$TMP"/ff/*/bin/ffmpeg.exe "$TMP"/ff/*/bin/ffprobe.exe "$BIN/"
    DENO_TARGET=x86_64-pc-windows-msvc
    ;;
  mac-arm64|mac-x64)
    if [ "$PLATFORM" = mac-arm64 ]; then ARCH=arm64; DENO_TARGET=aarch64-apple-darwin
    else ARCH=amd64; DENO_TARGET=x86_64-apple-darwin; fi
    for tool in ffmpeg ffprobe; do
      get "https://ffmpeg.martin-riedl.de/redirect/latest/macos/$ARCH/release/$tool.zip" "$TMP/$tool.zip"
      unzip_to "$TMP/$tool.zip" "$TMP/$tool"
      find "$TMP/$tool" -type f -name "$tool" -exec cp {} "$BIN/$tool" \;
    done
    ;;
  linux-x64)
    get https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz "$TMP/ff.tar.xz"
    tar -xJf "$TMP/ff.tar.xz" -C "$TMP"
    cp "$TMP"/ffmpeg-*-static/ffmpeg "$TMP"/ffmpeg-*-static/ffprobe "$BIN/"
    DENO_TARGET=x86_64-unknown-linux-gnu
    ;;
  *)
    echo "onbekend platform: $PLATFORM" >&2
    exit 1
    ;;
esac

# 7-Zip (officiële builds van 7-zip.org, via GitHub). Mislukt dit, dan werkt de rest gewoon.
SZ="https://github.com/ip7z/7zip/releases/download/$SEVENZIP_VERSION"
SZV="${SEVENZIP_VERSION//./}"
(
  case "$PLATFORM" in
    win-x64)
      get "$SZ/7zr.exe" "$TMP/7zr.exe"
      get "$SZ/7z$SZV-x64.exe" "$TMP/7z-setup.exe"
      "$TMP/7zr.exe" x -y "-o$TMP/7z" "$TMP/7z-setup.exe" > /dev/null
      cp "$TMP/7z/7z.exe" "$TMP/7z/7z.dll" "$BIN/" ;;
    mac-*)
      get "$SZ/7z$SZV-mac.tar.xz" "$TMP/7z.tar.xz"
      mkdir -p "$TMP/7z" && tar -xJf "$TMP/7z.tar.xz" -C "$TMP/7z"
      cp "$TMP/7z/7zz" "$BIN/" ;;
    linux-x64)
      get "$SZ/7z$SZV-linux-x64.tar.xz" "$TMP/7z.tar.xz"
      mkdir -p "$TMP/7z" && tar -xJf "$TMP/7z.tar.xz" -C "$TMP/7z"
      cp "$TMP/7z/7zz" "$BIN/" ;;
  esac
) || echo "::warning::7-Zip ophalen mislukt; exotische archieven werken dan alleen als 7-Zip los geïnstalleerd is."

get "https://github.com/denoland/deno/releases/download/$DENO_VERSION/deno-$DENO_TARGET.zip" "$TMP/deno.zip"
unzip_to "$TMP/deno.zip" "$BIN"
chmod +x "$BIN"/* 2>/dev/null || true
ls -la "$BIN"
