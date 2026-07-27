"""Хранилище статусов лидов (SQLite): статус аутрича и заметка по домену.

Переживает перезапуски и новые сканы — уже обработанные лиды видно всегда.
"""

from __future__ import annotations

import sqlite3
import threading
import time

STATUSES = ("", "написал", "ответили", "клиент", "отказ")


class LeadStore:
    def __init__(self, path: str):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS lead_state("
                "domain TEXT PRIMARY KEY, status TEXT, note TEXT, updated REAL)"
            )

    def all(self) -> dict[str, dict]:
        with self._lock:
            rows = self._conn.execute("SELECT domain, status, note FROM lead_state").fetchall()
        return {d: {"status": s or "", "note": n or ""} for d, s, n in rows}

    def get(self, domain: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT status, note FROM lead_state WHERE domain=?", (domain,)
            ).fetchone()
        return {"status": row[0] or "", "note": row[1] or ""} if row else {"status": "", "note": ""}

    def set(self, domain: str, *, status: str | None = None, note: str | None = None) -> dict:
        cur = self.get(domain)
        new_status = cur["status"] if status is None else status
        new_note = cur["note"] if note is None else note
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO lead_state(domain, status, note, updated) VALUES(?,?,?,?)",
                (domain, new_status, new_note, time.time()),
            )
        return {"status": new_status, "note": new_note}

    def close(self) -> None:
        with self._lock:
            self._conn.close()
