# Образ site-scanner (движок + веб-интерфейс).
FROM python:3.12-slim

WORKDIR /app

# Зависимости ставим отдельным слоем — кэшируется между сборками
COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-web.txt

# Chromium для скриншотов сайтов.
#
# Берём системный пакет Debian, а НЕ `playwright install`: тот качает бинарь с
# CDN Google, который доступен не из каждой сети — и сборка всего образа падала
# из-за необязательной функции. Playwright умеет работать с готовым бинарём
# через executable_path, его подхватывает CHROMIUM_PATH в webapp/screenshot.py.
#
# Шаг намеренно не фатальный: не поставился браузер — образ всё равно собран,
# скан работает, недоступны только скриншоты. Сборка без браузера (легче и
# быстрее): docker compose build --build-arg WITH_SCREENSHOTS=0
ARG WITH_SCREENSHOTS=1
RUN if [ "$WITH_SCREENSHOTS" = "1" ]; then \
      (apt-get update && apt-get install -y --no-install-recommends chromium \
       && rm -rf /var/lib/apt/lists/*) \
      || echo "ВНИМАНИЕ: Chromium не установлен — скриншоты будут недоступны, остальное работает"; \
    fi
ENV CHROMIUM_PATH=/usr/bin/chromium

COPY scanner ./scanner
COPY webapp ./webapp

# Постоянные данные (кэш, ключи, результаты) — на томе /data
ENV HOST=0.0.0.0 \
    PORT=8600 \
    SCANNER_DATA=/data/webapp_data \
    SCANNER_SECRETS=/data/secrets.local.json \
    PYTHONUNBUFFERED=1

RUN useradd -m app && mkdir -p /data && chown app:app /data
USER app
VOLUME /data
EXPOSE 8600

# Проверка живости без curl (в slim его нет)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8600/api/config', timeout=4)" || exit 1

# ВАЖНО: строго один процесс — список задач хранится в памяти процесса
CMD ["python", "-m", "webapp"]
