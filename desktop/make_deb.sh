#!/usr/bin/env bash
# Maakt een .deb-pakket van de gebouwde programmamap.
# Gebruik: desktop/make_deb.sh <build_exe-map> <versie> <uitvoer.deb>
set -euo pipefail
SRC="$1"; VERSION="$2"; OUT="$3"
HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$(mktemp -d)/pkg"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/anything-converter" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"
cp -a "$SRC/." "$PKG/opt/anything-converter/"
ln -s /opt/anything-converter/AnythingConverter "$PKG/usr/bin/anything-converter"
cp "$HERE/icons/app-256.png" "$PKG/usr/share/icons/hicolor/256x256/apps/anything-converter.png"
cat > "$PKG/usr/share/applications/anything-converter.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Anything Converter
Comment=Converteer, verklein, vergroot en knip bestanden
Exec=/opt/anything-converter/AnythingConverter
Icon=anything-converter
Terminal=false
Categories=AudioVideo;Graphics;Utility;
DESKTOP
SIZE_KB=$(du -sk "$PKG/opt" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CONTROL
Package: anything-converter
Version: $VERSION
Section: utils
Priority: optional
Architecture: amd64
Installed-Size: $SIZE_KB
Maintainer: Anything Converter <noreply@users.noreply.github.com>
Description: Converteer, verklein, vergroot en knip bestanden
 Lokale converter voor video, audio, afbeeldingen, PDF en meer, met ffmpeg,
 yt-dlp en Deno meegeleverd. Opent in je browser.
CONTROL
dpkg-deb --build --root-owner-group "$PKG" "$OUT"
echo "gemaakt: $OUT"
