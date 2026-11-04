"""Torrents downloaden (magnet-link of .torrent-bestand) met libtorrent.

Alleen bedoeld voor legale inhoud: eigen bestanden, open-source software, Linux-ISO's,
werk met een vrije licentie (Creative Commons, publiek domein) of met toestemming.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Optional

from .util import ConversionError, ProgressFn, human_size

METADATA_TIMEOUT = 180  # seconden wachten op gegevens van een magnet-link
STALL_TIMEOUT = 600     # stoppen als er zo lang niets binnenkomt


def _lt():
    try:
        import libtorrent as lt
    except ImportError as exc:
        raise ConversionError("Torrents vereisen libtorrent: pip install libtorrent") from exc
    return lt


def _speed(bps: float) -> str:
    return human_size(int(bps)) + "/s"


def download(source: str | bytes, out_dir: Path, progress: Optional[ProgressFn] = None,
             cancelled: Callable[[], bool] = lambda: False, peers: Optional[list] = None) -> dict:
    """Download een torrent. `source` is een magnet-link (str) of de inhoud van een .torrent (bytes).

    Geeft {"root": Path, "files": [{"idx", "path", "size"}], "name": str} terug.
    `peers` (lijst van (host, poort)) is voor tests zonder internet.
    """
    lt = _lt()
    out_dir.mkdir(parents=True, exist_ok=True)
    settings = {
        "listen_interfaces": "0.0.0.0:6881,[::]:6881",
        "enable_dht": True, "enable_lsd": True, "enable_upnp": True, "enable_natpmp": True,
        "alert_mask": 0,
        "user_agent": "AnythingConverter/libtorrent",
    }
    ses = lt.session(settings)
    try:
        if isinstance(source, (bytes, bytearray)):
            try:
                ti = lt.torrent_info(lt.bdecode(bytes(source)))
            except Exception as exc:
                raise ConversionError("Dit is geen geldig .torrent-bestand.") from exc
            params = lt.add_torrent_params()
            params.ti = ti
        else:
            src = source.strip()
            if not src.lower().startswith("magnet:?"):
                raise ConversionError("Plak een magnet-link (begint met magnet:?) of kies een .torrent-bestand.")
            try:
                params = lt.parse_magnet_uri(src)
            except Exception as exc:
                raise ConversionError("Deze magnet-link is ongeldig.") from exc
        params.save_path = str(out_dir)
        h = ses.add_torrent(params)
        for host, port in peers or []:
            h.connect_peer((host, port))

        # 1) gegevens ophalen (alleen bij magnet-links nodig)
        start = time.time()
        while not h.status().has_metadata:
            if cancelled():
                raise ConversionError("Gestopt.")
            if time.time() - start > METADATA_TIMEOUT:
                raise ConversionError("Geen gegevens gevonden voor deze magnet-link (geen peers bereikbaar). "
                                      "Probeer het later opnieuw of gebruik een .torrent-bestand.")
            if progress:
                progress(0.01, f"Gegevens ophalen · {h.status().num_peers} peers")
            time.sleep(0.5)

        ti = h.torrent_file()
        fs = ti.files()
        name = ti.name()
        total = ti.total_size()

        # 2) downloaden
        last_bytes, last_change = 0, time.time()
        while True:
            st = h.status()
            if cancelled():
                raise ConversionError("Gestopt.")
            if st.is_finished or st.is_seeding or st.progress >= 1.0:
                break
            if st.total_done != last_bytes:
                last_bytes, last_change = st.total_done, time.time()
            elif time.time() - last_change > STALL_TIMEOUT:
                raise ConversionError(f"Al {STALL_TIMEOUT // 60} minuten komt er niets binnen "
                                      f"({human_size(st.total_done)} van {human_size(total)}). Te weinig peers.")
            if progress:
                progress(0.02 + 0.97 * st.progress,
                         f"Downloaden {human_size(st.total_done)} van {human_size(total)} · "
                         f"{_speed(st.download_rate)} · {st.num_peers} peers")
            time.sleep(0.5)

        # Alles netjes naar schijf schrijven voor we de sessie sluiten
        h.flush_cache() if hasattr(h, "flush_cache") else None
        pad = getattr(lt.file_storage, "flag_pad_file", 1)
        files = [{"idx": i, "path": fs.file_path(i), "size": fs.file_size(i)} for i in range(fs.num_files())
                 if not (fs.file_flags(i) & pad)]
        if progress:
            progress(0.99, "Klaar")
        return {"root": out_dir, "files": files, "name": name}
    finally:
        try:
            ses.pause()
        except Exception:
            pass
        # sessie in een aparte thread opruimen: kan even duren en mag de interface niet blokkeren
        threading.Thread(target=lambda s=ses: s.abort() if hasattr(s, "abort") else None, daemon=True).start()
