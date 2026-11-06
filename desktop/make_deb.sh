#!/usr/bin/env bash
# Maakt een .deb-pakket van de gebouwde programmamap.
# Gebruik: desktop/make_deb.sh <build_exe-map> <versie> <uitvoer.deb>
set -euo pipefail
SRC="$1"; VERSION="$2"; OUT="$3"
case "$(uname -m)" in aarch64|arm64) DEB_ARCH=arm64 ;; *) DEB_ARCH=amd64 ;; esac
HERE="$(cd "$(dirname "$0")" && pwd)"
PKG="$(mktemp -d)/pkg"
mkdir -p "$PKG/DEBIAN" "$PKG/opt/anything-converter" "$PKG/usr/bin" \
         "$PKG/usr/share/applications" "$PKG/usr/share/icons/hicolor/256x256/apps"
cp -a "$SRC/." "$PKG/opt/anything-converter/"
ln -s /opt/anything-converter/AnythingConverter "$PKG/usr/bin/anything-converter"
ln -s /opt/anything-converter/anything-converter-tui "$PKG/usr/bin/anything-converter-tui"
cp "$HERE/icons/app-256.png" "$PKG/usr/share/icons/hicolor/256x256/apps/anything-converter.png"
cat > "$PKG/usr/share/applications/anything-converter.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Anything Converter
Comment=Convert, shrink, enlarge and trim files
Exec=/opt/anything-converter/AnythingConverter %F
Icon=anything-converter
Terminal=false
Categories=AudioVideo;Graphics;Utility;
MimeType=video/mp4;video/x-matroska;video/quicktime;video/webm;video/x-msvideo;video/x-ms-wmv;video/mpeg;video/x-flv;audio/mpeg;audio/x-wav;audio/wav;audio/flac;audio/ogg;audio/mp4;audio/aac;audio/x-m4a;audio/opus;image/jpeg;image/png;image/gif;image/webp;image/heic;image/heif;image/avif;image/svg+xml;image/tiff;image/bmp;image/x-icon;application/pdf;application/msword;application/vnd.openxmlformats-officedocument.wordprocessingml.document;application/vnd.ms-excel;application/vnd.openxmlformats-officedocument.spreadsheetml.sheet;application/vnd.ms-powerpoint;application/vnd.openxmlformats-officedocument.presentationml.presentation;application/vnd.oasis.opendocument.text;application/vnd.oasis.opendocument.spreadsheet;application/rtf;application/epub+zip;application/zip;application/x-7z-compressed;application/vnd.rar;application/x-tar;application/gzip;application/x-iso9660-image;application/x-cue;text/plain;text/csv;text/markdown;text/html;application/json;application/xml;application/x-subrip;text/vtt;font/ttf;font/otf;model/stl;application/x-sqlite3;application/octet-stream;
DESKTOP
# KDE Dolphin: right-click > Convert with Anything Converter
mkdir -p "$PKG/usr/share/kio/servicemenus"
cat > "$PKG/usr/share/kio/servicemenus/anything-converter.desktop" <<DESKTOP
[Desktop Entry]
Type=Service
MimeType=all/allfiles;
X-KDE-ServiceTypes=KonqPopupMenu/Plugin
Actions=convert;

[Desktop Action convert]
Name=Convert with Anything Converter
Icon=anything-converter
Exec=/opt/anything-converter/AnythingConverter %F
DESKTOP
chmod +x "$PKG/usr/share/kio/servicemenus/anything-converter.desktop"
cat > "$PKG/usr/share/applications/anything-converter-tui.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Anything Converter (terminal)
Comment=Terminal version of Anything Converter
Exec=/opt/anything-converter/anything-converter-tui %f
Icon=anything-converter
Terminal=true
Categories=AudioVideo;Graphics;Utility;ConsoleOnly;
DESKTOP
SIZE_KB=$(du -sk "$PKG/opt" | cut -f1)
cat > "$PKG/DEBIAN/control" <<CONTROL
Package: anything-converter
Version: $VERSION
Section: utils
Priority: optional
Architecture: $DEB_ARCH
Installed-Size: $SIZE_KB
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-webkit2-4.1 | gir1.2-webkit2-4.0
Recommends: tesseract-ocr, tesseract-ocr-nld, tesseract-ocr-eng
Suggests: calibre, libreoffice
Maintainer: Anything Converter <noreply@users.noreply.github.com>
Description: Converteer, verklein, vergroot en knip bestanden
 Lokale converter voor video, audio, afbeeldingen, PDF en meer, met ffmpeg,
 yt-dlp en Deno meegeleverd. Opent in een eigen programmavenster.
CONTROL
dpkg-deb --build --root-owner-group "$PKG" "$OUT"
echo "gemaakt: $OUT"
