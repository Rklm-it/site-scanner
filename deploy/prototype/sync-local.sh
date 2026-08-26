#!/usr/bin/env bash
#
# Выложить прототип, собранный кодом в этом же репозитории.
#
#   deploy/prototype/sync-local.sh reklamabataysk clients/reklamabataysk.ru/prototype
#
# Чем отличается от sync.sh. Тот забирает ветку `deploy` из репозитория
# проекта Lovable — там сборка Vite, и её надо где-то собрать. Здесь собирать
# нечего: страница статическая и лежит прямо в репозитории сканера, который на
# этом сервере уже склонирован ради Caddyfile. Значит `git pull` приносит и
# прототип, а скрипту остаётся положить папку туда, откуда её отдаёт Caddy.
#
# Разметку и картинки копируем, служебное — нет: README прототипа объясняет
# устройство нам, а не посетителю, и в вебе ему делать нечего.

set -euo pipefail

NAME="${1:-}"
SRC="${2:-}"
ROOT="${PROTO_ROOT:-/root/prototypes-static}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

if [[ -z "$NAME" || -z "$SRC" ]]; then
    echo "Использование: $0 <имя> <путь к папке прототипа в репозитории>" >&2
    echo "Пример: $0 reklamabataysk clients/reklamabataysk.ru/prototype" >&2
    exit 1
fi

[[ "$SRC" = /* ]] || SRC="$REPO_ROOT/$SRC"

if [[ ! -f "$SRC/index.html" ]]; then
    echo "В $SRC нет index.html — это не прототип." >&2
    exit 1
fi

DEST="$ROOT/$NAME"
mkdir -p "$DEST"

echo "==> Копирую $SRC в $DEST"
# --delete: папка на сервере должна быть точной копией, иначе удалённая
# картинка продолжит отдаваться и прототип будет врать.
rsync -a --delete --exclude='*.md' --exclude='.git' "$SRC/" "$DEST/"

echo "    файлов: $(find "$DEST" -type f | wc -l), объём: $(du -sh "$DEST" | cut -f1)"
echo "    коммит: $(git -C "$REPO_ROOT" log --oneline -1)"
echo
echo "Готово. Caddy отдаёт это из /srv/$NAME, перечитывать его не нужно."
echo "Если домен добавлен только что — docker compose up -d --force-recreate caddy"
