"""Вежливое поведение: robots.txt и ограничение частоты запросов на домен."""

from __future__ import annotations

import threading
import time
import urllib.robotparser
from urllib.parse import urlparse

import requests

from .fetcher import USER_AGENT


class Politeness:
    """Кэширует robots.txt по хостам и держит минимальный интервал между
    обращениями к одному и тому же домену (потокобезопасно)."""

    def __init__(self, *, respect_robots: bool = True, per_host_delay: float = 1.0):
        self.respect_robots = respect_robots
        self.per_host_delay = per_host_delay
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._last_hit: dict[str, float] = {}
        self._lock = threading.Lock()

    def _robots_for(self, host: str, scheme: str) -> urllib.robotparser.RobotFileParser | None:
        with self._lock:
            if host in self._robots:
                return self._robots[host]
        parser: urllib.robotparser.RobotFileParser | None = None
        try:
            resp = requests.get(
                f"{scheme}://{host}/robots.txt",
                headers={"User-Agent": USER_AGENT},
                timeout=8,
            )
            if resp.status_code < 400 and resp.text:
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(resp.text.splitlines())
        except requests.RequestException:
            parser = None  # нет robots — считаем, что можно
        with self._lock:
            self._robots[host] = parser
        return parser

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parsed = urlparse(url)
        host, scheme = parsed.netloc, parsed.scheme or "https"
        if not host:
            return True
        parser = self._robots_for(host, scheme)
        if parser is None:
            return True
        return parser.can_fetch(USER_AGENT, url)

    def wait(self, url: str) -> None:
        """Выдерживает паузу, чтобы не долбить один домен слишком часто."""
        host = urlparse(url).netloc
        if not host:
            return
        with self._lock:
            last = self._last_hit.get(host, 0.0)
            now = time.monotonic()
            sleep_for = self.per_host_delay - (now - last)
            if sleep_for > 0:
                self._last_hit[host] = now + sleep_for
            else:
                self._last_hit[host] = now
                sleep_for = 0
        if sleep_for > 0:
            time.sleep(sleep_for)
