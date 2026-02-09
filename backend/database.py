"""
Простая SQLite-база для учёта посетителей и обращений к API.
Файл БД: data/visits.db
"""
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Путь к файлу БД (от корня проекта)
BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "visits.db"


def _ensure_data_dir():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def init_db() -> None:
    """Создаёт таблицу visits, если её ещё нет."""
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip_address TEXT,
                user_agent TEXT,
                path TEXT,
                method TEXT,
                created_at TEXT
            )
        """)
        conn.commit()
    finally:
        conn.close()


def log_visit(ip_address: str, user_agent: str, path: str, method: str) -> None:
    """Пишет один визит в БД."""
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO visits (ip_address, user_agent, path, method, created_at) VALUES (?, ?, ?, ?, ?)",
            (ip_address or "", (user_agent or "")[:500], path or "", method or "", datetime.utcnow().isoformat() + "Z")
        )
        conn.commit()
    except Exception as e:
        print(f"⚠️  Ошибка записи визита в БД: {e}")
    finally:
        conn.close()


def get_visits(limit: int = 500) -> List[Dict[str, Any]]:
    """Возвращает последние визиты (новые сверху)."""
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        cur = conn.execute(
            "SELECT id, ip_address, user_agent, path, method, created_at FROM visits ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()
