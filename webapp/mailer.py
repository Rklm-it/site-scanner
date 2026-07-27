"""Отправка писем через SMTP собственного ящика пользователя.

Осознанно НЕ делаем «залповую» рассылку: холодная рассылка большими
пачками с личного ящика = мгновенный бан и спам-листы. Шлём по одному,
с паузой и дневным лимитом.
"""

from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

# Разумные потолки, чтобы не сжечь ящик
DEFAULT_DELAY = 45          # секунд между письмами
DEFAULT_DAILY_CAP = 40      # писем за один запуск рассылки


def smtp_config() -> dict:
    return {
        "host": os.environ.get("SMTP_HOST", "").strip(),
        "port": int(os.environ.get("SMTP_PORT", "465") or 465),
        "user": os.environ.get("SMTP_USER", "").strip(),
        "password": os.environ.get("SMTP_PASSWORD", ""),
        "from_name": os.environ.get("SMTP_FROM_NAME", "").strip(),
    }


def is_configured() -> bool:
    c = smtp_config()
    return bool(c["host"] and c["user"] and c["password"])


def send_email(to: str, subject: str, body: str, *, cfg: dict | None = None,
               smtp_factory=None) -> None:
    """Отправляет одно письмо. Бросает исключение при ошибке.

    ``smtp_factory`` — для тестов (подменить smtplib.SMTP_SSL).
    """
    cfg = cfg or smtp_config()
    if not (cfg["host"] and cfg["user"] and cfg["password"]):
        raise RuntimeError("SMTP не настроен: заполните хост, логин и пароль.")
    if not to or "@" not in to:
        raise ValueError("Некорректный адрес получателя.")

    msg = EmailMessage()
    msg["From"] = f'{cfg["from_name"]} <{cfg["user"]}>' if cfg["from_name"] else cfg["user"]
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if smtp_factory is not None:
        server = smtp_factory(cfg["host"], cfg["port"])
    else:
        server = smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=ssl.create_default_context(), timeout=30)
    try:
        server.login(cfg["user"], cfg["password"])
        server.send_message(msg)
    finally:
        try:
            server.quit()
        except Exception:  # noqa: BLE001
            pass
