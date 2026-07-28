# Образ site-scanner (движок + веб-интерфейс).
FROM python:3.12-slim

WORKDIR /app

# Зависимости ставим отдельным слоем — кэшируется между сборками
COPY requirements.txt requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-web.txt

# Chromium для скриншотов сайтов + системные зависимости.
# Ставится под root до переключения на пользователя app; браузер лежит в
# общем пути и доступен app-пользователю.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/pw-browsers
RUN playwright install --with-deps chromium

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
