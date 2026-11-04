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

## Terminalversie (Windows Terminal, PowerShell, bash, SSH)

Dezelfde ASCII-layout als de web-app, maar als terminalprogramma: werkt in Windows Terminal/PowerShell, in
bash/zsh op macOS en Linux, en via SSH op een server zonder scherm. Muis en toetsenbord werken allebei.

- **Converteren**: bestand kiezen in de mapboom (of een pad plakken), formaat, kwaliteit of doelgrootte, knippen,
  resolutie; het resultaat komt naast het bestand (of in een gekozen map) met een ORIGINEEL/NIEUW-vergelijking.
- **Link & torrent**: video-links, magnet-links en .torrent-bestanden, met viruscheck na het downloaden.
- **Virusscan**: elk bestand of map scannen; VirusTotal-sleutel instellen.
- Toetsen: `ctrl+s` start, `ctrl+t` kleur (groen/amber/cyaan), `ctrl+o` pad, `ctrl+q` afsluiten.

Starten: in de desktop-app klik je bovenin op **[ TERMINAL ]**: er opent een terminalvenster met de
terminalversie. Op Windows staat ook **Anything Converter (terminal)** in het Startmenu, op Linux in het
programmamenu. Of typ zelf:

| Waar | Commando |
|---|---|
| Windows (na de .msi) | `anything-converter-tui` in een nieuwe terminal |
| Ubuntu/Debian (.deb) | `anything-converter-tui` |
| AppImage | `./AnythingConverter-Linux.AppImage tui` |
| macOS | `"/Applications/Anything Converter.app/Contents/MacOS/anything-converter-tui"` |
| Homebrew (macOS, Linux) | `brew install anything-converter` (zie hieronder) |
| Vanuit de broncode / via SSH | `pip install -r requirements.txt` en `python tui.py [bestand]` |

**Via Homebrew** (alleen de terminalversie, macOS en Linux; zonder Apple-melding):

```
brew tap wikidave/anything-converter https://github.com/WikiDave/The-Anything-Converter
brew trust wikidave/anything-converter
brew install anything-converter
anything-converter-tui
```

Bijwerken met `brew upgrade anything-converter`. De formule (`Formula/anything-converter.rb`) wordt bij elke
release automatisch bijgewerkt.

## Talen

De web-app is er in 14 talen: Nederlands, English, Deutsch, Español, Français, Português, Русский, Türkçe,
Bahasa Indonesia, العربية (van rechts naar links), हिन्दी, বাংলা, 中文 en 日本語. De taal van je browser wordt
automatisch gekozen; wisselen kan met het keuzemenu bovenaan.

Vertalingen staan in `i18n/<taal>.txt`: één regel per tekst, in dezelfde volgorde als `i18n/keys.py`
(de Nederlandse brontekst). Na een wijziging: `python i18n/build.py`. De lokale/desktop-startpagina is nog
Nederlands; de werkbanken (via **[ PDF & ARCHIEF ]**) zijn vertaald.

## Social media

Tabblad **[ SOCIAL MEDIA ]** in de web-app: kies een platform en formaat, en foto's en video's krijgen exact de
afmetingen die het platform zelf gebruikt. Dan schaalt Instagram/Facebook niets meer en blijft de kwaliteit zo hoog
mogelijk.

- **45 formaten** voor Instagram, Facebook, YouTube, TikTok, X/Twitter, LinkedIn, Pinterest, Snapchat, Threads,
  WhatsApp, Bluesky en Twitch: posts (staand 4:5, vierkant, liggend), stories/reels/shorts (9:16), omslag- en
  profielfoto's, banners, thumbnails en video (YouTube tot 4K).
- **Passen**: vullen met bijsnijden (sleep in het voorbeeld en zoom in om te kiezen wat zichtbaar blijft), of passend
  met een vage achtergrond van dezelfde foto, of met zwarte/witte randen.
- **Panorama-carrousel**: een brede foto wordt in naadloze slides (4:5 of 1:1, 2–10 stuks) geknipt. Upload ze in
  volgorde als één carrousel; door te swipen zie je het hele panorama.
- Foto's worden jpg onder de maximale bestandsgrootte van het platform; video's mp4 (H.264 + AAC) met een passende bitrate.
- Profielfoto's tonen een ronde uitsnede in het voorbeeld; de YouTube-banner toont de veilige zone.

## Archief-werkbank (zip, rar, 7z, tar …)

In de web-app (en in de desktop-app via **[ PDF & ARCHIEF ]**) staat de **ARCHIEF-WERKBANK**:

- **Openen**: zip, rar, 7z, tar, tar.gz/.tgz, tar.bz2, tar.xz, gz, bz2, xz, zst, iso, cab, jar, lzh en meer,
  ook versleutelde archieven (wachtwoord invullen). Meerdere archieven tegelijk komen elk in een eigen map.
- **Bekijken**: de inhoud als ASCII-boom met mappen, aantallen en groottes, en een zoekveld.
- **Weglaten**: vink bestanden of hele mappen uit.
- **Toevoegen**: bestanden in een gekozen map, en losse bestanden uit de lijst gaan ook mee.
- **Los opslaan**: elk bestand met [↓].
- **Nieuw leeg archief**: met **[ + NIEUW LEEG ARCHIEF ]** op het startscherm begin je zonder archief en voeg je zelf bestanden en mappen toe.
- **Opslaan als**: .zip (optioneel met AES-256-wachtwoord), .7z, .tar, .tar.gz, .tar.xz, .tar.bz2 of .iso.
  Dubbele namen (bijv. iPhone-foto's die allemaal `image.jpg` heten) worden automatisch `image_2.jpg` enz.
  RAR maken kan niet: alleen WinRAR mag dat formaat maken. Openen en uitpakken van rar kan wel.

Werkt met [libarchive.js](https://github.com/nika-begiashvili/libarchivejs) (meegeleverd in `vendor/`) en
[zip.js](https://github.com/gildas-lormeau/zip.js).

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
| Android 10+ | `AnythingConverter-Android.apk` |
| iPhone / iPad | geen bestand: open de web-app in Safari → Deel → Zet op beginscherm |

ffmpeg, yt-dlp (video-links) en Deno zitten erin; je hoeft niets anders te installeren. De converter
opent in een **eigen programmavenster**, zonder browser en zonder adresbalk (WebView2 op Windows, WebKit op
macOS en Linux). Venster dicht = programma af. Opslaan gaat via het gewone "Bewaar als"-venster, links naar
buiten openen in je browser, en **[ PDF & ARCHIEF ]** opent in een tweede venster.
Lukt een eigen venster niet (Windows zonder WebView2, Linux zonder GTK/WebKit), dan valt de app terug op
een los app-venster van Edge/Chrome, en als laatste op de gewone browser met **[ AFSLUITEN ]** bovenaan.
Voor Word/Excel/PowerPoint-conversie installeer je los [LibreOffice](https://www.libreoffice.org);
de app vindt het vanzelf.

De app is niet betaald ondertekend, dus de eerste keer:
- **Windows**: "Windows heeft uw pc beschermd" → **Meer informatie** → **Toch uitvoeren**.
- **macOS** ("Apple kon niet verifiëren…"): klik **Gereed** (niet "Verplaats naar prullenmand"), ga naar
  **Systeeminstellingen → Privacy en beveiliging**, scroll naar beneden → **Toch openen**. Of in Terminal:
  `xattr -dr com.apple.quarantine "/Applications/Anything Converter.app"`.

**Android**: de app (`android/`) toont de web-app en voegt bestanden kiezen via Android en opslaan in
**Downloads/Anything Converter** toe. Installeren: open de .apk en sta "installeren van onbekende apps" toe.
YouTube-links ophalen kan alleen in de desktop-app.

Zodat een nieuwe versie als update over de oude heen installeert, kun je een vaste sleutel als GitHub-geheim
instellen (eenmalig; zonder geheim wordt met een tijdelijke debug-sleutel ondertekend):

```bash
keytool -genkeypair -keystore release.jks -alias anything -keyalg RSA -keysize 2048 -validity 10000
base64 -w0 release.jks   # macOS: base64 -i release.jks
```

Zet in **Settings → Secrets and variables → Actions**: `ANDROID_KEYSTORE_B64` (de base64-tekst),
`ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS` (`anything`) en `ANDROID_KEY_PASSWORD`.
Bewaar `release.jks` zelf veilig en zet hem nooit in de repository.

**iPhone/iPad**: Apple staat apps buiten de App Store niet toe zonder betaald ontwikkelaarsaccount.
Gebruik de web-app via Safari → Deel → Zet op beginscherm.

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

## Torrents (lokale versie en desktop-app)

In hetzelfde kader als de video-links: plak een **magnet-link** of klik **[ .TORRENT KIEZEN ]** (of sleep een
.torrent-bestand op het sleepvak). Je ziet voortgang, snelheid en het aantal peers, en kunt stoppen met **[ STOP ]**.
Eén bestand gaat direct de converter in; bij meerdere bestanden krijg je een lijst met **[ OPENEN ]** en **[↓]** per
bestand. Werkt met [libtorrent](https://www.libtorrent.org) (in `requirements.txt` en in de installers).
Alleen voor legale inhoud: eigen bestanden, open-source software en Linux-ISO's, vrije licenties of met toestemming.
Windows kan de eerste keer vragen of de app door de firewall mag; dat is nodig om met peers te verbinden.

## Viruscontrole

- **Desktop-app/lokale versie**: video-links en torrents worden na het downloaden automatisch gescand
  (vinkje **Controleren op virussen**). Gebruikt de scanner die al op de computer staat: Microsoft Defender
  (Windows, standaard aanwezig) of ClamAV (macOS: `brew install clamav`, Linux: `sudo apt install clamav`).
  Wordt er iets gevonden, dan wordt het bestand niet geopend en kun je het met **[ VERWIJDEREN ]** wissen.
  Elk geopend bestand kun je ook los scannen met **[ VIRUSSCAN ]**.
- **VirusTotal**: van elk bestand wordt een SHA-256-vingerafdruk gemaakt met een link naar VirusTotal (70+ scanners).
  Met een gratis API-sleutel (in het kader *VIRUSSCANNER & VIRUSTOTAL*) gebeurt dat automatisch. Alleen de
  vingerafdruk wordt gedeeld, nooit het bestand. De sleutel staat alleen op je eigen computer.
- **Web-app**: de knop **[VT]** per bestand opent de VirusTotal-controle via dezelfde vingerafdruk.

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
