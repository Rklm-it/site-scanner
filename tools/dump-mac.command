#!/usr/bin/env bash
#
# Выгрузка сайта клиента с компьютера владельца (macOS).
#
# Зачем отдельный скрипт, если в интерфейсе есть кнопка «📦 Выгрузки».
# Некоторые площадки режут адреса дата-центров: rgz61.ru на конструкторе
# «Пульс цен» отдаёт серверу 503 «Проверка безопасности» на все адреса, а в
# браузере владельца тот же сайт открывается спокойно. Обойти проверку мы не
# беремся (чужая защита, ломается на первом их обновлении) — снимаем сайт с
# той машины, которой он виден.
#
# Движок тот же самый, `scanner/mirror.py`: кодировки, отсев тяжёлого и лент,
# картинки из CSS, manifest.json на выходе — всё как у серверной выгрузки.
#
# Запуск:
#   ./tools/dump-mac.command rgz61.ru        # или двойным щелчком в Finder
#   ./tools/dump-mac.command rgz61.ru 400 5  # страниц, глубина
#
# Результат ложится сразу в clients/<домен>/full/ — распаковывать нечего.
#
set -euo pipefail

cd "$(dirname "$0")/.."          # корень репозитория, откуда бы ни запустили

DOMAIN="${1:-}"
PAGES="${2:-400}"
DEPTH="${3:-5}"

if [ -z "$DOMAIN" ]; then
    printf 'Домен сайта клиента (например rgz61.ru): '
    read -r DOMAIN
fi

# Адрес можно вставлять целиком — лишнее отрежется, как в веб-форме.
DOMAIN="$(printf '%s' "$DOMAIN" \
    | tr 'A-Z' 'a-z' \
    | sed -E 's#^[a-z]+://##; s#/.*$##; s/^\.+//; s/\.+$//')"

if [ -z "$DOMAIN" ]; then
    echo "Домен не указан." >&2
    exit 1
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Нужен Python 3. Поставьте его командой:  xcode-select --install" >&2
    echo "(или скачайте с python.org и запустите скрипт заново)" >&2
    exit 1
fi

# Окружение держим в .venv рядом с репозиторием: он уже в .gitignore, и
# системный Python на маке трогать не надо — Apple его иногда обновляет
# сама, а сломанные зависимости потом ищутся полдня.
if [ ! -d .venv ]; then
    echo "Готовлю окружение (один раз, займёт минуту)…"
    python3 -m venv .venv
fi
./.venv/bin/python -m pip install --quiet --upgrade pip
./.venv/bin/python -m pip install --quiet -r requirements.txt

DEST="clients/$DOMAIN/full"
if [ -d "$DEST" ] && [ -n "$(ls -A "$DEST" 2>/dev/null || true)" ]; then
    echo "В $DEST уже что-то лежит — прошлая выгрузка."
    printf 'Перезаписать? [y/N]: '
    read -r ANSWER
    case "$ANSWER" in
        y|Y|д|Д) rm -rf "$DEST" ;;
        *) echo "Отменено."; exit 1 ;;
    esac
fi

# robots.txt по умолчанию НЕ уважаем: скрипт для сайта клиента, который сам
# заказал переделку, а robots на конструкторах и Joomla закрывает как раз
# папки со стилями и картинками. Уважать — ROBOTS=1 перед командой.
ROBOTS="${ROBOTS:-0}"

echo
echo "Качаю $DOMAIN → $DEST (страниц до $PAGES, глубина $DEPTH)"
echo

DOMAIN="$DOMAIN" DEST="$DEST" PAGES="$PAGES" DEPTH="$DEPTH" ROBOTS="$ROBOTS" \
./.venv/bin/python - <<'PY'
import json
import logging
import os
import re
import sys
import threading
import time
from pathlib import Path

# Логгеру scanner нужен обработчик, а не только уровень: без него разбор
# прогона уходит в logging.lastResort и виден не будет.
logging.basicConfig(level=logging.INFO, format="%(message)s")

import requests

from scanner import mirror
from scanner.fetcher import DEFAULT_HEADERS

domain = os.environ["DOMAIN"]
dest = Path(os.environ["DEST"])
started = time.time()

# Проверка до обхода: отдаёт ли сайт страницы этой машине. Без неё выгрузка
# сайта, закрытого антиботом, десять минут молча перебирает адреса и
# заканчивается пустотой — ровно это и случилось на rgz61.ru.
print("Проверяю, что сайт отвечает…")
session = requests.Session()
try:
    # Схему выбираем так же, как обход: https с откатом на http. Иначе на
    # сайте без https проверка пугает ошибкой сертификата, а выгрузка при
    # этом отработает нормально.
    root = mirror._pick_root(domain, session, 20)
    probe = session.get(root, headers=DEFAULT_HEADERS,
                        timeout=20, allow_redirects=True)
    # Через тот же декодер, что и выгрузка: requests без объявления charset
    # считает страницу latin-1, и русский заголовок приезжает кракозябрами.
    text, _ = mirror._decode_page(probe.content,
                                  probe.headers.get("content-type", ""), None)
    title = re.search(r"<title[^>]*>(.*?)</title>", text, re.S | re.I)
    print(f"  ответ {probe.status_code} · {probe.headers.get('content-type', '?')} "
          f"· {len(probe.content)} байт · {probe.url}")
    if title:
        print(f"  заголовок: {title.group(1).strip()[:100]}")
    if probe.status_code >= 400:
        print("  Сайт отвечает отказом уже на главной — выгрузка, скорее всего,")
        print("  окажется пустой. Прервать: Ctrl+C.")
except Exception as exc:  # noqa: BLE001
    print(f"  не отвечает: {type(exc).__name__}: {exc}")
print()


def summary(st) -> str:
    codes = ", ".join(f"{code}×{n}" for code, n in sorted(st.statuses.items()))
    return (f"  {int(time.time() - started):>4}с · страниц {st.pages}, "
            f"файлов {st.assets}, {st.bytes / 1048576:.1f} МБ · "
            f"пропущено {st.skipped}, ошибок {len(st.errors)}"
            + (f" · ответы: {codes}" if codes else ""))


state = {"stats": None, "printed": 0.0}


def progress(st) -> None:
    state["stats"] = st
    now = time.time()
    if now - state["printed"] < 3:
        return
    state["printed"] = now
    print(summary(st), flush=True)


# Сторож на случай тишины: обход может минутами ждать таймаутов, и без него
# экран замирает — непонятно, работает скрипт или повис.
finished = threading.Event()


def watchdog() -> None:
    while not finished.wait(15):
        if time.time() - state["printed"] < 15:
            continue
        state["printed"] = time.time()
        st = state["stats"]
        if st is None:
            print(f"  {int(time.time() - started):>4}с · ответов пока нет, ждём сайт",
                  flush=True)
        else:
            print(summary(st), flush=True)


threading.Thread(target=watchdog, daemon=True).start()

try:
    st = mirror.run(
        domain, dest,
        max_pages=int(os.environ["PAGES"]),
        max_depth=int(os.environ["DEPTH"]),
        respect_robots=os.environ["ROBOTS"] == "1",
        # Бюджет больше серверного: здесь никто не ждёт ответа в браузере, а
        # сайт на 400 страниц с паузами между запросами в семь минут не влезет.
        time_budget=1800.0,
        on_progress=progress,
    )
except KeyboardInterrupt:
    print(f"\nПрервано. Скачанное осталось в {dest}, но без manifest.json —")
    print("для разбора запустите выгрузку заново.")
    sys.exit(130)
finally:
    finished.set()

if st.pages == 0:
    print("\nНи одной страницы не скачалось.", file=sys.stderr)
    if st.statuses:
        codes = ", ".join(f"{code}×{n}" for code, n in sorted(st.statuses.items()))
        print(f"Сайт отвечал так: {codes}", file=sys.stderr)
    for line in st.errors[:5]:
        print("  ", line, file=sys.stderr)
    if any(code >= 400 for code in st.statuses):
        print("\nСайт отвечает, но отдаёт отказы — значит площадка отличает браузер",
              file=sys.stderr)
        print("от скрипта и на этой машине тоже. Обходом сайт не взять:",
              file=sys.stderr)
        print("содержимое придётся брать из кабинета клиента.", file=sys.stderr)
    else:
        print("\nОткройте сайт в браузере на этой же машине. Не открывается —",
              file=sys.stderr)
        print("дело не в скрипте.", file=sys.stderr)
    sys.exit(1)

man = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
print(f"\nГотово: страниц {st.pages}, файлов {st.assets}, "
      f"{st.bytes / 1048576:.1f} МБ, остановились по причине «{st.stopped_by}».")

if st.stopped_by == "limit":
    print("Упёрлись в потолок — запустите ещё раз, увеличив число страниц.")
elif st.stopped_by == "deadline":
    print("Кончился бюджет времени — часть страниц не скачана, запустите ещё раз.")

print("\nПервые страницы из карты сайта:")
for page in man["index"][:10]:
    print(f"  {page['url']}\n    {page['title'][:90]}")

if st.errors:
    print(f"\nОшибок по дороге: {len(st.errors)} (первые три)")
    for line in st.errors[:3]:
        print("  ", line)
PY

echo
echo "Проверьте, что внутри — отсев служебных путей работает по списку"
echo "известных CMS, а самописные админки называются как попало:"
echo "  open $DEST"
echo
echo "Дальше в репозиторий:"
echo "  git add $DEST"
echo "  git commit -m 'Выгрузка $DOMAIN для разбора: <что за сайт, что проверено>'"
echo "  git push"
