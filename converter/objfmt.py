"""Lettertypes, e-mail, contacten, agenda, GPS, 3D-modellen, CAD (DXF), vectorbeelden, certificaten en DICOM."""
from __future__ import annotations

import csv
import email
import html
import io
import json
import re
import zipfile
from email import policy
from pathlib import Path
from xml.etree import ElementTree as ET

from .util import ConversionError, have

FONTS = {"ttf", "otf", "ttc", "otc", "woff", "woff2", "dfont"}
MAIL = {"eml", "emlx", "msg", "oft", "mbox", "tnef", "p7m"}
CONTACT = {"vcf"}
CALENDAR = {"ics", "vcs"}
GPS = {"gpx", "kml", "kmz", "geojson", "tcx", "fit", "igc", "loc"}
MODEL3D = {"stl", "obj", "ply", "off", "glb", "gltf", "3mf", "dae", "xyz", "pts", "3ds-model"}
CAD = {"dxf"}
VECTOR = {"svg", "svgz", "ai", "xps", "oxps", "eps", "ps", "gv", "dot-graph"}
CERT = {"pem", "crt", "cer", "der", "p7b", "p7c", "csr", "crl", "key", "pub"}
MEDICAL = {"dcm"}


def targets(fam: str, ext: str) -> list[str]:
    if fam == "font":
        out = ["ttf", "woff", "woff2", "otf", "png", "pdf"]
        if ext in ("ttc", "otc"):
            out = ["zip", "png", "pdf"]
        return [t for t in out if t != ext]
    if fam == "mail":
        return ["zip", "csv", "txt"] if ext == "mbox" else ["pdf", "html", "txt", "zip", "eml"] if ext in (
            "msg", "oft", "emlx", "tnef", "p7m") else ["pdf", "html", "txt", "zip"]
    if fam == "contact":
        return ["csv", "xlsx", "json", "txt"]
    if fam == "calendar":
        return ["csv", "xlsx", "json", "txt", "html"]
    if fam == "gps":
        return [t for t in ("gpx", "kml", "kmz", "geojson", "csv", "tcx") if t != ext]
    if fam == "model3d":
        return [t for t in ("stl", "obj", "ply", "glb", "off", "3mf") if t != ext]
    if fam == "cad":
        return ["svg", "pdf", "png"]
    if fam == "vector":
        out = ["png", "pdf", "jpg", "webp", "svg"]
        return [t for t in out if t != ext.replace("svgz", "svg")]
    if fam == "cert":
        return ["txt", "pem", "der"]
    if fam == "medical":
        return ["png", "jpg", "tiff", "txt"]
    return []


# --------------------------------------------------------------------------- lettertypes

def font(src: Path, out_dir: Path, fmt: str) -> Path:
    from fontTools.ttLib import TTCollection, TTFont
    ext = src.suffix.lower().lstrip(".")
    if ext in ("ttc", "otc"):
        coll = TTCollection(str(src))
        if fmt == "zip":
            dst = out_dir / f"{src.stem}.zip"
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
                for i, f in enumerate(coll.fonts):
                    buf = io.BytesIO()
                    f.save(buf)
                    name = f["name"].getDebugName(4) or f"font{i}"
                    z.writestr(re.sub(r"[^\w .-]", "_", name) + (".otf" if "CFF " in f else ".ttf"), buf.getvalue())
            return dst
        f = coll.fonts[0]
    else:
        f = TTFont(str(src))
    dst = out_dir / f"{src.stem}.{fmt}"
    if fmt in ("png", "pdf"):
        return font_specimen(f, src, dst, fmt)
    is_cff = "CFF " in f or "CFF2" in f
    if fmt == "otf" and not is_cff:
        raise ConversionError("Dit is een TrueType-lettertype; omzetten naar OpenType-CFF wordt niet ondersteund. "
                              "Een .ttf werkt overal waar .otf werkt.")
    if fmt == "ttf" and is_cff:
        f = _cff_to_ttf(f)
    f.flavor = {"woff": "woff", "woff2": "woff2"}.get(fmt)
    f.save(str(dst))
    return dst


def _cff_to_ttf(f):
    """OpenType-CFF naar TrueType (kubische naar kwadratische curven)."""
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable
    gs = f.getGlyphSet()
    glyf = newTable("glyf")
    glyf.glyphs = {}
    glyf.glyphOrder = f.getGlyphOrder()
    for name in f.getGlyphOrder():
        pen = TTGlyphPen(gs)
        gs[name].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
        glyf.glyphs[name] = pen.glyph()
    del f["CFF "]
    if "VORG" in f:
        del f["VORG"]
    f["glyf"] = glyf
    f["loca"] = newTable("loca")
    maxp = f["maxp"]
    maxp.tableVersion = 0x00010000
    for attr in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
                 "maxStackElements", "maxSizeOfInstructions", "maxComponentElements", "maxPoints", "maxContours",
                 "maxCompositePoints", "maxCompositeContours", "maxComponentDepth"):
        setattr(maxp, attr, 0 if attr not in ("maxZones",) else 1)
    f["head"].indexToLocFormat = 0
    f["head"].glyphDataFormat = 0
    f["post"].formatType = 2.0
    f.sfntVersion = "\x00\x01\x00\x00"
    return f


def font_specimen(f, src: Path, dst: Path, fmt: str) -> Path:
    import tempfile
    from PIL import Image, ImageDraw, ImageFont
    tmp = Path(tempfile.mkdtemp()) / "f.ttf"
    f.flavor = None
    f.save(str(tmp))
    name = f["name"].getDebugName(4) or src.stem
    im = Image.new("RGB", (1600, 1000), "white")
    d = ImageDraw.Draw(im)
    label = ImageFont.load_default(size=22)
    d.text((40, 24), f"{name}  ·  {src.name}  ·  {len(f.getGlyphOrder())} tekens", fill=(90, 90, 90), font=label)
    y = 80
    for size, text in ((96, "Aa Bb Cc 123"), (56, "ABCDEFGHIJKLMNOPQRSTUVWXYZ"), (56, "abcdefghijklmnopqrstuvwxyz"),
                       (48, "0123456789 !?&@€$%()[]"), (36, "De snelle bruine vos springt over de luie hond."),
                       (24, "Pa's wijze lynx bezag vroom het fikse aquaduct.")):
        try:
            fnt = ImageFont.truetype(str(tmp), size)
            d.text((40, y), text, fill="black", font=fnt)
        except OSError:
            d.text((40, y), "(dit lettertype kan niet getekend worden)", fill="red", font=label)
            break
        y += int(size * 1.35) + 10
    im = im.crop((0, 0, 1600, min(1000, y + 40)))
    im.save(dst, "PDF" if fmt == "pdf" else "PNG", resolution=150)
    return dst


# --------------------------------------------------------------------------- e-mail

def _parse_mail(src: Path):
    ext = src.suffix.lower().lstrip(".")
    data = src.read_bytes()
    if ext == "emlx":
        first, _, rest = data.partition(b"\n")
        n = int(first.strip() or 0)
        data = rest[:n] if n else rest
    if ext in ("msg", "oft"):
        try:
            import extract_msg
        except ImportError as e:
            raise ConversionError("Outlook-berichten lezen vraagt extract-msg.") from e
        m = extract_msg.openMsg(str(src))
        atts = []
        for a in m.attachments:
            name = getattr(a, "longFilename", None) or getattr(a, "shortFilename", None) or "bijlage"
            payload = getattr(a, "data", b"")
            if isinstance(payload, bytes):
                atts.append((name, payload))
        body_html = m.htmlBody.decode("utf-8", "replace") if isinstance(m.htmlBody, bytes) else (m.htmlBody or "")
        info = {"Van": m.sender or "", "Aan": m.to or "", "Cc": m.cc or "", "Datum": str(m.date or ""),
                "Onderwerp": m.subject or ""}
        return info, m.body or "", body_html, atts, None
    if ext == "tnef" or data[:4] == b"\x78\x9f\x3e\x22":
        try:
            from tnefparse import TNEF
        except ImportError as e:
            raise ConversionError("winmail.dat lezen vraagt tnefparse.") from e
        t = TNEF(data)
        atts = [(a.long_filename() or a.name or "bijlage", a.data) for a in t.attachments]
        body = t.body.decode("utf-8", "replace") if isinstance(t.body, bytes) else (t.body or "")
        htmlb = t.htmlbody.decode("utf-8", "replace") if isinstance(getattr(t, "htmlbody", None), bytes) else ""
        return {"Onderwerp": src.stem}, body, htmlb, atts, None
    if ext == "p7m":
        data = _p7m_content(data)
    msg = email.message_from_bytes(data, policy=policy.default)
    info = {k: str(msg.get(k, "")) for k in ("From", "To", "Cc", "Date", "Subject")}
    info = dict(zip(("Van", "Aan", "Cc", "Datum", "Onderwerp"), info.values()))
    body = msg.get_body(preferencelist=("plain",))
    body_html = msg.get_body(preferencelist=("html",))
    atts = []
    for part in msg.iter_attachments():
        payload = part.get_payload(decode=True) or b""
        atts.append((part.get_filename() or "bijlage", payload))
    return info, body.get_content() if body else "", body_html.get_content() if body_html else "", atts, msg


def _p7m_content(data: bytes) -> bytes:
    """S/MIME: ondertekende inhoud uitpakken. Versleutelde mail kan alleen met de privésleutel."""
    if b"application/pkcs7-mime" in data[:2000] or data[:30].startswith(b"MIME-Version"):
        msg = email.message_from_bytes(data, policy=policy.default)
        payload = msg.get_payload(decode=True)
        if payload:
            data = payload
    try:
        from asn1crypto import cms
        info = cms.ContentInfo.load(data)
        if info["content_type"].native == "enveloped_data":
            raise ConversionError("Deze mail is versleuteld; openen kan alleen met de privésleutel van de ontvanger.")
        content = info["content"]["encap_content_info"]["content"].native
        if content:
            return content
    except ConversionError:
        raise
    except Exception:  # noqa: BLE001
        pass
    raise ConversionError("De inhoud van dit S/MIME-bestand kon niet gelezen worden.")


def mail(src: Path, out_dir: Path, fmt: str) -> Path:
    ext = src.suffix.lower().lstrip(".")
    if ext == "mbox":
        import mailbox
        box = mailbox.mbox(str(src))
        if fmt == "zip":
            dst = out_dir / f"{src.stem}.zip"
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
                for i, m in enumerate(box, 1):
                    subj = re.sub(r"[^\w .-]", "_", str(m.get("Subject", "")))[:60] or "bericht"
                    z.writestr(f"{i:05d} {subj}.eml", m.as_bytes())
            return dst
        rows = [{"datum": m.get("Date", ""), "van": m.get("From", ""), "aan": m.get("To", ""),
                 "onderwerp": m.get("Subject", "")} for m in box]
        from .datafmt import write
        return write(rows, out_dir / f"{src.stem}.{fmt}", fmt, src.stem)
    info, body, body_html, atts, msg = _parse_mail(src)
    dst = out_dir / f"{src.stem}.{fmt}"
    if fmt == "zip":
        if not atts:
            raise ConversionError("Dit bericht heeft geen bijlagen.")
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            used = set()
            for name, payload in atts:
                name = re.sub(r"[\\/:*?\"<>|]", "_", name)
                while name in used:
                    name = "_" + name
                used.add(name)
                z.writestr(name, payload)
        return dst
    if fmt == "eml":
        if msg is not None:
            dst.write_bytes(msg.as_bytes())
            return dst
        from email.message import EmailMessage
        em = EmailMessage()
        for k_nl, k in (("Van", "From"), ("Aan", "To"), ("Cc", "Cc"), ("Onderwerp", "Subject")):
            if info.get(k_nl):
                em[k] = info[k_nl].replace("\n", " ")
        em.set_content(body or "")
        if body_html:
            em.add_alternative(body_html, subtype="html")
        for name, payload in atts:
            em.add_attachment(payload, maintype="application", subtype="octet-stream", filename=name)
        dst.write_bytes(em.as_bytes())
        return dst
    head = "\n".join(f"{k}: {v}" for k, v in info.items() if v)
    att_line = ("\nBijlagen: " + ", ".join(n for n, _ in atts)) if atts else ""
    if fmt == "txt":
        from .ebook import html_to_text
        dst.write_text(head + att_line + "\n\n" + (body or html_to_text(body_html)) + "\n", encoding="utf-8")
        return dst
    head_html = "<table>" + "".join(f"<tr><th align=left>{html.escape(k)}</th><td>{html.escape(v)}</td></tr>"
                                    for k, v in info.items() if v) + "</table>"
    if atts:
        head_html += "<p><b>Bijlagen:</b> " + html.escape(", ".join(n for n, _ in atts)) + "</p>"
    content = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "", body_html) if body_html else \
        f"<pre style='white-space:pre-wrap'>{html.escape(body)}</pre>"
    page = f"{head_html}<hr/>{content}"
    if fmt == "html":
        dst.write_text(f"<!doctype html><meta charset='utf-8'><title>{html.escape(info.get('Onderwerp', ''))}</title>"
                       f"{page}", encoding="utf-8")
        return dst
    from .pdftools import html_to_pdf
    return html_to_pdf(page, dst)


# --------------------------------------------------------------------------- contacten en agenda

def _unfold(text: str) -> list[str]:
    return re.sub(r"\r?\n[ \t]", "", text).splitlines()


def vcards(src: Path) -> list[dict]:
    from .textfmt import read_text
    cards, cur = [], None
    for line in _unfold(read_text(src)):
        if line.upper().startswith("BEGIN:VCARD"):
            cur = {}
        elif line.upper().startswith("END:VCARD") and cur is not None:
            cards.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            name = key.split(";")[0].upper()
            label = {"FN": "naam", "N": "naam (delen)", "TEL": "telefoon", "EMAIL": "e-mail", "ORG": "organisatie",
                     "TITLE": "functie", "ADR": "adres", "BDAY": "verjaardag", "URL": "website", "NOTE": "notitie"}.get(name)
            if label:
                val = val.replace("\\,", ",").replace("\\n", " ").replace(";", " ").strip()
                cur[label] = (cur[label] + "; " + val) if label in cur else val
    if not cards:
        raise ConversionError("Geen contacten gevonden.")
    return cards


def events(src: Path) -> list[dict]:
    from .textfmt import read_text
    evs, cur = [], None
    for line in _unfold(read_text(src)):
        u = line.upper()
        if u.startswith("BEGIN:VEVENT") or u.startswith("BEGIN:VTODO"):
            cur = {}
        elif (u.startswith("END:VEVENT") or u.startswith("END:VTODO")) and cur is not None:
            evs.append(cur)
            cur = None
        elif cur is not None and ":" in line:
            key, val = line.split(":", 1)
            name = key.split(";")[0].upper()
            label = {"SUMMARY": "titel", "DTSTART": "begin", "DTEND": "einde", "LOCATION": "locatie",
                     "DESCRIPTION": "omschrijving", "RRULE": "herhaling", "ORGANIZER": "organisator"}.get(name)
            if label:
                if name in ("DTSTART", "DTEND"):
                    m = re.match(r"(\d{4})(\d\d)(\d\d)(?:T(\d\d)(\d\d))?", val)
                    if m:
                        val = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" + (f" {m.group(4)}:{m.group(5)}" if m.group(4)
                                                                            else "")
                cur[label] = val.replace("\\n", " ").replace("\\,", ",")
    if not evs:
        raise ConversionError("Geen afspraken gevonden.")
    return evs


# --------------------------------------------------------------------------- GPS

def read_track(src: Path) -> dict:
    """{'naam', 'punten': [(lat, lon, hoogte, tijd)], 'waypoints': [(lat, lon, naam)]}"""
    ext = src.suffix.lower().lstrip(".")
    pts, wps, name = [], [], src.stem
    if ext == "fit":
        try:
            import fitdecode
        except ImportError as e:
            raise ConversionError("Garmin .fit lezen vraagt fitdecode.") from e
        with fitdecode.FitReader(str(src)) as fr:
            for frame in fr:
                if isinstance(frame, fitdecode.FitDataMessage) and frame.name == "record":
                    def g(k):
                        return frame.get_value(k) if frame.has_field(k) else None
                    lat, lon = g("position_lat"), g("position_long")
                    if lat is not None and lon is not None:
                        k = 180 / 2 ** 31
                        alt = g("enhanced_altitude") or g("altitude")
                        t = g("timestamp")
                        pts.append((lat * k, lon * k, alt, t.isoformat() if t else None))
    elif ext == "igc":
        from .textfmt import read_text
        for line in read_text(src).splitlines():
            m = re.match(r"B(\d{6})(\d{2})(\d{5})([NS])(\d{3})(\d{5})([EW])A(\d{5})(\d{5})", line)
            if m:
                lat = int(m.group(2)) + int(m.group(3)) / 60000
                lon = int(m.group(5)) + int(m.group(6)) / 60000
                lat *= -1 if m.group(4) == "S" else 1
                lon *= -1 if m.group(7) == "W" else 1
                t = m.group(1)
                pts.append((lat, lon, float(m.group(9)), f"{t[:2]}:{t[2:4]}:{t[4:]}"))
    elif ext in ("geojson", "json"):
        data = json.loads(src.read_text(encoding="utf-8"))
        feats = data.get("features", [data]) if isinstance(data, dict) else []
        for f in feats:
            geom = f.get("geometry") or {}
            props = f.get("properties") or {}
            coords = geom.get("coordinates")
            if geom.get("type") == "Point":
                wps.append((coords[1], coords[0], props.get("name", "")))
            elif geom.get("type") in ("LineString", "MultiPoint"):
                pts += [(c[1], c[0], c[2] if len(c) > 2 else None, None) for c in coords]
            elif geom.get("type") == "MultiLineString":
                for line in coords:
                    pts += [(c[1], c[0], c[2] if len(c) > 2 else None, None) for c in line]
    else:
        raw = src.read_bytes()
        if ext == "kmz":
            with zipfile.ZipFile(src) as z:
                raw = z.read(next(n for n in z.namelist() if n.lower().endswith(".kml")))
        root = ET.fromstring(raw)
        for el in root.iter():
            tag = el.tag.split("}")[-1]
            if tag in ("trkpt", "rtept"):
                ele = next((c.text for c in el if c.tag.endswith("ele")), None)
                t = next((c.text for c in el if c.tag.endswith("time")), None)
                pts.append((float(el.get("lat")), float(el.get("lon")), float(ele) if ele else None, t))
            elif tag == "wpt" or (tag == "waypoint" and ext == "loc"):
                nm = next((c.text for c in el if c.tag.split("}")[-1] in ("name",)), "") or ""
                coord = el if el.get("lat") else next((c for c in el if c.tag.endswith("coord")), el)
                if coord.get("lat"):
                    wps.append((float(coord.get("lat")), float(coord.get("lon")), nm))
            elif tag == "Trackpoint":
                lat = next((c.text for c in el.iter() if c.tag.endswith("LatitudeDegrees")), None)
                lon = next((c.text for c in el.iter() if c.tag.endswith("LongitudeDegrees")), None)
                ele = next((c.text for c in el.iter() if c.tag.endswith("AltitudeMeters")), None)
                t = next((c.text for c in el if c.tag.endswith("Time")), None)
                if lat and lon:
                    pts.append((float(lat), float(lon), float(ele) if ele else None, t))
            elif tag == "Placemark":
                nm = next((c.text for c in el if c.tag.endswith("name")), "") or ""
                for c in el.iter():
                    ct = c.tag.split("}")[-1]
                    if ct == "coordinates" and c.text:
                        coords = [tuple(float(x) for x in p.split(",")) for p in c.text.split()]
                        parent_is_point = any(x.tag.endswith("Point") for x in el.iter())
                        if parent_is_point and len(coords) == 1:
                            wps.append((coords[0][1], coords[0][0], nm))
                        else:
                            pts += [(c2[1], c2[0], c2[2] if len(c2) > 2 else None, None) for c2 in coords]
            elif tag in ("name",) and name == src.stem and el.text:
                name = el.text
    if not pts and not wps:
        raise ConversionError("Geen route of punten gevonden.")
    return {"naam": name, "punten": pts, "waypoints": wps}


def write_track(tr: dict, dst: Path, fmt: str) -> Path:
    e = html.escape
    pts, wps = tr["punten"], tr["waypoints"]
    if fmt == "gpx":
        w = "".join(f'<wpt lat="{a}" lon="{b}"><name>{e(n)}</name></wpt>' for a, b, n in wps)
        seg = "".join(f'<trkpt lat="{a}" lon="{b}">' + (f"<ele>{h}</ele>" if h is not None else "") +
                      (f"<time>{t}</time>" if t else "") + "</trkpt>" for a, b, h, t in pts)
        dst.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Anything Converter" '
                       f'xmlns="http://www.topografix.com/GPX/1/1">{w}<trk><name>{e(tr["naam"])}</name><trkseg>{seg}'
                       "</trkseg></trk></gpx>\n", encoding="utf-8")
    elif fmt in ("kml", "kmz"):
        marks = "".join(f"<Placemark><name>{e(n)}</name><Point><coordinates>{b},{a}</coordinates></Point></Placemark>"
                        for a, b, n in wps)
        if pts:
            coords = " ".join(f"{b},{a}" + (f",{h}" if h is not None else "") for a, b, h, _ in pts)
            marks += (f"<Placemark><name>{e(tr['naam'])}</name><LineString><tessellate>1</tessellate>"
                      f"<coordinates>{coords}</coordinates></LineString></Placemark>")
        kml = ('<?xml version="1.0" encoding="UTF-8"?>\n<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'
               f"<name>{e(tr['naam'])}</name>{marks}</Document></kml>\n")
        if fmt == "kmz":
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
                z.writestr("doc.kml", kml)
        else:
            dst.write_text(kml, encoding="utf-8")
    elif fmt == "geojson":
        feats = [{"type": "Feature", "properties": {"name": n}, "geometry": {"type": "Point", "coordinates": [b, a]}}
                 for a, b, n in wps]
        if pts:
            feats.append({"type": "Feature", "properties": {"name": tr["naam"]},
                          "geometry": {"type": "LineString", "coordinates": [[b, a] + ([h] if h is not None else [])
                                                                             for a, b, h, _ in pts]}})
        dst.write_text(json.dumps({"type": "FeatureCollection", "features": feats}, indent=1), encoding="utf-8")
    elif fmt == "csv":
        with open(dst, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["soort", "breedtegraad", "lengtegraad", "hoogte", "tijd", "naam"])
            for a, b, n in wps:
                w.writerow(["punt", a, b, "", "", n])
            for a, b, h, t in pts:
                w.writerow(["route", a, b, h if h is not None else "", t or "", ""])
    elif fmt == "tcx":
        tps = "".join(f"<Trackpoint>{f'<Time>{t}</Time>' if t else ''}<Position><LatitudeDegrees>{a}</LatitudeDegrees>"
                      f"<LongitudeDegrees>{b}</LongitudeDegrees></Position>"
                      f"{f'<AltitudeMeters>{h}</AltitudeMeters>' if h is not None else ''}</Trackpoint>"
                      for a, b, h, t in pts)
        dst.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<TrainingCenterDatabase xmlns="http://www.garmin.com/'
                       'xmlschemas/TrainingCenterDatabase/v2"><Courses><Course><Name>' + e(tr["naam"][:15]) +
                       f"</Name><Track>{tps}</Track></Course></Courses></TrainingCenterDatabase>\n", encoding="utf-8")
    else:
        raise ConversionError(f"Route naar .{fmt} wordt niet ondersteund.")
    return dst


# --------------------------------------------------------------------------- 3D en CAD

def model3d(src: Path, out_dir: Path, fmt: str) -> Path:
    try:
        import trimesh
    except ImportError as e:
        raise ConversionError("3D-modellen omzetten vraagt trimesh.") from e
    ext = src.suffix.lower().lstrip(".")
    try:
        mesh = trimesh.load(str(src), file_type="stl" if ext == "stl" else None, force="mesh" if fmt in (
            "stl", "off") else None)
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"Dit 3D-model kan niet gelezen worden: {e}") from e
    dst = out_dir / f"{src.stem}{'_bewerkt' if fmt == ext else ''}.{fmt}"
    try:
        mesh.export(str(dst), file_type=fmt)
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"Opslaan als .{fmt} lukte niet: {e}") from e
    return dst


def cad(src: Path, out_dir: Path, fmt: str) -> Path:
    try:
        import ezdxf
        from ezdxf.addons.drawing import Frontend, RenderContext, layout
        from ezdxf.addons.drawing import svg as svg_backend
    except ImportError as e:
        raise ConversionError("DXF tekenen vraagt ezdxf.") from e
    try:
        doc = ezdxf.readfile(str(src))
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"Deze DXF-tekening kan niet gelezen worden: {e}") from e
    msp = doc.modelspace()
    backend = svg_backend.SVGBackend()
    Frontend(RenderContext(doc), backend).draw_layout(msp)
    page = layout.Page(0, 0, layout.Units.mm, margins=layout.Margins.all(10))
    svg_text = backend.get_string(page)
    dst = out_dir / f"{src.stem}.{fmt}"
    if fmt == "svg":
        dst.write_text(svg_text, encoding="utf-8")
        return dst
    tmp = out_dir / f"_{src.stem}.svg"
    tmp.write_text(svg_text, encoding="utf-8")
    out = vector(tmp, out_dir, fmt)
    tmp.unlink(missing_ok=True)
    final = out_dir / f"{src.stem}.{fmt}"
    out.replace(final)
    return final


# --------------------------------------------------------------------------- vector

def vector(src: Path, out_dir: Path, fmt: str) -> Path:
    import fitz
    ext = src.suffix.lower().lstrip(".")
    dst = out_dir / f"{src.stem}{'_bewerkt' if fmt == ext else ''}.{fmt}"
    work = src
    if ext == "svgz":
        import gzip
        work = out_dir / f"_{src.stem}.svg"
        work.write_bytes(gzip.decompress(src.read_bytes()))
        if fmt == "svg":
            work.replace(dst)
            return dst
    if ext in ("eps", "ps"):
        from .util import run
        gs = "gswin64c" if have("gswin64c") else "gs"
        if not have(gs):
            raise ConversionError("PostScript/EPS omzetten vraagt Ghostscript (gratis, ghostscript.com).")
        work = out_dir / f"_{src.stem}.pdf"
        run([gs, "-q", "-dNOPAUSE", "-dBATCH", "-dSAFER", "-dEPSCrop", "-sDEVICE=pdfwrite", f"-sOutputFile={work}",
             str(src)], timeout=600)
    if ext in ("gv", "dot-graph", "dot"):
        from .util import run
        if not have("dot"):
            raise ConversionError("Graphviz-diagrammen tekenen vraagt Graphviz (gratis, graphviz.org).")
        run(["dot", f"-T{'svg' if fmt == 'svg' else 'pdf'}", str(src), "-o", str(dst if fmt in ("svg", "pdf") else
                                                                              out_dir / f"_{src.stem}.pdf")], timeout=300)
        if fmt in ("svg", "pdf"):
            return dst
        work = out_dir / f"_{src.stem}.pdf"
    try:
        doc = fitz.open(str(work)) if work.suffix.lower() in (".pdf", ".ai", ".xps", ".oxps") else \
            fitz.open("svg", work.read_bytes())
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"Dit bestand kan niet getekend worden: {e}") from e
    if fmt == "pdf":
        if doc.is_pdf:
            doc.save(str(dst), garbage=3, deflate=True)
        else:
            fitz.open("pdf", doc.convert_to_pdf()).save(str(dst), garbage=3, deflate=True)
        return dst
    if fmt == "svg":
        dst.write_text(doc[0].get_svg_image(text_as_path=True), encoding="utf-8")
        return dst
    page = doc[0]
    zoom = max(1.0, min(4.0, 2000 / max(page.rect.width, page.rect.height, 1)))
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=fmt in ("png", "webp"))
    if fmt in ("png",):
        pix.save(str(dst))
    else:
        from PIL import Image
        im = Image.frombytes("RGBA" if pix.alpha else "RGB", (pix.width, pix.height), pix.samples)
        if fmt == "jpg":
            bg = Image.new("RGB", im.size, "white")
            bg.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
            im = bg
        im.save(dst, {"jpg": "JPEG", "webp": "WEBP"}[fmt], quality=90)
    return dst


# --------------------------------------------------------------------------- certificaten

def _load_certs(data: bytes):
    from cryptography import x509
    from cryptography.hazmat.primitives.serialization import pkcs7
    items = []
    if b"-----BEGIN" in data:
        for m in re.finditer(rb"-----BEGIN ([A-Z0-9 ]+)-----(.*?)-----END \1-----", data, re.S):
            kind = m.group(1).decode()
            blob = m.group(0)
            if kind == "CERTIFICATE":
                items.append(("cert", x509.load_pem_x509_certificate(blob)))
            elif kind == "CERTIFICATE REQUEST":
                items.append(("csr", x509.load_pem_x509_csr(blob)))
            elif kind == "X509 CRL":
                items.append(("crl", x509.load_pem_x509_crl(blob)))
            elif kind == "PKCS7":
                items += [("cert", c) for c in pkcs7.load_pem_pkcs7_certificates(blob)]
            elif "PRIVATE KEY" in kind or "PUBLIC KEY" in kind:
                items.append(("key", kind))
        return items
    for loader, kind in ((x509.load_der_x509_certificate, "cert"), (x509.load_der_x509_csr, "csr"),
                         (x509.load_der_x509_crl, "crl")):
        try:
            return [(kind, loader(data))]
        except Exception:  # noqa: BLE001
            pass
    try:
        return [("cert", c) for c in pkcs7.load_der_pkcs7_certificates(data)]
    except Exception:  # noqa: BLE001
        pass
    raise ConversionError("Geen certificaat, aanvraag of intrekkingslijst herkend.")


def _key_convert(data: bytes, dst: Path, fmt: str) -> Path:
    """Sleutel PEM <-> DER (onversleuteld). Versleutelde sleutels blijven dicht: daar is het wachtwoord voor nodig."""
    from cryptography.hazmat.primitives import serialization as ser
    loaders = ((ser.load_pem_private_key, True), (ser.load_pem_public_key, False)) if data.startswith(b"-----") else \
        ((ser.load_der_private_key, True), (ser.load_der_public_key, False))
    for loader, private in loaders:
        try:
            key = loader(data, None) if private else loader(data)
        except TypeError as e:
            raise ConversionError("Deze sleutel is met een wachtwoord beveiligd; die blijft dicht.") from e
        except Exception:  # noqa: BLE001
            continue
        enc = ser.Encoding.PEM if fmt == "pem" else ser.Encoding.DER
        if private:
            dst.write_bytes(key.private_bytes(enc, ser.PrivateFormat.PKCS8, ser.NoEncryption()))
        else:
            dst.write_bytes(key.public_bytes(enc, ser.PublicFormat.SubjectPublicKeyInfo))
        return dst
    raise ConversionError("Geen certificaat of sleutel herkend.")


def cert(src: Path, out_dir: Path, fmt: str) -> Path:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.serialization import Encoding
    data = src.read_bytes()
    if data.startswith((b"ssh-", b"ecdsa-")):
        if fmt != "txt":
            raise ConversionError("Een SSH-sleutel kan alleen als tekstoverzicht.")
        parts = data.decode().split()
        import base64
        import hashlib
        fp = base64.b64encode(hashlib.sha256(base64.b64decode(parts[1])).digest()).decode().rstrip("=")
        dst = out_dir / f"{src.stem}.txt"
        dst.write_text(f"Publieke SSH-sleutel\nType: {parts[0]}\nVingerafdruk: SHA256:{fp}\n"
                       f"Opmerking: {' '.join(parts[2:])}\n", encoding="utf-8")
        return dst
    try:
        items = _load_certs(data)
    except ConversionError:
        items = []
    dst = out_dir / f"{src.stem}{'_bewerkt' if fmt == src.suffix.lower().lstrip('.') else ''}.{fmt}"
    if fmt in ("pem", "der"):
        objs = [o for k, o in items if k in ("cert", "csr", "crl")]
        if not objs:
            return _key_convert(data, dst, fmt)
        enc = Encoding.PEM if fmt == "pem" else Encoding.DER
        if fmt == "der" and len(objs) > 1:
            objs = objs[:1]
        dst.write_bytes(b"".join(o.public_bytes(enc) for o in objs))
        return dst
    if not items:
        raise ConversionError("Geen certificaat, aanvraag of intrekkingslijst herkend.")
    lines = []
    for kind, o in items:
        if kind == "cert":
            try:
                san = o.extensions.get_extension_for_class(__import__("cryptography").x509.SubjectAlternativeName)
                names = ", ".join(str(n.value) for n in san.value)
            except Exception:  # noqa: BLE001
                names = ""
            lines += ["CERTIFICAAT", f"  Voor:        {o.subject.rfc4514_string()}",
                      f"  Uitgegeven door: {o.issuer.rfc4514_string()}",
                      f"  Geldig van:  {o.not_valid_before_utc:%Y-%m-%d %H:%M} UTC",
                      f"  Geldig tot:  {o.not_valid_after_utc:%Y-%m-%d %H:%M} UTC",
                      f"  Serienummer: {o.serial_number:x}",
                      f"  SHA-256:     {o.fingerprint(hashes.SHA256()).hex(':')}"]
            if names:
                lines.append(f"  Namen:       {names}")
            lines.append("")
        elif kind == "csr":
            lines += ["CERTIFICAATAANVRAAG", f"  Voor: {o.subject.rfc4514_string()}", ""]
        elif kind == "crl":
            lines += ["INTREKKINGSLIJST", f"  Uitgever: {o.issuer.rfc4514_string()}",
                      f"  Ingetrokken certificaten: {len(list(o))}", ""]
        else:
            lines += [f"SLEUTEL ({o.lower()}) - inhoud wordt niet getoond", ""]
    dst.write_text("\n".join(lines), encoding="utf-8")
    return dst


# --------------------------------------------------------------------------- DICOM

def dicom(src: Path, out_dir: Path, fmt: str) -> Path:
    try:
        import numpy as np
        import pydicom
    except ImportError as e:
        raise ConversionError("Medische beelden (DICOM) lezen vraagt pydicom.") from e
    ds = pydicom.dcmread(str(src))
    dst = out_dir / f"{src.stem}.{fmt}"
    if fmt == "txt":
        keep = ("PatientID", "StudyDate", "Modality", "StudyDescription", "SeriesDescription", "Rows", "Columns",
                "Manufacturer", "BodyPartExamined", "SliceThickness", "PixelSpacing")
        dst.write_text("\n".join(f"{k}: {getattr(ds, k, '')}" for k in keep if hasattr(ds, k)) + "\n",
                       encoding="utf-8")
        return dst
    try:
        arr = ds.pixel_array.astype("float64")
    except Exception as e:  # noqa: BLE001
        raise ConversionError(f"Het beeld in dit DICOM-bestand kan niet gelezen worden (compressie?): {e}") from e
    if arr.ndim == 3 and arr.shape[-1] not in (3, 4):
        arr = arr[arr.shape[0] // 2]
    wc, ww = getattr(ds, "WindowCenter", None), getattr(ds, "WindowWidth", None)
    if wc is not None and ww is not None:
        wc = float(wc[0] if isinstance(wc, pydicom.multival.MultiValue) else wc)
        ww = float(ww[0] if isinstance(ww, pydicom.multival.MultiValue) else ww)
        lo, hi = wc - ww / 2, wc + ww / 2
    else:
        lo, hi = float(arr.min()), float(arr.max())
    img = np.clip((arr - lo) / max(hi - lo, 1e-6) * 255, 0, 255).astype("uint8")
    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
        img = 255 - img
    from PIL import Image
    Image.fromarray(img).save(dst, {"png": "PNG", "jpg": "JPEG", "tiff": "TIFF"}[fmt])
    return dst


# --------------------------------------------------------------------------- hoofdfunctie

def convert(fam: str, src: Path, out_dir: Path, fmt: str, opts: dict) -> Path:
    from .datafmt import write
    if fam == "font":
        return font(src, out_dir, fmt)
    if fam == "mail":
        return mail(src, out_dir, fmt)
    if fam == "contact":
        return write(vcards(src), out_dir / f"{src.stem}.{fmt}", fmt, src.stem)
    if fam == "calendar":
        return write(events(src), out_dir / f"{src.stem}.{fmt}", fmt, src.stem)
    if fam == "gps":
        ext = src.suffix.lower().lstrip(".")
        return write_track(read_track(src), out_dir / f"{src.stem}{'_bewerkt' if fmt == ext else ''}.{fmt}", fmt)
    if fam == "model3d":
        return model3d(src, out_dir, fmt)
    if fam == "cad":
        return cad(src, out_dir, fmt)
    if fam == "vector":
        return vector(src, out_dir, fmt)
    if fam == "cert":
        return cert(src, out_dir, fmt)
    if fam == "medical":
        return dicom(src, out_dir, fmt)
    raise ConversionError("Onbekende soort.")
