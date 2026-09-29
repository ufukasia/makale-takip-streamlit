# -*- coding: utf-8 -*-
"""
Turso kurulum + tasima yardimcisi.

Ne yapar?
    1. .streamlit/secrets.toml icindeki [turso] bilgileriyle baglanir.
    2. Tablolari olusturur (zaten varsa dokunmaz).
    3. Yerel submissions.db icindeki tum kayitlari buluta kopyalar.
    4. Sonucu ozetler.

Kullanim (streamlit klasorunun icinden):
    python turso_kur.py            # tablolari kur + yerel veriyi yukle
    python turso_kur.py --kontrol  # sadece baglantiyi ve kayit sayilarini goster

Turso hesabi / veritabani acma adimlari icin README.md'ye bak.
"""

import argparse
import sqlite3
import sys
from pathlib import Path

from turso_db import Turso, TursoError

BASE = Path(__file__).parent
DB_PATH = BASE / "submissions.db"
SECRETS = BASE / ".streamlit" / "secrets.toml"

SCHEMA = [
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
    )""",
    """CREATE TABLE IF NOT EXISTS step_feedback (
        student_no    TEXT NOT NULL,
        step          TEXT NOT NULL,
        status        INTEGER NOT NULL DEFAULT 0,
        student_note  TEXT NOT NULL DEFAULT '',
        advisor_reply TEXT NOT NULL DEFAULT '',
        updated_at    TEXT NOT NULL,
        PRIMARY KEY (student_no, step)
    )""",
    """CREATE TABLE IF NOT EXISTS accounts (
        email      TEXT PRIMARY KEY,
        name       TEXT NOT NULL,
        salt       TEXT NOT NULL,
        pw_hash    TEXT NOT NULL,
        created_at TEXT NOT NULL
    )""",
]

TABLES = {
    "submissions": ["student_no", "student_name", "topic_id", "topic_code",
                    "topic_title", "dataset_downloaded", "baseline_ran",
                    "code_stable", "beat_baseline", "updated_at"],
    "step_feedback": ["student_no", "step", "status", "student_note",
                      "advisor_reply", "updated_at"],
    "accounts": ["email", "name", "salt", "pw_hash", "created_at"],
}


def read_turso_secrets():
    """secrets.toml icindeki [turso] bolumunu okur."""
    if not SECRETS.exists():
        sys.exit(f"HATA: {SECRETS} yok. Once secrets.toml.example'i kopyala.")
    try:
        import tomllib                      # Python 3.11+
        cfg = tomllib.loads(SECRETS.read_text(encoding="utf-8"))
    except ModuleNotFoundError:
        import toml                         # pip install toml
        cfg = toml.loads(SECRETS.read_text(encoding="utf-8"))
    turso = cfg.get("turso") or {}
    if not turso.get("url"):
        sys.exit("HATA: secrets.toml icinde [turso] url tanimli degil. "
                 "README.md'deki adimlari izle.")
    return turso["url"], turso.get("auth_token") or turso.get("token") or ""


def local_rows():
    """Yerel submissions.db icindeki satirlari okur."""
    if not DB_PATH.exists():
        print(f"! Yerel veritabani yok ({DB_PATH.name}) — sadece tablolar kurulacak.")
        return {}
    c = sqlite3.connect(DB_PATH)
    data = {}
    for table, cols in TABLES.items():
        try:
            data[table] = c.execute(f"SELECT {', '.join(cols)} FROM {table}").fetchall()
        except sqlite3.OperationalError:
            data[table] = []                # tablo yerelde hic olusmamis
    c.close()
    return data


def main():
    ap = argparse.ArgumentParser(description="Turso kurulum/tasima araci")
    ap.add_argument("--kontrol", action="store_true",
                    help="Sadece baglantiyi ve buluttaki kayit sayilarini goster")
    args = ap.parse_args()

    url, token = read_turso_secrets()
    print(f"→ Turso: {url}")
    try:
        db = Turso(url, token)
        db.ping()
    except TursoError as exc:
        sys.exit(f"HATA: {exc}")
    print("✓ Baglanti kuruldu.")

    db.batch([(ddl, ()) for ddl in SCHEMA])
    print("✓ Tablolar hazir.")

    if not args.kontrol:
        data = local_rows()
        for table, cols in TABLES.items():
            rows = data.get(table) or []
            if not rows:
                continue
            placeholders = ",".join("?" * len(cols))
            sql = (f"INSERT OR REPLACE INTO {table} ({', '.join(cols)}) "
                   f"VALUES ({placeholders})")
            db.batch([(sql, row) for row in rows])
            print(f"✓ {table}: {len(rows)} kayit buluta yazildi.")

    print("\nBuluttaki durum:")
    for table in TABLES:
        n = db.execute(f"SELECT COUNT(*) FROM {table}")[0][0]
        print(f"   {table}: {n} kayit")
    print("\nHazir. Ayni [turso] bilgilerini Streamlit Cloud > Settings > Secrets "
          "kismina da yapistir; boylece uygulama uyanip yeniden kurulsa bile "
          "kayitlar yerinde kalir.")


if __name__ == "__main__":
    main()
