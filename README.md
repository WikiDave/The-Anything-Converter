# The Anything Converter

Een lokale web-app om (bijna) elk bestand te **converteren**, **kleiner of groter te maken** tot een exacte
bestandsgrootte in KB/MB/GB, en **video's en audio te knippen**. Alles draait op je eigen computer;
bestanden worden na 1 uur automatisch opgeruimd. De interface heeft een retro terminal-/ASCII-stijl met drie kleurthema's (groen, amber, cyaan).

## Wat kan het?

| Soort | Converteren naar | Grootte (kleiner/groter) | Knippen |
|---|---|---|---|
| **Video** (mp4, mov, mkv, webm, avi, wmv, flv, …) | mp4, webm, mkv, mov, avi, gif, of alleen audio (mp3, m4a, wav, ogg) | Doelgrootte via 2-pass codering; groter = hogere bitrate. Resolutie kiezen, geluid verwijderen | ✅ met preview en schuifregelaars, ook snel knippen zonder hercoderen |
| **Audio** (mp3, wav, flac, m4a, ogg, opus, …) | mp3, m4a, aac, wav, flac, ogg, opus | Doelgrootte via bitrate | ✅ |
| **Afbeeldingen** (jpg, png, webp, gif, heic, avif, tiff, bmp, svg, psd, …) | jpg, png, webp, avif, gif, bmp, tiff, ico, pdf | Kleiner: kwaliteit/resolutie zoeken; groter: kwaliteit + opschalen. Schalen op % of pixels | – |
| **PDF** | pdf (comprimeren), docx, odt, txt, html, png/jpg (per pagina) | Doelgrootte door afbeeldingen te herschalen/comprimeren | – |
| **Documenten** (docx, doc, odt, rtf, md, html, txt, epub, …) | pdf, docx, odt, rtf, txt, html, md, epub | Via PDF-uitvoer | – |
| **Spreadsheets** (xlsx, xls, ods, csv) | xlsx, ods, csv, pdf, html | – | – |
| **Presentaties** (pptx, ppt, odp) | pdf, pptx, odp | – | – |
| **Archieven & overig** | zip, tar.gz, tar.bz2, tar.xz | Maximale verliesvrije compressie | – |

> Let op: "groter maken" werkt voor video's, audio en afbeeldingen (meer bitrate/kwaliteit/resolutie).
> Al gecomprimeerde bestanden (zip, jpg in een zip, …) kunnen verliesvrij nauwelijks kleiner.

## Starten

### Optie 1 – Docker (aanbevolen, alles inbegrepen)

```bash
docker compose up --build
```

Open daarna <http://localhost:8000>.

### Optie 2 – Direct op je computer

Benodigd: **Python 3.10+** en **ffmpeg**. Optioneel voor meer formaten: LibreOffice (Office-documenten),
pandoc (Markdown/HTML/EPUB), Ghostscript (betere PDF-compressie), poppler-utils (PDF → afbeelding),
ImageMagick (HEIC/SVG/PSD).

- **Windows:** dubbelklik `start.bat` (installeer ffmpeg bijv. met `winget install ffmpeg`)
- **macOS / Linux:** `./start.sh` (macOS: `brew install ffmpeg libreoffice pandoc ghostscript poppler imagemagick`)

De browser opent vanzelf op <http://localhost:8000>.

## Gebruik

1. Sleep een bestand in het venster.
2. Kies het uitvoerformaat.
3. Kies **Kwaliteit** (hoog/normaal/laag) óf **Doelgrootte** (bijv. `8 MB` of `500 KB`; knoppen voor 10%, 50%, 2× groter…).
4. Bij video/audio: knip met de schuifregelaars of de knoppen *hier* tijdens het afspelen.
5. Klik **Start** en download het resultaat. Je ziet direct hoeveel kleiner/groter het is geworden.

## Instellingen (omgevingsvariabelen)

| Variabele | Standaard | Betekenis |
|---|---|---|
| `PORT` | `8000` | Poort van de webserver |
| `HOST` | `127.0.0.1` | Gebruik `0.0.0.0` om de converter op je netwerk te delen |
| `CONVERTER_MAX_MB` | `4096` | Maximale uploadgrootte |
| `CONVERTER_WORKDIR` | tijdelijke map | Waar uploads en resultaten tijdelijk staan |

## Ontwikkeling

```bash
pip install -r requirements-dev.txt
python -m pytest
```

Structuur: `app.py` (Flask-server), `converter/` (detectie, media, afbeelding, document, archief, jobs),
`static/` (interface).

## Browser-versie (zonder installatie)

`web/index.html` is een losse versie die volledig in de browser draait (WebCodecs via Mediabunny,
canvas voor afbeeldingen). Niets wordt geüpload. Open het bestand via een webserver of zet het op
GitHub Pages. Ondersteund: video (mp4/mov/webm/mkv) → mp4, webm, gif, mp3, m4a, wav; audio → mp3, m4a,
ogg, wav, webm; afbeeldingen → jpg, png, webp, gif, pdf, bmp, ico; overige bestanden → zip. Knippen en
doelgrootte werken ook. Word/Excel/PowerPoint/PDF-conversie en avi/wmv vereisen de lokale versie.
