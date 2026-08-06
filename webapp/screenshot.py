"""Снимок главной страницы сайта (headless Chromium через Playwright).

Ленивый: снимается по запросу и кэшируется на диск. Чтобы не запускать
десяток браузеров разом, захват сериализован локом.
"""

from __future__ import annotations

import os
import threading
from pathlib import Path

_LOCK = threading.Lock()


def capture(url: str, out_path: str | Path, *, timeout: int = 20000,
            width: int = 1280, height: int = 820, executable_path: str | None = None) -> Path:
    """Снимает верх главной страницы в PNG. Бросает исключение при ошибке.

    ``executable_path`` (или env ``CHROMIUM_PATH``) — путь к бинарю Chromium;
    если не задан, Playwright ищет установленный им браузер.
    """
    from playwright.sync_api import sync_playwright

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    exe = executable_path or os.environ.get("CHROMIUM_PATH") or None

    # Браузер в образе необязателен: если его не поставили (или не смогли —
    # скачивание с CDN Google доступно не отовсюду), говорим об этом прямо,
    # а не роняем пользователя в стектрейс Playwright.
    if exe and not Path(exe).exists():
        raise RuntimeError(
            f"Chromium не найден по пути {exe}. Скриншоты отключены — остальное работает. "
            f"Поставьте браузер в образ или укажите путь в CHROMIUM_PATH."
        )

    with _LOCK:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                args=["--no-sandbox", "--disable-dev-shm-usage"], executable_path=exe)
            try:
                page = browser.new_page(viewport={"width": width, "height": height})
                page.goto(url, timeout=timeout, wait_until="domcontentloaded")
                page.wait_for_timeout(1500)
                page.screenshot(path=str(out), clip={"x": 0, "y": 0, "width": width, "height": height})
            finally:
                browser.close()
    return out
