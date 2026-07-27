"""Запуск веб-интерфейса: python -m webapp"""

from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8600"))
    print(f"site-scanner UI: http://{host}:{port}")
    uvicorn.run("webapp.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
