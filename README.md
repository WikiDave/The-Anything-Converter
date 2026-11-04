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

## Desktop-app (installer, alles inbegrepen)

Download de installer voor jouw systeem van de
[nieuwste release](https://github.com/WikiDave/The-Anything-Converter/releases/latest):

| Systeem | Bestand |
|---|---|
| Windows 10/11 | `AnythingConverter-Windows.msi` |
| Mac met M1/M2/M3/M4 | `AnythingConverter-macOS-AppleSilicon.dmg` |
| Mac met Intel | `AnythingConverter-macOS-Intel.dmg` |
| Ubuntu / Debian / Mint | `AnythingConverter-Linux.deb` |
| Andere Linux | `AnythingConverter-Linux.AppImage` |

ffmpeg, yt-dlp (video-links) en Deno zitten erin; je hoeft niets anders te installeren. Na het
starten opent de converter in je browser. Afsluiten met **[ AFSLUITEN ]** bovenaan de pagina.
Voor Word/Excel/PowerPoint-conversie installeer je los [LibreOffice](https://www.libreoffice.org);
de app vindt het vanzelf.

De app is niet betaald ondertekend, dus de eerste keer:
- **Windows**: "Windows heeft uw pc beschermd" → **Meer informatie** → **Toch uitvoeren**.
- **macOS**: open de app, sluit de melding, ga naar **Systeeminstellingen → Privacy en beveiliging** → **Toch openen**.

De installers worden gebouwd door `.github/workflows/desktop.yml` (cx_Freeze). Een nieuwe release
maak je via **Actions → Desktop-installers → Run workflow**.

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

## Video ophalen via een link (alleen lokale versie)

Onder het sleepvak staat **OF PLAK EEN LINK**: plak een link van YouTube, Vimeo of een van de
[vele andere sites](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md) en klik
**[ OPHALEN ]**. De video (of met *Alleen geluid* alleen de audio) komt direct in de converter,
zodat je kunt knippen, verkleinen of omzetten, of met **[ ↓ OPSLAAN ]** het origineel bewaart.

- Werkt met [yt-dlp](https://github.com/yt-dlp/yt-dlp) (staat in `requirements.txt`). Voor YouTube
  heeft yt-dlp een JavaScript-runtime nodig: installeer [Deno](https://deno.com) (`brew install deno`,
  `winget install DenoLand.Deno`). In Docker zit Deno er al in.
- Sites veranderen vaak; werkt een link niet meer, werk yt-dlp bij: `pip install -U "yt-dlp[default]"`.
- Alleen voor je eigen video's, video's met een vrije licentie (bijv. Creative Commons) of met
  toestemming van de maker. Downloaden van andermans video's kan tegen de voorwaarden van de site
  en het auteursrecht ingaan.
- In de browser-versie (GitHub Pages) kan dit niet: een webpagina mag geen video's van andere sites ophalen.

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

`index.html` (in de hoofdmap) is een losse versie die volledig in de browser draait (WebCodecs via Mediabunny,
canvas voor afbeeldingen). Niets wordt geüpload. Online via GitHub Pages: <https://wikidave.github.io/The-Anything-Converter/>
(GitHub Pages publiceert de hoofdmap van de branch; elke push werkt de site bij). Je kunt meerdere bestanden tegelijk verwerken en alles in één zip opslaan. Ondersteund: video (mp4/mov/webm/mkv) → mp4, webm, gif, mp3, m4a, wav; audio → mp3, m4a,
ogg, wav, webm; afbeeldingen → jpg, png, webp, gif, pdf, bmp, ico; overige bestanden → zip. Knippen en
doelgrootte werken ook. PDF: een PDF-werkbank om PDF's en foto's samen te voegen, pagina's te ordenen, draaien en verwijderen, te splitsen
(per pagina of bereik), paginanummers en een watermerk toe te voegen, titel/auteur in te stellen en te comprimeren;
losse PDF's kunnen ook naar jpg/png (per pagina) of tekst. Word/Excel/PowerPoint en avi/wmv vereisen de lokale versie.
