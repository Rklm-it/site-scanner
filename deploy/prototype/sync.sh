#!/usr/bin/env bash
#
# Забрать собранный прототип на сервер и отдать его Caddy.
#
#   deploy/prototype/sync.sh projekt-doma https://github.com/Rklm-it/project-house-design.git
#
# Здесь НЕТ сборки, и это главное. VPS владельца — 961 МБ памяти и одно ядро;
# `bun run build` там получает SIGKILL от OOM-killer после ~13 минут свопинга.
# Проверено на двух машинах этого тарифа, обе одинаковые.
#
# Поэтому проект собирается вне сервера, а результат лежит в ветке `deploy`
# того же репозитория: готовая разметка, клиентский бандл, фотографии.
# Скрипт эту ветку просто клонирует. Работы серверу — секунды, памяти — ноль.
#
# Рантайма тоже нет: страница статическая, отдаёт её Caddy. Node не нужен.

set -euo pipefail

NAME="${1:-}"
REPO="${2:-}"
BRANCH="${3:-deploy}"
ROOT="${PROTO_ROOT:-/root/prototypes-static}"

if [[ -z "$NAME" || -z "$REPO" ]]; then
    echo "Использование: $0 <имя> <git-url> [ветка]" >&2
    echo "Пример: $0 projekt-doma https://github.com/Rklm-it/project-house-design.git" >&2
    exit 1
fi

DEST="$ROOT/$NAME"
mkdir -p "$ROOT"

echo "==> Забираю ветку $BRANCH в $DEST"
if [[ -d "$DEST/.git" ]]; then
    git -C "$DEST" fetch --quiet --depth 1 origin "$BRANCH"
    # Ветка сборки перезаписывается принудительным пушем, поэтому сливать
    # нечего: берём ровно то, что на сервере GitHub.
    git -C "$DEST" reset --hard --quiet "origin/$BRANCH"
    git -C "$DEST" clean -qfd
else
    git clone --quiet --branch "$BRANCH" --depth 1 "$REPO" "$DEST"
fi

echo "    коммит: $(git -C "$DEST" log --oneline -1)"

if [[ ! -f "$DEST/index.html" ]]; then
    echo "    В ветке нет index.html — это не собранный прототип." >&2
    exit 1
fi

echo "    файлов: $(find "$DEST" -type f -not -path '*/.git/*' | wc -l), объём: $(du -sh "$DEST" | cut -f1)"
echo
echo "Готово. Caddy отдаёт это из /srv/$NAME — перечитывать его не нужно,"
echo "файлы читаются на каждый запрос. Проверьте адрес в браузере."
