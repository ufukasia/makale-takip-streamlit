# -*- coding: utf-8 -*-
"""
Turso (SQLite uyumlu bulut veritabani) icin kucuk HTTP istemcisi.

Neden bu dosya var?
    Streamlit Cloud'un diski GECICIDIR. Makine uykuya dalip yeniden kurulunca
    repo sifirdan acilir ve submissions.db dosyasi ilk haline doner; ogrenci
    secimleri kaybolur. Kalici cozum veritabanini disariya tasimaktir.

Neden ekstra kutuphane yok?
    Turso'nun resmi "libsql-client" paketi 2024'ten beri guncellenmedi ve
    aiohttp'ye baglidir; Streamlit Cloud'un Python surumunde kurulumu sik sik
    patliyor. Turso ayni zamanda duz HTTP (Hrana v2 "pipeline") konusur, biz de
    sadece requests ile onu kullaniyoruz. Ek bagimlilik yok, kurulum riski yok.

Kullanim:
    db = Turso("libsql://db-adi-org.turso.io", "eyJhbGci...")
    db.execute("CREATE TABLE IF NOT EXISTS t (a TEXT)")
    db.execute("INSERT INTO t VALUES (?)", ("selam",))
    rows = db.execute("SELECT a FROM t")      # [("selam",)]
"""

import base64

import requests


class TursoError(RuntimeError):
    """Turso'ya baglanirken / sorgu calistirirken olusan hata."""


def normalize_url(url: str) -> str:
    """libsql://... , wss://... veya duz alan adini https://... yapar."""
    url = (url or "").strip().rstrip("/")
    if not url:
        return ""
    for prefix in ("libsql://", "wss://", "ws://", "http://"):
        if url.startswith(prefix):
            url = "https://" + url[len(prefix):]
            break
    if not url.startswith("https://"):
        url = "https://" + url
    return url


def _encode(value):
    """Python degerini Hrana arguman formatina cevirir."""
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "integer", "value": str(int(value))}
    if isinstance(value, int):
        return {"type": "integer", "value": str(value)}
    if isinstance(value, float):
        return {"type": "float", "value": value}
    if isinstance(value, (bytes, bytearray)):
        return {"type": "blob", "base64": base64.b64encode(bytes(value)).decode()}
    return {"type": "text", "value": str(value)}


def _decode(cell):
    """Hrana hucresini Python degerine cevirir (tam sayilar string gelir!)."""
    kind = cell.get("type")
    if kind == "null":
        return None
    if kind == "integer":
        return int(cell["value"])
    if kind == "float":
        return float(cell["value"])
    if kind == "blob":
        return base64.b64decode(cell.get("base64", ""))
    return cell.get("value")


class Turso:
    """Turso veritabanina HTTP uzerinden sorgu calistirir (her sorgu autocommit)."""

    def __init__(self, url: str, auth_token: str = "", timeout: int = 30):
        base = normalize_url(url)
        if not base:
            raise TursoError("Turso URL'si bos.")
        self.endpoint = base + "/v2/pipeline"
        self.timeout = timeout
        self._session = requests.Session()
        self._session.headers["Content-Type"] = "application/json"
        if auth_token:
            self._session.headers["Authorization"] = f"Bearer {auth_token.strip()}"

    # ── temel calistirma ──────────────────────────────────────────────
    def batch(self, statements):
        """[(sql, params), ...] listesini TEK HTTP isteginde sirayla calistirir.

        Her sorgu icin satir listesi dondurur: [[(sutun, ...), ...], ...]
        """
        payload = {"requests": [
            {"type": "execute",
             "stmt": {"sql": sql, "args": [_encode(p) for p in (params or ())]}}
            for sql, params in statements
        ] + [{"type": "close"}]}

        last_error = None
        for attempt in range(2):          # gecici ag hatasinda bir kez daha dene
            try:
                resp = self._session.post(self.endpoint, json=payload,
                                          timeout=self.timeout)
                break
            except requests.RequestException as exc:
                last_error = exc
        else:
            raise TursoError(
                "Turso sunucusuna ulasilamadi (internet/URL kontrol et): "
                f"{last_error}")

        if resp.status_code == 401:
            raise TursoError("Turso kimlik dogrulamasi reddedildi — "
                             "secrets icindeki auth_token yanlis veya suresi dolmus.")
        if resp.status_code != 200:
            raise TursoError(f"Turso HTTP {resp.status_code}: {resp.text[:300]}")

        try:
            body = resp.json()
        except ValueError:
            raise TursoError(f"Turso beklenmeyen yanit verdi: {resp.text[:300]}")

        results = []
        for item in body.get("results", []):
            if item.get("type") == "error":
                msg = (item.get("error") or {}).get("message", "bilinmeyen hata")
                raise TursoError(f"SQL hatasi: {msg}")
            response = item.get("response") or {}
            if response.get("type") == "execute":
                rows = (response.get("result") or {}).get("rows", [])
                results.append([tuple(_decode(c) for c in row) for row in rows])
        return results

    def execute(self, sql: str, params=()):
        """Tek sorgu calistirir, satirlari (tuple listesi) dondurur."""
        return self.batch([(sql, params)])[0]

    def ping(self):
        """Baglanti canli mi? Hata firlatmazsa evet."""
        self.execute("SELECT 1")
        return True
