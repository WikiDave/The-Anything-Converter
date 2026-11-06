#!/usr/bin/env bash
# Maakt een AppImage van de gebouwde programmamap.
# Gebruik: desktop/make_appimage.sh <build_exe-map> <uitvoer.AppImage>
set -euo pipefail
SRC="$1"; OUT="$2"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
APPDIR="$WORK/AnythingConverter.AppDir"
mkdir -p "$APPDIR/usr/lib/anything-converter"
cp -a "$SRC/." "$APPDIR/usr/lib/anything-converter/"

cat > "$APPDIR/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
# ./AnythingConverter-Linux.AppImage tui  -> terminalversie
if [ "$1" = "tui" ]; then shift; exec "$HERE/usr/lib/anything-converter/anything-converter-tui" "$@"; fi
exec "$HERE/usr/lib/anything-converter/AnythingConverter" "$@"
APPRUN

cat > "$APPDIR/anything-converter.desktop" <<'DESKTOP'
[Desktop Entry]
Type=Application
Name=Anything Converter
Comment=Convert, shrink, enlarge and trim files
Exec=AnythingConverter %F
Icon=anything-converter
Terminal=false
Categories=AudioVideo;Graphics;Utility;
DESKTOP

# the icon must sit at the top of the AppDir with the name from Icon=
cp "$HERE/icons/app-256.png" "$APPDIR/anything-converter.png"
chmod -R a+rX "$APPDIR"
chmod 0755 "$APPDIR/AppRun"

TOOL="$WORK/appimagetool"
case "$(uname -m)" in aarch64|arm64) AI_ARCH=aarch64 ;; *) AI_ARCH=x86_64 ;; esac
curl -fsSL --retry 4 -o "$TOOL" \
  "https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-$AI_ARCH.AppImage"
chmod +x "$TOOL"
# run without FUSE (CI machines)
APPIMAGE_EXTRACT_AND_RUN=1 ARCH=$AI_ARCH "$TOOL" "$APPDIR" "$OUT"
chmod 0755 "$OUT"
echo "made: $OUT"
