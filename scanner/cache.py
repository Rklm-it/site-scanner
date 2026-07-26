"""Кэш на SQLite: выдача поиска, страницы и список просмотренных доменов.

Зачем: у Google CSE всего 100 запросов/день бесплатно, у Яндекс.XML тоже
лимиты. Кэш выдачи экономит квоту, кэш страниц — трафик при повторных
прогонах, а таблица seen позволяет докручивать список инкрементально,
не пересканируя уже обработанные домены.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time

from .fetcher import FetchResult


class Cache:
    def __init__(self, path: str, *, search_ttl: int = 86_400, page_ttl: int = 86_400,
                 cache_pages: bool = False):
        self.search_ttl = search_ttl
        self.page_ttl = page_ttl
        self.cache_pages = cache_pages
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._init()

    def _init(self) -> None:
        with self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS search_cache(
                    query TEXT, provider TEXT, ts REAL, urls TEXT,
                    PRIMARY KEY(query, provider));
                CREATE TABLE IF NOT EXISTS page_cache(
                    url TEXT PRIMARY KEY, ts REAL, status INTEGER,
                    final_url TEXT, html TEXT, headers TEXT, https INTEGER, tls_error INTEGER);
                CREATE TABLE IF NOT EXISTS seen(
                    domain TEXT PRIMARY KEY, ts REAL, score INTEGER);
                """
            )

    # ---- поиск ----
    def get_search(self, query: str, provider: str) -> list[str] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT ts, urls FROM search_cache WHERE query=? AND provider=?",
                (query, provider),
            ).fetchone()
        if row and time.time() - row[0] < self.search_ttl:
            return json.loads(row[1])
        return None

    def set_search(self, query: str, provider: str, urls: list[str]) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO search_cache(query, provider, ts, urls) VALUES(?,?,?,?)",
                (query, provider, time.time(), json.dumps(urls, ensure_ascii=False)),
            )

    # ---- страницы ----
    def get_page(self, url: str) -> FetchResult | None:
        if not self.cache_pages:
            return None
        with self._lock:
            row = self._conn.execute(
                "SELECT ts, status, final_url, html, headers, https, tls_error "
                "FROM page_cache WHERE url=?",
                (url,),
            ).fetchone()
        if row and time.time() - row[0] < self.page_ttl:
            return FetchResult(
                url=url, status=row[1], final_url=row[2], html=row[3],
                headers=json.loads(row[4]) if row[4] else {},
                https=bool(row[5]), tls_error=bool(row[6]),
            )
        return None

    def set_page(self, res: FetchResult) -> None:
        if not self.cache_pages or not res.ok:
            return
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO page_cache"
                "(url, ts, status, final_url, html, headers, https, tls_error) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (res.url, time.time(), res.status, res.final_url, res.html,
                 json.dumps(res.headers or {}, ensure_ascii=False),
                 int(res.https), int(res.tls_error)),
            )

    # ---- просмотренные домены ----
    def is_seen(self, domain: str) -> bool:
        with self._lock:
            row = self._conn.execute("SELECT 1 FROM seen WHERE domain=?", (domain,)).fetchone()
        return row is not None

    def mark_seen(self, domain: str, score: int) -> None:
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT OR REPLACE INTO seen(domain, ts, score) VALUES(?,?,?)",
                (domain, time.time(), score),
            )

    def close(self) -> None:
        with self._lock:
            self._conn.close()


class NullCache:
    """Заглушка с тем же интерфейсом — когда кэш отключён."""

    cache_pages = False

    def get_search(self, query: str, provider: str) -> list[str] | None:
        return None

    def set_search(self, query: str, provider: str, urls: list[str]) -> None:
        pass

    def get_page(self, url: str) -> FetchResult | None:
        return None

    def set_page(self, res: FetchResult) -> None:
        pass

    def is_seen(self, domain: str) -> bool:
        return False

    def mark_seen(self, domain: str, score: int) -> None:
        pass

    def close(self) -> None:
        pass
