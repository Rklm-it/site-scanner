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
            # миграции колонок для старых баз
            cols = {r[1] for r in self._conn.execute("PRAGMA table_info(lead_state)")}
            if "callback" not in cols:
                self._conn.execute("ALTER TABLE lead_state ADD COLUMN callback TEXT")
            if "deal_amount" not in cols:
                self._conn.execute("ALTER TABLE lead_state ADD COLUMN deal_amount REAL")
            if "mrr" not in cols:
                self._conn.execute("ALTER TABLE lead_state ADD COLUMN mrr REAL")
            if "prototype_url" not in cols:
                self._conn.execute("ALTER TABLE lead_state ADD COLUMN prototype_url TEXT")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS leads("
                "domain TEXT PRIMARY KEY, data TEXT, outreach_score INTEGER, "
                "first_seen REAL, last_seen REAL)"
            )

    _COLS = "status, note, callback, deal_amount, mrr, prototype_url"

    def _row_to_dict(self, row) -> dict:
        if not row:
            return {"status": "", "note": "", "callback": "", "deal_amount": 0, "mrr": 0, "prototype_url": ""}
        return {"status": row[0] or "", "note": row[1] or "", "callback": row[2] or "",
                "deal_amount": row[3] or 0, "mrr": row[4] or 0, "prototype_url": row[5] or ""}

    def all(self) -> dict[str, dict]:
        with self._lock:
            rows = self._conn.execute(f"SELECT domain, {self._COLS} FROM lead_state").fetchall()
        return {r[0]: self._row_to_dict(r[1:]) for r in rows}

    def get(self, domain: str) -> dict:
        with self._lock:
            row = self._conn.execute(
                f"SELECT {self._COLS} FROM lead_state WHERE domain=?", (domain,)
            ).fetchone()
        return self._row_to_dict(row)

    def set(self, domain: str, *, status: str | None = None, note: str | None = None,
            callback: str | None = None, deal_amount: float | None = None,
            mrr: float | None = None, prototype_url: str | None = None) -> dict:
        cur = self.get(domain)
        new = {
            "status": cur["status"] if status is None else status,
            "note": cur["note"] if note is None else note,
            "callback": cur["callback"] if callback is None else callback,
            "deal_amount": cur["deal_amount"] if deal_amount is None else deal_amount,
            "mrr": cur["mrr"] if mrr is None else mrr,
            "prototype_url": cur["prototype_url"] if prototype_url is None else prototype_url,
        }
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO lead_state"
                "(domain, status, note, callback, deal_amount, mrr, prototype_url, updated)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (domain, new["status"], new["note"], new["callback"], new["deal_amount"],
                 new["mrr"], new["prototype_url"], time.time()),
            )
        return new

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
            r["deal_amount"] = st.get("deal_amount", 0)
            r["mrr"] = st.get("mrr", 0)
            r["prototype_url"] = st.get("prototype_url", "")
            r["first_seen"] = first
            r["last_seen"] = last
            out.append(r)
        return out

    def close(self) -> None:
        with self._lock:
            self._conn.close()
