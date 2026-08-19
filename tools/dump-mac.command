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
import sys
import time
from pathlib import Path

# Логгеру scanner нужен обработчик, а не только уровень: без него разбор
# прогона уходит в logging.lastResort и виден не будет.
logging.basicConfig(level=logging.INFO, format="%(message)s")

from scanner import mirror

domain = os.environ["DOMAIN"]
dest = Path(os.environ["DEST"])
last = [0.0]


def progress(st):
    now = time.time()
    if now - last[0] < 2:
        return
    last[0] = now
    print(f"  страниц {st.pages}, файлов {st.assets}, {st.bytes / 1048576:.1f} МБ",
          flush=True)


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

if st.pages == 0:
    print("\nНи одной страницы не скачалось.", file=sys.stderr)
    print("Первые ошибки:", file=sys.stderr)
    for line in st.errors[:5]:
        print("  ", line, file=sys.stderr)
    print("\nОткройте сайт в браузере на этой же машине. Если он открывается, "
          "а здесь ноль — площадка отличает браузер от скрипта, и обходом "
          "сайт не взять: содержимое придётся брать из кабинета клиента.",
          file=sys.stderr)
    sys.exit(1)

man = json.loads((dest / "manifest.json").read_text(encoding="utf-8"))
print(f"\nГотово: страниц {st.pages}, файлов {st.assets}, "
      f"{st.bytes / 1048576:.1f} МБ, остановились по причине «{st.stopped_by}».")

if st.stopped_by == "limit":
    print("Упёрлись в потолок — запустите ещё раз, увеличив число страниц.")

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
