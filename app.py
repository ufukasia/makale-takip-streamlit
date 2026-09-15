# -*- coding: utf-8 -*-
"""
Yüksek Lisans Yapay Zeka Dersi — Makale Konu Seçim & İlerleme Takip (Streamlit)

Çalıştırma:
    pip install -r requirements.txt
    streamlit run app.py

- Öğrenci: ilk seferde @ostimteknik.edu.tr e-postasına gelen 6 haneli kodla
  kayıt olur ve şifre belirler; sonraki girişlerde e-posta + şifre yeterlidir.
  Şifresini unutursa yine mail koduyla sıfırlayabilir.
- Danışman: yan menüden "Danışman Paneli"ni açar (panel şifresi aşağıda).
- Tüm kayıtlar bu klasördeki submissions.db (SQLite) dosyasında tutulur.
  Aynı sunucuda çalışan tek uygulama olduğu için herkes aynı veriyi görür.

E-posta gönderimi için .streamlit/secrets.toml dosyasına SMTP bilgilerini ekleyin
(örnek: .streamlit/secrets.toml.example). SMTP ayarlanmadan kod gönderilemez.
"""

import hashlib
import json
import re
import secrets as _secrets
import smtplib
import sqlite3
import ssl
import time
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

import streamlit as st

BASE = Path(__file__).parent
DB_PATH = BASE / "submissions.db"

# ── Danışman paneli şifresi (değiştirmek için bu satırı düzenle) ──
PANEL_SIFRESI = "orkestra2026"

# ── E-posta doğrulama ayarları ──
EMAIL_DOMAIN = "ostimteknik.edu.tr"
EMAIL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._%+-]*@" + EMAIL_DOMAIN.replace(".", r"\.") + r"$")
OTP_TTL = 10 * 60          # kod geçerlilik süresi (saniye)
OTP_MAX_ATTEMPTS = 5       # en fazla hatalı deneme
OTP_RESEND_COOLDOWN = 60   # yeni kod göndermeden önce bekleme (saniye)

DIFF_LABEL = {1: "Kolay", 2: "Orta", 3: "İleri"}

STEPS = [
    ("selected", "Konu seçildi", "Kaydın panele düştü"),
    ("dataset", "Veri seti indirildi", "Orkestra veri setini indirdi ve doğruladı"),
    ("baseline", "Rakip (baseline) çalıştı", "Otoriter yöntem koşuldu, referans sonuç kaydedildi"),
    ("stable", "Kod stabil çalışıyor", "Deney döngüsü hatasız, tekrarlanabilir çalışıyor"),
    ("beat", "Rakip geçildi", "Manipüle edilmiş yöntem baseline'ı geçti (çoklu seed)"),
]

STEP_KEYS = ["dataset", "baseline", "stable", "beat"]
STEP_FIELD = {"dataset": "dataset_downloaded", "baseline": "baseline_ran",
              "stable": "code_stable", "beat": "beat_baseline"}
# adım durumları: 0 beklemede · 1 tamamlandı · 2 gerçekleştirilemiyor (sorun)
STATUS_OPTS = ["Beklemede", "Tamamlandı ✓", "Gerçekleştirilemiyor ⚠"]

st.set_page_config(page_title="Makale Konuları — AI Dersi", page_icon="📚", layout="wide")

# ───────────────────────── Neon / cyberpunk tema ─────────────────────────
NEON_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

/* ── Zemin: derin uzay + neon ışıma + ince grid ── */
.stApp {
    background:
        radial-gradient(1100px 550px at 85% -10%, rgba(0,240,255,.09), transparent 60%),
        radial-gradient(900px 500px at -5% 110%, rgba(255,43,214,.08), transparent 60%),
        repeating-linear-gradient(0deg, transparent, transparent 39px, rgba(0,240,255,.03) 40px),
        repeating-linear-gradient(90deg, transparent, transparent 39px, rgba(0,240,255,.03) 40px),
        #07070f;
}
html, body, [class*="css"] { font-family: 'Rajdhani', sans-serif; }

h1, h2, h3, h4 { font-family: 'Orbitron', sans-serif !important; letter-spacing: .05em; }
h2, h3 { color: #9df3ff !important; text-shadow: 0 0 14px rgba(0,240,255,.45); }

/* ── Neon ana başlık ── */
.neon-title {
    font-family: 'Orbitron', sans-serif; font-weight: 900;
    font-size: clamp(30px, 5vw, 52px); letter-spacing: .08em; line-height: 1.1;
    background: linear-gradient(92deg, #00f0ff 15%, #7a5cff 55%, #ff2bd6 90%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
    filter: drop-shadow(0 0 18px rgba(0,240,255,.45));
    margin-bottom: 4px;
}
.neon-sub { color: #8b8bb0; letter-spacing: .14em; text-transform: uppercase;
            font-size: 13px; margin-bottom: 18px; }
.neon-rule { height: 2px; border: 0; margin: 10px 0 22px;
    background: linear-gradient(90deg, #00f0ff, #7a5cff 50%, #ff2bd6, transparent 95%);
    box-shadow: 0 0 12px rgba(0,240,255,.5); }

/* ── Konu kartları (expander) — neon kart ── */
[data-testid="stExpander"] {
    border: 1px solid rgba(0,240,255,.30) !important;
    border-radius: 14px !important;
    background: linear-gradient(160deg, rgba(16,16,34,.92), rgba(9,9,20,.92)) !important;
    box-shadow: 0 0 18px rgba(0,240,255,.10), inset 0 0 34px rgba(0,240,255,.04);
    transition: box-shadow .25s ease, border-color .25s ease, transform .25s ease;
}
[data-testid="stExpander"]:hover {
    border-color: rgba(0,240,255,.65) !important;
    box-shadow: 0 0 30px rgba(0,240,255,.28), inset 0 0 34px rgba(0,240,255,.06);
    transform: translateY(-1px);
}
[data-testid="stExpander"] summary p { font-weight: 600; letter-spacing: .03em; }

/* ── Butonlar: neon çerçeve ── */
.stButton button {
    background: rgba(0,240,255,.04) !important;
    border: 1px solid rgba(0,240,255,.55) !important;
    border-radius: 10px !important;
    color: #7ff7ff !important;
    font-family: 'Orbitron', sans-serif !important;
    font-size: 12px !important; letter-spacing: .06em;
    text-shadow: 0 0 8px rgba(0,240,255,.55);
    box-shadow: 0 0 12px rgba(0,240,255,.20), inset 0 0 10px rgba(0,240,255,.06);
    transition: all .2s ease;
}
.stButton button:hover {
    color: #ffffff !important;
    box-shadow: 0 0 26px rgba(0,240,255,.5), inset 0 0 14px rgba(0,240,255,.12);
    border-color: #00f0ff !important;
}
.stButton button[kind="primary"] {
    border-color: rgba(255,43,214,.6) !important;
    color: #ffb0ec !important;
    text-shadow: 0 0 8px rgba(255,43,214,.6);
    box-shadow: 0 0 12px rgba(255,43,214,.25), inset 0 0 10px rgba(255,43,214,.08);
}
.stButton button[kind="primary"]:hover {
    box-shadow: 0 0 26px rgba(255,43,214,.55), inset 0 0 14px rgba(255,43,214,.15);
    border-color: #ff2bd6 !important;
}
.stButton button:disabled { opacity: .35; box-shadow: none; }

/* ── Kenar çubuğu ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0b0b1c, #07070f);
    border-right: 1px solid rgba(0,240,255,.18);
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    color: #9df3ff !important; text-shadow: 0 0 12px rgba(0,240,255,.4);
}

/* ── Giriş kutuları ── */
.stTextInput input, .stSelectbox div[data-baseweb="select"] > div {
    background: rgba(10,10,24,.85) !important;
    border: 1px solid rgba(0,240,255,.3) !important;
    border-radius: 10px !important;
    color: #d7f9ff !important;
}
.stTextInput input:focus {
    border-color: #00f0ff !important;
    box-shadow: 0 0 14px rgba(0,240,255,.35) !important;
}

/* ── Metrik kartları (panel) ── */
[data-testid="stMetric"] {
    background: linear-gradient(160deg, rgba(16,16,34,.95), rgba(9,9,20,.95));
    border: 1px solid rgba(255,43,214,.35);
    border-radius: 14px; padding: 14px 16px;
    box-shadow: 0 0 16px rgba(255,43,214,.14), inset 0 0 24px rgba(255,43,214,.05);
}
[data-testid="stMetricValue"] { font-family: 'Orbitron', sans-serif !important;
    color: #00f0ff !important; text-shadow: 0 0 12px rgba(0,240,255,.6); }

/* ── Bilgi/uyarı kutuları ── */
[data-testid="stAlert"] { border-radius: 12px !important; }

/* ══════════ KABLOLAMA İLERLEME AKIŞI ══════════ */
.flow { display: flex; align-items: flex-start; margin: 18px 0 10px; }
.fnode { display: flex; flex-direction: column; align-items: center; gap: 7px; min-width: 84px; }
.fdot {
    width: 30px; height: 30px; border-radius: 50%;
    border: 2px solid #26264a; background: #0b0b18;
    display: flex; align-items: center; justify-content: center;
    font-family: 'Orbitron', sans-serif; font-size: 12px; color: #4a4a70;
    transition: all .4s ease;
}
.flbl { font-size: 11.5px; line-height: 1.25; color: #56567e; text-align: center;
        letter-spacing: .03em; max-width: 96px; font-weight: 600; }

/* dolan düğüm */
.fnode.done .fdot {
    border-color: #00f0ff; color: #032025;
    background: radial-gradient(circle at 35% 35%, #a5fbff, #00f0ff 55%, #007f8c);
    box-shadow: 0 0 14px #00f0ff, 0 0 34px rgba(0,240,255,.55);
}
.fnode.done .flbl { color: #7ff7ff; text-shadow: 0 0 9px rgba(0,240,255,.75); }

/* sıradaki adım: pulse */
.fnode.next .fdot {
    border-color: #ff2bd6; color: #ff2bd6; background: rgba(255,43,214,.08);
    animation: pulse 1.5s ease-in-out infinite;
}
.fnode.next .flbl { color: #ff9ae6; text-shadow: 0 0 8px rgba(255,43,214,.6); }
@keyframes pulse {
    0%, 100% { box-shadow: 0 0 8px rgba(255,43,214,.35); }
    50%      { box-shadow: 0 0 24px rgba(255,43,214,.95), 0 0 44px rgba(255,43,214,.4); }
}

/* sorun bildirilen adım: kırmızı pulse */
.fnode.blocked .fdot {
    border-color: #ff4438; color: #ff6a5a; background: rgba(255,68,56,.10);
    animation: pulse-red 1.1s ease-in-out infinite;
}
.fnode.blocked .flbl { color: #ff9a8a; text-shadow: 0 0 9px rgba(255,68,56,.7); }
.mdot.blocked {
    border-color: #ff4438; background: rgba(255,68,56,.18);
    animation: pulse-red 1.1s ease-in-out infinite;
}
@keyframes pulse-red {
    0%, 100% { box-shadow: 0 0 7px rgba(255,68,56,.35); }
    50%      { box-shadow: 0 0 22px rgba(255,68,56,.95), 0 0 40px rgba(255,68,56,.4); }
}

/* bağlantı hattı (kablo) */
.fwire {
    flex: 1; height: 5px; border-radius: 3px; margin: 13px 6px 0;
    background: #181830; position: relative; overflow: hidden;
    box-shadow: inset 0 0 6px rgba(0,0,0,.6);
}
/* dolan hat: gradyan + üzerinden akan enerji parlaması */
.fwire.on {
    background: linear-gradient(90deg, #00f0ff, #7a5cff 60%, #ff2bd6);
    box-shadow: 0 0 12px rgba(0,240,255,.55), 0 0 22px rgba(255,43,214,.25);
}
.fwire.on::after {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(90deg, transparent 20%, rgba(255,255,255,.95) 50%, transparent 80%);
    animation: flow 1.3s linear infinite;
}
@keyframes flow { 0% { transform: translateX(-100%); } 100% { transform: translateX(100%); } }

/* ══════════ ÖZELLİK CHIP'LERİ + GEREKSİNİMLER ══════════ */
.spec-row { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin: 10px 0 6px; }
.chip {
    font-family: 'Orbitron', sans-serif; font-size: 10.5px; font-weight: 700;
    letter-spacing: .09em; padding: 5px 13px; border-radius: 20px;
    border: 1px solid var(--c); color: var(--c);
    text-shadow: 0 0 8px var(--c); box-shadow: 0 0 10px var(--c), inset 0 0 8px rgba(255,255,255,.04);
    background: rgba(10,10,24,.6);
}

/* ── Gereksinimler: pre-attentive yanıp sönme ── */
.req-row { display: flex; flex-wrap: wrap; gap: 10px; margin: 4px 0 12px; }
.req-chip {
    font-family: 'Rajdhani', sans-serif; font-weight: 700; font-size: 13.5px;
    letter-spacing: .04em; padding: 6px 14px; border-radius: 8px;
    border: 1px dashed rgba(255,209,102,.75); color: #ffd166;
    background: rgba(255,209,102,.06);
    animation: reqblink 1.1s ease-in-out infinite;
}
.req-chip.sys {
    border-color: rgba(0,240,255,.6); color: #7ff7ff;
    background: rgba(0,240,255,.05); animation-duration: 1.7s;
}
@keyframes reqblink {
    0%, 100% { opacity: .68; box-shadow: 0 0 3px transparent; }
    50%      { opacity: 1;   box-shadow: 0 0 16px currentColor; }
}

/* ── Orkestra uyumu: adım adım segment göstergesi ── */
.orch-meter {
    display: inline-flex; align-items: center; gap: 9px;
    font-family: 'Orbitron', sans-serif; font-size: 10.5px; font-weight: 700;
    letter-spacing: .09em; color: #8b8bb0;
}
.segs { display: inline-flex; gap: 4px; }
.segs i {
    width: 24px; height: 9px; border-radius: 3px;
    background: #181830; border: 1px solid #26264a; transform: skewX(-14deg);
}
.segs i.on {
    background: var(--oc); border-color: var(--oc);
    box-shadow: 0 0 10px var(--oc);
    animation: segpulse var(--spd) ease-in-out infinite;
}
.segs i.on:nth-child(2) { animation-delay: calc(var(--spd) / 4); }
.segs i.on:nth-child(3) { animation-delay: calc(var(--spd) / 2); }
@keyframes segpulse {
    0%, 100% { opacity: .5;  box-shadow: 0 0 5px var(--oc); }
    50%      { opacity: 1;   box-shadow: 0 0 20px var(--oc); }
}
.orch-lbl { color: var(--oc); text-shadow: 0 0 10px var(--oc); }

/* ══════════ PANEL MİNİ KABLO AKIŞI ══════════ */
.mflow { display: flex; align-items: center; padding-top: 7px; }
.mdot {
    width: 13px; height: 13px; border-radius: 50%; flex: none;
    border: 2px solid #26264a; background: #0b0b18;
}
.mdot.done {
    border-color: #00f0ff;
    background: radial-gradient(circle at 35% 35%, #a5fbff, #00f0ff 55%, #007f8c);
    box-shadow: 0 0 8px #00f0ff, 0 0 16px rgba(0,240,255,.5);
}
.mdot.next { border-color: #ff2bd6; animation: pulse 1.5s ease-in-out infinite; }
.mwire {
    flex: 1; min-width: 8px; height: 3px; border-radius: 2px; margin: 0 3px;
    background: #181830; position: relative; overflow: hidden;
}
.mwire.on {
    background: linear-gradient(90deg, #00f0ff, #7a5cff 60%, #ff2bd6);
    box-shadow: 0 0 8px rgba(0,240,255,.5);
}
.mwire.on::after {
    content: ''; position: absolute; inset: 0;
    background: linear-gradient(90deg, transparent 20%, rgba(255,255,255,.9) 50%, transparent 80%);
    animation: flow 1.3s linear infinite;
}
.mlegend { font-size: 11.5px; color: #56567e; letter-spacing: .05em; margin-top: 2px; }
</style>
"""

st.markdown(NEON_CSS, unsafe_allow_html=True)


def render_progress_flow(rec, fb=None):
    """5 aşamalı neon kablolama ilerleme akışını çizer (sorunlu adımlar kırmızı)."""
    fb = fb or {}
    done = [True, bool(rec["dataset_downloaded"]), bool(rec["baseline_ran"]),
            bool(rec["code_stable"]), bool(rec["beat_baseline"])]
    blocked = [False] + [fb.get(k, {}).get("status") == 2 for k in STEP_KEYS]
    next_idx = next((i for i in range(len(done))
                     if not done[i] and not blocked[i]), None)
    parts = ['<div class="flow">']
    for i, ((key, label, _desc), d) in enumerate(zip(STEPS, done)):
        if d:
            state, mark = "done", "✓"
        elif blocked[i]:
            state, mark = "blocked", "✗"
        elif i == next_idx:
            state, mark = "next", str(i + 1)
        else:
            state, mark = "", str(i + 1)
        parts.append(
            f'<div class="fnode {state}">'
            f'<div class="fdot">{mark}</div>'
            f'<div class="flbl">{label}</div></div>'
        )
        if i < len(STEPS) - 1:
            parts.append(f'<div class="fwire {"on" if done[i + 1] else ""}"></div>')
    parts.append("</div>")
    st.markdown("".join(parts), unsafe_allow_html=True)


ORCH_LEVEL = {"Orta": 1, "Yüksek": 2, "Çok yüksek": 3}
# seviye → (renk, animasyon hızı): yüksek uyum = hızlı & hareketli, düşük uyum = yavaş
ORCH_STYLE = {1: ("#00f0ff", "2.8s"), 2: ("#a06bff", "1.4s"), 3: ("#ff2bd6", "0.55s")}
DIFF_STYLE = {1: "#00f0ff", 2: "#ffd166", 3: "#ff2bd6"}


def render_specs(topic):
    """Zorluk/süre chip'leri, orkestra uyumu segmentleri ve yanıp sönen gereksinimler."""
    lvl = ORCH_LEVEL.get(topic["orchFit"], 2)
    oc, spd = ORCH_STYLE[lvl]
    segs = "".join(f'<i class="{"on" if i < lvl else ""}"></i>' for i in range(3))
    diff = DIFF_LABEL[topic["difficulty"]]
    dc = DIFF_STYLE[topic["difficulty"]]
    st.markdown(
        f'<div class="spec-row">'
        f'<span class="chip" style="--c:{dc}">◆ ZORLUK: {diff.upper()}</span>'
        f'<span class="chip" style="--c:#7ff7ff">⏱ {topic["duration"].upper()}</span>'
        f'<span class="orch-meter" style="--oc:{oc}; --spd:{spd}">'
        f'ORKESTRA UYUMU <span class="segs">{segs}</span>'
        f'<span class="orch-lbl">{topic["orchFit"].upper()}</span></span>'
        f'</div>'
        f'<div class="req-row">'
        f'<span class="req-chip">🖥 GPU: {topic["gpu"]}</span>'
        f'<span class="req-chip sys">⬢ {topic["system"]}</span>'
        f'</div>',
        unsafe_allow_html=True,
    )


def mini_flow_html(rec, fb=None) -> str:
    """Panel satırı için 5 düğümlü mini neon kablo akışı (HTML döner)."""
    fb = fb or {}
    done = [True, bool(rec["dataset_downloaded"]), bool(rec["baseline_ran"]),
            bool(rec["code_stable"]), bool(rec["beat_baseline"])]
    blocked = [False] + [fb.get(k, {}).get("status") == 2 for k in STEP_KEYS]
    next_idx = next((i for i in range(len(done))
                     if not done[i] and not blocked[i]), None)
    parts = ['<div class="mflow">']
    for i, d in enumerate(done):
        if d:
            state = "done"
        elif blocked[i]:
            state = "blocked"
        elif i == next_idx:
            state = "next"
        else:
            state = ""
        parts.append(f'<span class="mdot {state}"></span>')
        if i < len(done) - 1:
            parts.append(f'<span class="mwire {"on" if done[i + 1] else ""}"></span>')
    parts.append("</div>")
    return "".join(parts)


# ───────────────────────── E-posta doğrulama ─────────────────────────
def _smtp_cfg():
    """SMTP ayarlarını st.secrets içinden okur; yoksa None döner."""
    try:
        cfg = dict(st.secrets["smtp"])
    except Exception:
        return None
    return cfg if cfg.get("host") else None


def send_otp_email(to_addr: str, code: str):
    """Doğrulama kodunu e-posta ile gönderir. (başarılı_mı, hata_mesajı) döner."""
    cfg = _smtp_cfg()
    if not cfg:
        return False, ("E-posta sunucusu ayarlanmamış. Danışmanının "
                       ".streamlit/secrets.toml içine [smtp] bilgilerini eklemesi gerekir.")
    msg = EmailMessage()
    msg["Subject"] = "AI Dersi - Dogrulama Kodun"
    msg["From"] = cfg.get("sender") or cfg.get("user", "")
    msg["To"] = to_addr
    msg.set_content(
        f"Merhaba,\n\n"
        f"Makale konu secim sistemi icin dogrulama kodun: {code}\n\n"
        f"Kod {OTP_TTL // 60} dakika gecerlidir. Bu istegi sen yapmediysan "
        f"bu mesaji yok sayabilirsin.\n\n"
        f"Yapay Zeka Dersi - Konu Secim Sistemi"
    )
    try:
        port = int(cfg.get("port") or 465)
        if port == 465:
            with smtplib.SMTP_SSL(cfg["host"], port, timeout=15,
                                  context=ssl.create_default_context()) as srv:
                if cfg.get("user"):
                    srv.login(cfg["user"], cfg.get("password", ""))
                srv.send_message(msg)
        else:
            with smtplib.SMTP(cfg["host"], port, timeout=15) as srv:
                srv.starttls(context=ssl.create_default_context())
                if cfg.get("user"):
                    srv.login(cfg["user"], cfg.get("password", ""))
                srv.send_message(msg)
        return True, ""
    except Exception as e:
        return False, f"E-posta gonderilemedi: {e}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode()).hexdigest()


def request_otp(name: str, email: str, purpose: str):
    """Yeni kod uretip gonderir; basariliysa bekleyen dogrulamayı kaydeder."""
    code = f"{_secrets.randbelow(1_000_000):06d}"
    ok, err = send_otp_email(email, code)
    if not ok:
        return False, err
    st.session_state["pending_otp"] = {
        "code_hash": _hash_code(code),
        "email": email,
        "name": name,
        "purpose": purpose,   # "register" | "reset"
        "expires": time.time() + OTP_TTL,
        "attempts": 0,
        "last_sent": time.time(),
    }
    return True, ""


# ───────────────────────── Veri katmanı ─────────────────────────
@st.cache_data
def load_topics():
    with open(BASE / "topics.json", encoding="utf-8") as f:
        return json.load(f)


def conn():
    c = sqlite3.connect(DB_PATH)
    c.execute(
        """CREATE TABLE IF NOT EXISTS submissions (
            student_no   TEXT PRIMARY KEY,
            student_name TEXT NOT NULL,
            topic_id     TEXT NOT NULL,
            topic_code   TEXT NOT NULL,
            topic_title  TEXT NOT NULL,
            dataset_downloaded INTEGER NOT NULL DEFAULT 0,
            baseline_ran       INTEGER NOT NULL DEFAULT 0,
            code_stable        INTEGER NOT NULL DEFAULT 0,
            beat_baseline      INTEGER NOT NULL DEFAULT 0,
            updated_at   TEXT NOT NULL
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS step_feedback (
            student_no    TEXT NOT NULL,
            step          TEXT NOT NULL,
            status        INTEGER NOT NULL DEFAULT 0,
            student_note  TEXT NOT NULL DEFAULT '',
            advisor_reply TEXT NOT NULL DEFAULT '',
            updated_at    TEXT NOT NULL,
            PRIMARY KEY (student_no, step)
        )"""
    )
    c.execute(
        """CREATE TABLE IF NOT EXISTS accounts (
            email      TEXT PRIMARY KEY,
            name       TEXT NOT NULL,
            salt       TEXT NOT NULL,
            pw_hash    TEXT NOT NULL,
            created_at TEXT NOT NULL
        )"""
    )
    return c


def db_get(student_no: str):
    c = conn()
    row = c.execute(
        "SELECT student_no, student_name, topic_id, topic_code, topic_title, "
        "dataset_downloaded, baseline_ran, code_stable, beat_baseline, updated_at "
        "FROM submissions WHERE student_no = ?",
        (student_no,),
    ).fetchone()
    c.close()
    if not row:
        return None
    keys = ["student_no", "student_name", "topic_id", "topic_code", "topic_title",
            "dataset_downloaded", "baseline_ran", "code_stable", "beat_baseline", "updated_at"]
    return dict(zip(keys, row))


def db_register(student_no, name, topic):
    """Konuyu öğrenciye kaydeder. Konu başkasındaysa False döner."""
    c = conn()
    owner = c.execute(
        "SELECT student_no FROM submissions WHERE topic_id = ?", (topic["id"],)
    ).fetchone()
    if owner and owner[0] != student_no:
        c.close()
        return False
    c.execute(
        """INSERT INTO submissions
           (student_no, student_name, topic_id, topic_code, topic_title,
            dataset_downloaded, baseline_ran, code_stable, beat_baseline, updated_at)
           VALUES (?,?,?,?,?,0,0,0,0,?)
           ON CONFLICT(student_no) DO UPDATE SET
             student_name=excluded.student_name,
             topic_id=excluded.topic_id, topic_code=excluded.topic_code,
             topic_title=excluded.topic_title,
             dataset_downloaded=0, baseline_ran=0, code_stable=0, beat_baseline=0,
             updated_at=excluded.updated_at""",
        (student_no, name, topic["id"], topic["code"], topic["title"],
         datetime.now().isoformat(timespec="seconds")),
    )
    c.execute("DELETE FROM step_feedback WHERE student_no = ?", (student_no,))
    c.commit()
    c.close()
    return True


def db_get_feedback(student_no: str):
    """Öğrencinin adım durumları: {step: {status, note, reply}}"""
    c = conn()
    rows = c.execute(
        "SELECT step, status, student_note, advisor_reply "
        "FROM step_feedback WHERE student_no = ?",
        (student_no,),
    ).fetchall()
    c.close()
    return {s: {"status": st_, "note": n, "reply": r} for s, st_, n, r in rows}


def db_set_step(student_no: str, step: str, status: int, note: str = ""):
    """Öğrenci bir adımın durumunu değiştirir; submissions'taki bayrağı da eşitler."""
    c = conn()
    now = datetime.now().isoformat(timespec="seconds")
    c.execute(
        """INSERT INTO step_feedback (student_no, step, status, student_note, updated_at)
           VALUES (?,?,?,?,?)
           ON CONFLICT(student_no, step) DO UPDATE SET
             status=excluded.status, student_note=excluded.student_note,
             advisor_reply='', updated_at=excluded.updated_at""",
        (student_no, step, status, note, now),
    )
    c.execute(
        f"UPDATE submissions SET {STEP_FIELD[step]} = ?, updated_at = ? WHERE student_no = ?",
        (1 if status == 1 else 0, now, student_no),
    )
    c.commit()
    c.close()


def db_reply(student_no: str, step: str, reply: str):
    """Danışmanın öğrencinin sorununa cevabı."""
    c = conn()
    c.execute(
        "UPDATE step_feedback SET advisor_reply = ?, updated_at = ? "
        "WHERE student_no = ? AND step = ?",
        (reply, datetime.now().isoformat(timespec="seconds"), student_no, step),
    )
    c.commit()
    c.close()


def db_all_feedback():
    c = conn()
    rows = c.execute(
        "SELECT student_no, step, status, student_note, advisor_reply, updated_at "
        "FROM step_feedback ORDER BY updated_at DESC"
    ).fetchall()
    c.close()
    keys = ["student_no", "step", "status", "note", "reply", "updated_at"]
    return [dict(zip(keys, r)) for r in rows]


def db_withdraw(student_no: str):
    c = conn()
    c.execute("DELETE FROM submissions WHERE student_no = ?", (student_no,))
    c.execute("DELETE FROM step_feedback WHERE student_no = ?", (student_no,))
    c.commit()
    c.close()


def db_all():
    c = conn()
    rows = c.execute(
        "SELECT student_no, student_name, topic_id, topic_code, topic_title, "
        "dataset_downloaded, baseline_ran, code_stable, beat_baseline, updated_at "
        "FROM submissions ORDER BY updated_at DESC"
    ).fetchall()
    c.close()
    keys = ["student_no", "student_name", "topic_id", "topic_code", "topic_title",
            "dataset_downloaded", "baseline_ran", "code_stable", "beat_baseline", "updated_at"]
    return [dict(zip(keys, r)) for r in rows]


def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(),
                               bytes.fromhex(salt), 100_000).hex()


def db_get_account(email: str):
    c = conn()
    row = c.execute(
        "SELECT email, name, salt, pw_hash FROM accounts WHERE email = ?", (email,)
    ).fetchone()
    c.close()
    if not row:
        return None
    return {"email": row[0], "name": row[1], "salt": row[2], "pw_hash": row[3]}


def db_create_account(email: str, name: str, password: str):
    salt = _secrets.token_hex(16)
    c = conn()
    c.execute(
        "INSERT INTO accounts (email, name, salt, pw_hash, created_at) VALUES (?,?,?,?,?)",
        (email, name, salt, _hash_password(password, salt),
         datetime.now().isoformat(timespec="seconds")),
    )
    c.commit()
    c.close()


def db_update_password(email: str, password: str):
    salt = _secrets.token_hex(16)
    c = conn()
    c.execute(
        "UPDATE accounts SET salt = ?, pw_hash = ? WHERE email = ?",
        (salt, _hash_password(password, salt), email),
    )
    c.commit()
    c.close()


def db_check_password(acc, password: str) -> bool:
    return _secrets.compare_digest(_hash_password(password, acc["salt"]), acc["pw_hash"])


def db_taken_topics():
    """Seçilmiş konular: topic_id -> {"student_no", "student_name"}"""
    c = conn()
    rows = c.execute("SELECT topic_id, student_no, student_name FROM submissions").fetchall()
    c.close()
    return {tid: {"student_no": sno, "student_name": sname} for tid, sno, sname in rows}


DATA = load_topics()
CATEGORIES = DATA["categories"]
BONUS = DATA["bonus"]
TOPIC_BY_ID = {t["id"]: (c, t) for c in CATEGORIES for t in c["topics"]}


# ───────────────────────── Öğrenci görünümü ─────────────────────────
def topic_card(cat, topic, my_record, taken):
    mine = my_record is not None and my_record["topic_id"] == topic["id"]
    owner = taken.get(topic["id"])
    taken_by_other = owner is not None and not mine
    header = f"**{topic['code']}** · {topic['title']}"
    if mine:
        header += f" — 👤 **{my_record['student_name']}**"
    elif owner:
        header += f" — 🔒 {owner['student_name']}"
    with st.expander(header, expanded=False):
        if topic.get("titleEn"):
            st.caption(f"EN başlık: {topic['titleEn']}")

        render_specs(topic)
        st.markdown(f"**Yayın hedefi:** {topic['publishTarget']}")

        st.divider()
        a, b = st.columns(2)
        with a:
            st.markdown("**Veri seti**")
            st.markdown(f"{topic['dataset']['name']} — {topic['dataset']['detail']}")
            st.markdown(f"[{topic['dataset']['url']}]({topic['dataset']['url']})")
            st.markdown("**Hedef ve metrik**")
            st.markdown(f"{topic['target']}  \nMetrik: `{topic['metric']}`")
        with b:
            st.markdown("**Otoriter yöntem (rakip)**")
            st.markdown(f"{topic['baseline']['name']} — {topic['baseline']['code']}")
            st.info(topic["baseline"]["result"])

        st.markdown("**Orkestra deney döngüsü**")
        for i, s in enumerate(topic["strategy"], 1):
            st.markdown(f"{i}. {s}")

        st.divider()
        # Seçim
        if mine:
            st.success("✓ Bu konu sende — **aksiyon planın sayfanın altında.**")
        else:
            if taken_by_other:
                st.error(f"🔒 Bu konuyu **{owner['student_name']}** seçti — artık alınamaz.")
            else:
                already = my_record is not None
                if st.button(
                    "Başka konu seçili (önce ondan vazgeç)" if already else "Bu konuyu seç",
                    key=f"pick_{topic['id']}",
                    disabled=already,
                ):
                    ident = st.session_state.get("identity")
                    if not ident:
                        st.error("Önce sol menüden okul e-postanla doğrulama yaparak giriş yap.")
                    elif not db_register(ident["email"], ident["name"], topic):
                        st.error("Bu konu az önce başkası tarafından seçildi.")
                    else:
                        st.rerun()


def render_action_plan(my_record):
    """Seçim sonrası aksiyon planı: kablo akışı + adım durumları + sorun/cevap."""
    _cat, topic = TOPIC_BY_ID.get(my_record["topic_id"], (None, None))
    st.markdown(
        '<div class="neon-sub">🎯 AKSİYON PLANI</div><hr class="neon-rule">',
        unsafe_allow_html=True,
    )
    st.markdown(f"### [{my_record['topic_code']}] {my_record['topic_title']}")
    if topic:
        render_specs(topic)
        st.markdown(f"**Hedef:** {topic['target']}  \n**Metrik:** `{topic['metric']}` · "
                    f"**Veri:** [{topic['dataset']['name']}]({topic['dataset']['url']})")

    fb = db_get_feedback(my_record["student_no"])
    render_progress_flow(my_record, fb)
    st.caption("Her adımın durumunu işaretle, hattın dolduğunu izle. Takıldığın adımı "
               "**“Gerçekleştirilemiyor”** olarak işaretle ve sorununu yaz — "
               "danışmanın panelden görüp cevaplar.")
    for key, label, desc in STEPS[1:]:
        entry = fb.get(key)
        cur = entry["status"] if entry else (1 if my_record[STEP_FIELD[key]] else 0)
        sid = f"{my_record['student_no']}_{key}"
        choice = st.radio(f"**{label}**", STATUS_OPTS, index=cur,
                          horizontal=True, help=desc, key=f"step_{sid}")
        new_status = STATUS_OPTS.index(choice)
        if new_status != cur:
            db_set_step(my_record["student_no"], key, new_status)
            st.rerun()
        if new_status == 2:
            note = st.text_area("Sorununu yaz — danışmanın panelde görür:",
                                value=entry["note"] if entry else "",
                                key=f"note_{sid}")
            if st.button("Sorunu gönder", key=f"send_{sid}"):
                if note.strip():
                    db_set_step(my_record["student_no"], key, 2, note.strip())
                    st.rerun()
                else:
                    st.error("Önce sorununu kısaca yaz.")
        if entry and entry["reply"]:
            with st.expander("💬 Danışman cevabı"):
                st.info(entry["reply"])

    c1, c2 = st.columns([1, 3])
    if c1.button("Seçimden vazgeç", key="withdraw_action"):
        db_withdraw(my_record["student_no"])
        st.rerun()

    with st.expander("§ Zorunlu Deney Matrisi (her makale için)"):
        st.markdown(
            "1. **Doğrulama** — Veri setini böl, baseline'ı sıfır müdahale ile koştur → "
            "Baseline Metrik Tablosu\n"
            "2. **Hipotez & Müdahale** — Stratejiyi koda enjekte et, aynı seed/split ile koş → "
            "Yeni ağırlıklar & loglar\n"
            "3. **Ablation Study** — Bileşenleri tek tek kapat/aç → Bileşen Etki Tablosu\n"
            "4. **Hata Analizi** — Rakibin bilemediği 3–5 uç örneği görselleştir → "
            "Niteliksel karşılaştırma grafiği"
        )
        st.caption(
            "Kural: bir manipülasyon 3 seed ortalamasında baseline'ı standart sapmayı aşarak "
            "geçmiyorsa yayına koyma. Reproduced baseline olmayan karşılaştırma geçersizdir."
        )


def student_view():
    st.markdown(
        '<div class="neon-title">MAKALE KONULARI</div>'
        '<div class="neon-sub">Yapay Zeka Dersi · Orkestra Deney Protokolü</div>'
        '<hr class="neon-rule">',
        unsafe_allow_html=True,
    )

    ident = st.session_state.get("identity")
    my_record = db_get(ident["email"]) if ident else None
    taken = db_taken_topics()

    # ── North-star KPI satırı ──
    total = sum(len(c["topics"]) for c in CATEGORIES)
    dolu = len(taken)
    if my_record:
        steps_done = 1 + sum(bool(my_record[f]) for f in STEP_FIELD.values())
        my_issues = sum(1 for f in db_get_feedback(my_record["student_no"]).values()
                        if f["status"] == 2)
    else:
        steps_done, my_issues = 0, 0
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Kalan konu", total - dolu)          # north star
    k2.metric("Toplam konu", total)
    k3.metric("Seçilmiş", dolu)
    k4.metric("İlerlemen", f"{steps_done}/5" if my_record else "—")
    k5.metric("Sorun bildirimin", my_issues if my_record else "—")

    if my_record:
        _cat, topic = TOPIC_BY_ID.get(my_record["topic_id"], (None, None))
        st.success(
            f"👤 **{my_record['student_name']}** ({my_record['student_no']}) — "
            f"Seçili konu: **[{my_record['topic_code']}]** "
            f"{topic['title'] if topic else my_record['topic_title']} · "
            f"aksiyon planın sayfanın altında."
        )
    elif ident:
        st.info(f"👤 **{ident['name']}** ({ident['email']}) — henüz konu seçmedin. "
                "Aşağıdan bir dal aç ve konunu seç.")
    else:
        st.warning("Konu seçebilmek için önce sol menüden **giriş yap** veya kayıt ol.")

    st.divider()

    # ── Solda filtreler · ortada hiyerarşik dallar ──
    fcol, mcol = st.columns([1, 3.4], gap="large")
    with fcol:
        st.markdown("### 🎚 Filtreler")
        q = st.text_input("🔍 Konu ara", placeholder="ör. RAG, GNN, CIFAR…")
        only_free = st.checkbox("Sadece müsait konular")
        diffs = st.multiselect("Zorluk", ["Kolay", "Orta", "İleri"])
        fits = st.multiselect("Orkestra uyumu", ["Çok yüksek", "Yüksek", "Orta"])
        filters_on = bool(q or only_free or diffs or fits)
        st.caption("Dallar kapalı gelir; bir dal açıkken başkasına tıklarsan önceki "
                   "kapanır. Filtre aktifken eşleşen dallar kendiliğinden açılır.")

    def topic_matches(t):
        if only_free and t["id"] in taken and (
                not my_record or my_record["topic_id"] != t["id"]):
            return False
        if diffs and DIFF_LABEL[t["difficulty"]] not in diffs:
            return False
        if fits and t["orchFit"] not in fits:
            return False
        if q:
            ql = q.lower()
            hay = (t["title"] + t["dataset"]["name"] + t["baseline"]["name"]
                   + t["target"]).lower()
            if ql not in hay:
                return False
        return True

    with mcol:
        branch = st.session_state.get("branch")
        for cat in CATEGORIES:
            topics = [t for t in cat["topics"] if topic_matches(t)]
            if filters_on and not topics:
                continue
            dolu_n = sum(1 for t in cat["topics"] if t["id"] in taken)
            # kapalıyken: akordeon — birini açınca diğerleri kapalı kalır;
            # filtre aktifken eşleşme olan dallar otomatik açılır
            is_open = (branch == cat["no"]) or (filters_on and branch is None)
            if not is_open:
                if st.button(f"▶ {cat['no']} · {cat['name']} — "
                             f"{len(topics)}/{len(cat['topics'])} konu · {dolu_n} dolu",
                             key=f"br_{cat['no']}", use_container_width=True):
                    st.session_state["branch"] = cat["no"]
                    st.rerun()
                continue
            if st.button(f"▼ {cat['no']} · {cat['name']} — "
                         f"{len(topics)}/{len(cat['topics'])} konu · {dolu_n} dolu",
                         key=f"br_{cat['no']}", use_container_width=True):
                st.session_state.pop("branch", None)
                st.rerun()
            st.caption(f"{cat['short']} — {cat['blurb']}")
            for t in topics:
                topic_card(cat, t, my_record, taken)
            st.divider()

    # ── Bonus havuzu ──
    with st.expander("➕ Bonus havuzu"):
        for b_ in BONUS:
            st.markdown(f"**{b_['code']} · {b_['name']}** — {b_['title']}")
            st.markdown(f"**Veri:** {b_['dataset']}  \n**Rakip:** {b_['baseline']}")
            st.caption(b_["note"])

    # ── Aksiyon planı (seçim yapınca, sayfanın altında) ──
    if my_record:
        st.divider()
        render_action_plan(my_record)


# ───────────────────────── Danışman paneli ─────────────────────────
def panel_view():
    st.markdown(
        '<div class="neon-title">SINIF DURUMU</div>'
        '<div class="neon-sub">Danışman Paneli · Anlık İlerleme</div>'
        '<hr class="neon-rule">',
        unsafe_allow_html=True,
    )
    st.caption("Her satır bir öğrenci: seçtiği konu ve beş aşamalı ilerlemesi.")

    rows = db_all()
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Konu seçti", len(rows))
    m2.metric("Dataset indi", sum(r["dataset_downloaded"] for r in rows))
    m3.metric("Rakip çalıştı", sum(r["baseline_ran"] for r in rows))
    m4.metric("Kod stabil", sum(r["code_stable"] for r in rows))
    m5.metric("Rakip geçildi", sum(r["beat_baseline"] for r in rows))

    if st.button("🔄 Yenile"):
        st.rerun()

    if not rows:
        st.info("Henüz kayıt yok — öğrenciler konu seçtikçe burada listelenir.")
        return

    st.subheader("Öğrenciler")
    fb_all = db_all_feedback()
    fb_map = {}
    for f in fb_all:
        fb_map.setdefault(f["student_no"], {})[f["step"]] = {
            "status": f["status"], "note": f["note"], "reply": f["reply"]}
    header = st.columns([2, 2.2, 3.2, 3.6, 1.4])
    for col, h in zip(header, ["Öğrenci", "E-posta", "Konu", "İlerleme", "Güncelleme"]):
        col.markdown(f"**{h}**")
    st.divider()
    for r in rows:
        c = st.columns([2, 2.2, 3.2, 3.6, 1.4])
        c[0].markdown(f"**{r['student_name']}**")
        c[1].code(r["student_no"])
        c[2].markdown(f"**{r['topic_code']}** — {r['topic_title'][:90]}")
        c[3].markdown(mini_flow_html(r, fb_map.get(r["student_no"])),
                      unsafe_allow_html=True)
        c[4].caption(datetime.fromisoformat(r["updated_at"]).strftime("%d/%m %H:%M"))
    st.markdown(
        '<div class="mlegend">Düğümler soldan sağa: Konu seçildi · Veri seti · '
        'Rakip çalıştı · Kod stabil · Rakip geçildi — dolu hat = tamamlanan aşama, '
        'magenta pulse = sıradaki adım, kırmızı pulse = sorun bildirildi.</div>',
        unsafe_allow_html=True,
    )

    # ── Sorun bildirimleri: danışman cevap kutusu ──
    issues = [f for f in fb_all if f["status"] == 2]
    if issues:
        st.subheader("🚨 Sorun bildirimleri")
        name_of = {r["student_no"]: r["student_name"] for r in rows}
        label_of = {k: l for k, l, _ in STEPS[1:]}
        for f in issues:
            who = name_of.get(f["student_no"], "?")
            step_label = label_of.get(f["step"], f["step"])
            with st.expander(f"⚠ {who} ({f['student_no']}) — {step_label}"):
                st.warning(f"**Öğrencinin sorunu:** {f['note'] or '(açıklama yazılmadı)'}")
                if f["reply"]:
                    st.info(f"**Gönderdiğin cevap:** {f['reply']}")
                rid = f"{f['student_no']}_{f['step']}"
                reply = st.text_area("Cevabın (öğrenci kendi ekranında görür):",
                                     value=f["reply"], key=f"reply_{rid}")
                if st.button("Cevabı gönder", key=f"replybtn_{rid}"):
                    if reply.strip():
                        db_reply(f["student_no"], f["step"], reply.strip())
                        st.rerun()
                    else:
                        st.error("Cevap boş olamaz.")
    else:
        st.caption("Aktif sorun bildirimi yok.")

    st.subheader("Konu başına seçim dağılımı")
    import collections
    counts = collections.Counter(r["topic_code"] for r in rows)
    st.bar_chart(dict(counts.most_common()))

    st.subheader("Dışa aktar")
    lines = ["AI DERSİ — SINIF DURUM RAPORU", "=" * 50, ""]
    for r in rows:
        durum = [s[1] for s in STEPS[1:] if r[{
            "dataset": "dataset_downloaded", "baseline": "baseline_ran",
            "stable": "code_stable", "beat": "beat_baseline"}[s[0]]]]
        lines.append(f"{r['student_name']} ({r['student_no']}) — "
                     f"[{r['topic_code']}] {r['topic_title']}")
        lines.append(f"   İlerleme: konu seçildi" + (", " + ", ".join(durum) if durum else ""))
        lines.append("")
    st.download_button("📄 Raporu indir (.txt)", "\n".join(lines),
                       file_name="sinif-durum-raporu.txt")


# ───────────────────────── Kimlik doğrulama formları ─────────────────────────
MIN_PW_LEN = 6


def _login_form():
    email = st.text_input("Okul e-postan", placeholder=f"ornek@{EMAIL_DOMAIN}",
                          key="login_email")
    pw = st.text_input("Şifre", type="password", key="login_pw")
    if st.button("Giriş yap", type="primary", key="login_btn"):
        acc = db_get_account(email.strip().lower())
        if not acc:
            st.error("Bu e-postayla kayıt bulunamadı — önce **Kayıt Ol** sekmesini kullan.")
        elif not db_check_password(acc, pw):
            st.error("Şifre hatalı.")
        else:
            st.session_state["identity"] = {"name": acc["name"], "email": acc["email"]}
            st.rerun()


def _send_otp_guarded(name, email, purpose):
    pending = st.session_state.get("pending_otp")
    if pending and time.time() - pending["last_sent"] < OTP_RESEND_COOLDOWN:
        kalan = int(OTP_RESEND_COOLDOWN - (time.time() - pending["last_sent"]))
        st.warning(f"Yeni kod istemeden önce {kalan} sn bekle.")
        return
    ok, err = request_otp(name, email, purpose)
    if ok:
        st.success(f"Kod **{email}** adresine gönderildi.")
    else:
        st.error(err)


def _register_form():
    name = st.text_input("Ad Soyad", key="reg_name")
    email = st.text_input("Okul e-postan", placeholder=f"ornek@{EMAIL_DOMAIN}",
                          key="reg_email")
    if st.button("Doğrulama kodu gönder", type="primary", key="reg_btn"):
        email_clean = email.strip().lower()
        if len(name.strip()) < 2:
            st.error("Ad Soyad gerekli.")
        elif not EMAIL_RE.match(email_clean):
            st.error(f"Sadece @{EMAIL_DOMAIN} uzantılı okul e-postası kabul edilir.")
        elif db_get_account(email_clean):
            st.error("Bu e-posta zaten kayıtlı — giriş yap veya şifreni sıfırla.")
        else:
            _send_otp_guarded(name.strip(), email_clean, "register")


def _reset_form():
    email = st.text_input("Kayıtlı okul e-postan", placeholder=f"ornek@{EMAIL_DOMAIN}",
                          key="reset_email")
    if st.button("Sıfırlama kodu gönder", type="primary", key="reset_btn"):
        email_clean = email.strip().lower()
        acc = db_get_account(email_clean) if EMAIL_RE.match(email_clean) else None
        if not acc:
            st.error("Bu e-postayla kayıt bulunamadı.")
        else:
            _send_otp_guarded(acc["name"], email_clean, "reset")


def _otp_verify_form(p):
    """Kod + şifre belirleme formu (kayıt ve şifre sıfırlama ortak)."""
    is_register = p["purpose"] == "register"
    st.caption(f"Kod **{p['email']}** adresine gönderildi ({OTP_TTL // 60} dk geçerli). "
               "Spam klasörünü de kontrol et.")
    code_in = st.text_input("6 haneli doğrulama kodu", max_chars=6, key="otp_code")
    lbl = "Şifre belirle" if is_register else "Yeni şifre"
    pw1 = st.text_input(lbl, type="password", key="otp_pw1")
    pw2 = st.text_input(lbl + " (tekrar)", type="password", key="otp_pw2")
    btn = "Hesabı oluştur ve giriş yap" if is_register else "Şifreyi sıfırla ve giriş yap"
    c1, c2 = st.columns(2)
    if c2.button("Vazgeç", key="otp_cancel"):
        st.session_state.pop("pending_otp")
        st.rerun()
    if c1.button(btn, type="primary", key="otp_go"):
        if time.time() > p["expires"]:
            st.session_state.pop("pending_otp")
            st.error("Kodun süresi doldu. Yeni kod iste.")
            st.rerun()
        elif p["attempts"] >= OTP_MAX_ATTEMPTS:
            st.session_state.pop("pending_otp")
            st.error("Çok fazla hatalı deneme. Yeni kod iste.")
            st.rerun()
        elif not code_in.strip() or _hash_code(code_in) != p["code_hash"]:
            p["attempts"] += 1
            st.error(f"Kod hatalı. Kalan deneme: {OTP_MAX_ATTEMPTS - p['attempts']}")
        elif len(pw1) < MIN_PW_LEN:
            st.error(f"Şifre en az {MIN_PW_LEN} karakter olmalı.")
        elif pw1 != pw2:
            st.error("Şifreler eşleşmiyor.")
        else:
            if is_register:
                db_create_account(p["email"], p["name"], pw1)
                name = p["name"]
            else:
                db_update_password(p["email"], pw1)
                name = db_get_account(p["email"])["name"]
            st.session_state["identity"] = {"name": name, "email": p["email"]}
            st.session_state.pop("pending_otp")
            st.rerun()


# ───────────────────────── Kenar çubuğu / yönlendirme ─────────────────────────
with st.sidebar:
    st.header("AI Dersi · 2026")
    mode = st.radio("Görünüm", ["📋 Konu seçimi (Öğrenci)", "📊 Danışman Paneli"])

    if mode.startswith("📋"):
        st.divider()
        st.subheader("Kimliğin")
        ident = st.session_state.get("identity")
        if ident:
            st.success(f"{ident['name']}\n\n{ident['email']}")
            if st.button("Çıkış yap"):
                st.session_state.pop("identity")
                st.rerun()
        else:
            pending = st.session_state.get("pending_otp")
            if pending:
                _otp_verify_form(pending)
            else:
                tab = st.radio("Hesap işlemi",
                               ["🔑 Giriş Yap", "📝 Kayıt Ol", "♻ Şifremi Unuttum"],
                               horizontal=True, label_visibility="collapsed")
                if tab.endswith("Giriş Yap"):
                    _login_form()
                elif tab.endswith("Kayıt Ol"):
                    _register_form()
                else:
                    _reset_form()
        st.caption("Kayıtlar bu sunucudaki veritabanında (submissions.db) tutulur; "
                   "danışmanın panelden anlık görür.")

if mode.startswith("📋"):
    student_view()
else:
    ok = st.session_state.get("panel_ok", False)
    if not ok:
        pw = st.sidebar.text_input("Panel şifresi", type="password")
        if st.sidebar.button("Panele gir"):
            if pw == PANEL_SIFRESI:
                st.session_state["panel_ok"] = True
                st.rerun()
            else:
                st.sidebar.error("Yanlış şifre.")
        st.info("Bu panel şifre korumalıdır. Şifreyi danışmanından al.")
    else:
        if st.sidebar.button("Panelden çık"):
            st.session_state["panel_ok"] = False
            st.rerun()
        panel_view()
