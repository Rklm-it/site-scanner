"""Хранилище статусов лидов (SQLite): статус аутрича и заметка по домену.

Переживает перезапуски и новые сканы — уже обработанные лиды видно всегда.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time

STATUSES = ("", "написал", "звонил", "недозвон", "перезвонить", "интерес", "ответили", "клиент", "отказ")


class LeadStore:
    def __init__(self, path: str):
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        with self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS lead_state("
                "domain TEXT PRIMARY KEY, status TEXT, note TEXT, updated REAL)"
            )
            # миграция: колонка callback (дата «перезвонить») для старых баз
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(lead_state)")}
            if "callback" not in cols:
                self._conn.execute("ALTER TABLE lead_state ADD COLUMN callback TEXT")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS leads("
                "domain TEXT PRIMARY KEY, data TEXT, outreach_score INTEGER, "
                "first_seen REAL, last_seen REAL)"
            )

    def all(self) -> dict[str, dict]:
        with self._lock:
            rows = self._conn.execute("SELECT domain, status, note, callback FROM lead_state").fetchall()
        return {d: {"status": s or "", "note": n or "", "callback": cb or ""} for d, s, n, cb in rows}

    def get(self, domain: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                "SELECT status, note, callback FROM lead_state WHERE domain=?", (domain,)
            ).fetchone()
        if not row:
            return {"status": "", "note": "", "callback": ""}
        return {"status": row[0] or "", "note": row[1] or "", "callback": row[2] or ""}

    def set(self, domain: str, *, status: str | None = None, note: str | None = None,
            callback: str | None = None) -> dict:
        cur = self.get(domain)
        new_status = cur["status"] if status is None else status
        new_note = cur["note"] if note is None else note
        new_callback = cur["callback"] if callback is None else callback
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO lead_state(domain, status, note, callback, updated)"
                " VALUES(?,?,?,?,?)",
                (domain, new_status, new_note, new_callback, time.time()),
            )
        return {"status": new_status, "note": new_note, "callback": new_callback}

    # --- накопительная база просканированных лидов ---
    def upsert_leads(self, rows: list[dict]) -> None:
        """Складывает лиды в базу (дедуп по домену; first_seen сохраняется)."""
        now = time.time()
        with self._lock, self._conn:
            for r in rows:
                dom = r.get("domain")
                if not dom:
                    continue
                prev = self._conn.execute(
                    "SELECT first_seen FROM leads WHERE domain=?", (dom,)
                ).fetchone()
                first = prev[0] if prev else now
                self._conn.execute(
                    "INSERT OR REPLACE INTO leads(domain, data, outreach_score, first_seen, last_seen)"
                    " VALUES(?,?,?,?,?)",
                    (dom, json.dumps(r, ensure_ascii=False), int(r.get("outreach_score") or 0), first, now),
                )

    def all_leads(self) -> list[dict]:
        """Все накопленные лиды, отсортированные по приоритету, со свежим статусом."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT data, first_seen, last_seen FROM leads ORDER BY outreach_score DESC"
            ).fetchall()
        states = self.all()
        out: list[dict] = []
        for data, first, last in rows:
            r = json.loads(data)
            st = states.get(r.get("domain"), {})
            r["status"] = st.get("status", "")
            r["note"] = st.get("note", "")
            r["callback"] = st.get("callback", "")
            r["first_seen"] = first
            r["last_seen"] = last
            out.append(r)
        return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()
