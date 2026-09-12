# -*- coding: utf-8 -*-
"""
Yüksek Lisans Yapay Zeka Dersi — Makale Konu Seçim & İlerleme Takip (Streamlit)

Çalıştırma:
    pip install -r requirements.txt
    streamlit run app.py

- Öğrenci: isim + numarasını girer, konu seçer, ilerleme kutularını işaretler.
- Danışman: yan menüden "Danışman Paneli"ni açar (panel şifresi aşağıda).
- Tüm kayıtlar bu klasördeki submissions.db (SQLite) dosyasında tutulur.
  Aynı sunucuda çalışan tek uygulama olduğu için herkes aynı veriyi görür.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

import streamlit as st

BASE = Path(__file__).parent
DB_PATH = BASE / "submissions.db"

# ── Danışman paneli şifresi (değiştirmek için bu satırı düzenle) ──
PANEL_SIFRESI = "orkestra2026"

DIFF_LABEL = {1: "Kolay", 2: "Orta", 3: "İleri"}

STEPS = [
    ("selected", "Konu seçildi", "Kaydın panele düştü"),
    ("dataset", "Veri seti indirildi", "Orkestra veri setini indirdi ve doğruladı"),
    ("baseline", "Rakip (baseline) çalıştı", "Otoriter yöntem koşuldu, referans sonuç kaydedildi"),
    ("stable", "Kod stabil çalışıyor", "Deney döngüsü hatasız, tekrarlanabilir çalışıyor"),
    ("beat", "Rakip geçildi", "Manipüle edilmiş yöntem baseline'ı geçti (çoklu seed)"),
]

st.set_page_config(page_title="Makale Konuları — AI Dersi", page_icon="📚", layout="wide")


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
    c = conn()
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
    c.commit()
    c.close()


def db_set_progress(student_no: str, field: str, value: bool):
    c = conn()
    c.execute(
        f"UPDATE submissions SET {field} = ?, updated_at = ? WHERE student_no = ?",
        (1 if value else 0, datetime.now().isoformat(timespec="seconds"), student_no),
    )
    c.commit()
    c.close()


def db_withdraw(student_no: str):
    c = conn()
    c.execute("DELETE FROM submissions WHERE student_no = ?", (student_no,))
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


DATA = load_topics()
CATEGORIES = DATA["categories"]
BONUS = DATA["bonus"]
TOPIC_BY_ID = {t["id"]: (c, t) for c in CATEGORIES for t in c["topics"]}


# ───────────────────────── Öğrenci görünümü ─────────────────────────
def topic_card(cat, topic, my_record):
    mine = my_record is not None and my_record["topic_id"] == topic["id"]
    header = f"**{topic['code']}** · {topic['title']}"
    with st.expander(header, expanded=False):
        if topic.get("titleEn"):
            st.caption(f"EN başlık: {topic['titleEn']}")

        c1, c2, c3 = st.columns(3)
        c1.markdown(f"**Zorluk:** {DIFF_LABEL[topic['difficulty']]}")
        c2.markdown(f"**Süre:** {topic['duration']}")
        c3.markdown(f"**Orkestra uyumu:** {topic['orchFit']}")
        st.markdown(f"**GPU/Sistem:** {topic['gpu']} · {topic['system']}")
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
        # Seçim + ilerleme
        if mine:
            st.success("Bu konuyu seçtin ✓ — ilerleme kutuların danışman paneline anlık yansır.")
            cols = st.columns(4)
            field_map = {
                "dataset": "dataset_downloaded",
                "baseline": "baseline_ran",
                "stable": "code_stable",
                "beat": "beat_baseline",
            }
            for col, (key, label, desc) in zip(cols, STEPS[1:]):
                cur = bool(my_record[field_map[key]])
                new = col.checkbox(f"**{label}**", value=cur,
                                   help=desc, key=f"prog_{my_record['student_no']}_{key}")
                if new != cur:
                    db_set_progress(my_record["student_no"], field_map[key], new)
                    st.rerun()
            if st.button("Seçimden vazgeç", key=f"withdraw_{topic['id']}"):
                db_withdraw(my_record["student_no"])
                st.rerun()
        else:
            already = my_record is not None
            if st.button(
                "Başka konu seçili (önce ondan vazgeç)" if already else "Bu konuyu seç",
                key=f"pick_{topic['id']}",
                disabled=already,
            ):
                ident = st.session_state.get("identity")
                if not ident:
                    st.error("Önce sol menüden adını ve öğrenci numaranı gir.")
                else:
                    db_register(ident["no"], ident["name"], topic)
                    st.rerun()


def student_view():
    st.title("MAKALE KONULARI.")
    st.markdown(
        f"**{len(CATEGORIES)} yapay zeka bölümü, "
        f"{sum(len(c['topics']) for c in CATEGORIES)} makale seçeneği.** "
        "Her konu aynı protokolü izler: orkestra veri setini indirir, otoriter yöntemi çalıştırır, "
        "sonucu kaydeder, ardından yöntemi manipüle ederek daha iyisini arar."
    )

    ident = st.session_state.get("identity")
    my_record = db_get(ident["no"]) if ident else None

    if my_record:
        cat, topic = TOPIC_BY_ID.get(my_record["topic_id"], (None, None))
        st.success(
            f"👤 **{my_record['student_name']}** ({my_record['student_no']}) — "
            f"Seçili konu: **[{my_record['topic_code']}]** "
            f"{topic['title'] if topic else my_record['topic_title']}"
        )
    elif ident:
        st.info(f"👤 **{ident['name']}** ({ident['no']}) — henüz konu seçmedin.")
    else:
        st.warning("Konu seçebilmek için önce sol menüden **ad soyad + öğrenci numaranı** gir.")

    # Filtreler
    q = st.text_input("🔍 Konu ara", placeholder="ör. RAG, GNN, CIFAR…")
    cat_names = ["Tümü"] + [f"{c['no']} · {c['name']}" for c in CATEGORIES]
    cat_sel = st.selectbox("Kategori", cat_names)

    for cat in CATEGORIES:
        if cat_sel != "Tümü" and not cat_sel.startswith(cat["no"] + " "):
            continue
        topics = cat["topics"]
        if q:
            ql = q.lower()
            topics = [t for t in topics if ql in (
                t["title"] + t["dataset"]["name"] + t["baseline"]["name"] + t["target"]
            ).lower()]
        if not topics:
            continue
        st.header(f"{cat['no']} · {cat['name']}")
        st.caption(f"{cat['short']} — {cat['blurb']}")
        for t in topics:
            topic_card(cat, t, my_record)

    with st.expander("➕ Bonus havuzu"):
        for b_ in BONUS:
            st.markdown(f"**{b_['code']} · {b_['name']}** — {b_['title']}")
            st.markdown(f"**Veri:** {b_['dataset']}  \n**Rakip:** {b_['baseline']}")
            st.caption(b_["note"])

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


# ───────────────────────── Danışman paneli ─────────────────────────
def panel_view():
    st.title("SINIF DURUMU.")
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
    header = st.columns([2, 1.2, 3.5, 1, 1, 1, 1, 1, 1.4])
    for col, h in zip(header, ["Öğrenci", "Numara", "Konu", "Seçti",
                               "Dataset", "Rakip", "Stabil", "Geçti", "Güncelleme"]):
        col.markdown(f"**{h}**")
    st.divider()
    for r in rows:
        c = st.columns([2, 1.2, 3.5, 1, 1, 1, 1, 1, 1.4])
        c[0].markdown(f"**{r['student_name']}**")
        c[1].code(r["student_no"])
        c[2].markdown(f"**{r['topic_code']}** — {r['topic_title'][:90]}")
        for i, f in enumerate(["selected", "dataset_downloaded", "baseline_ran",
                               "code_stable", "beat_baseline"]):
            on = True if f == "selected" else bool(r[f])
            c[3 + i].markdown("✅" if on else "⬜")
        c[8].caption(datetime.fromisoformat(r["updated_at"]).strftime("%d/%m %H:%M"))

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


# ───────────────────────── Kenar çubuğu / yönlendirme ─────────────────────────
with st.sidebar:
    st.header("AI Dersi · 2026")
    mode = st.radio("Görünüm", ["📋 Konu seçimi (Öğrenci)", "📊 Danışman Paneli"])

    if mode.startswith("📋"):
        st.divider()
        st.subheader("Kimliğin")
        ident = st.session_state.get("identity")
        if ident:
            st.success(f"{ident['name']} · {ident['no']}")
            if st.button("Çıkış yap"):
                st.session_state.pop("identity")
                st.rerun()
        else:
            name = st.text_input("Ad Soyad")
            no = st.text_input("Öğrenci numarası")
            if st.button("Kaydet", type="primary"):
                if len(name.strip()) >= 2 and no.strip():
                    st.session_state["identity"] = {"name": name.strip(), "no": no.strip()}
                    st.rerun()
                else:
                    st.error("Ad ve numara gerekli.")
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
