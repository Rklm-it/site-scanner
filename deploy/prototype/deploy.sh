#!/usr/bin/env bash
#
# Развернуть прототип клиента на своём сервере.
#
#   deploy/prototype/deploy.sh projekt-doma https://github.com/Rklm-it/project-house-design.git
#
# Скрипт клонирует (или обновляет) репозиторий прототипа, собирает образ и
# перезапускает контейнер в сети, где живёт Caddy. Дальше остаётся один раз
# дописать блок в Caddyfile — как именно, написано в README рядом.
#
# Почему отдельным скриптом, а не через docker compose: прототипов будет
# много, по одному на клиента, и каждый живёт в своём репозитории. Плодить
# сервисы в общем docker-compose.yml значит на каждого клиента править файл,
# который отвечает за боевой сканер. Один скрипт с параметром безопаснее.

set -euo pipefail

NAME="${1:-}"
REPO="${2:-}"
BRANCH="${3:-main}"
# Сеть compose-проекта сканера: имя папки + _default. Переименуете каталог —
# поменяется и оно, как и имя тома (об этом же предупреждает CLAUDE.md).
NETWORK="${PROTO_NETWORK:-site-scanner-main_default}"
WORKDIR="${PROTO_DIR:-/root/prototypes}"

if [[ -z "$NAME" || -z "$REPO" ]]; then
    echo "Использование: $0 <имя> <git-url> [ветка]" >&2
    echo "Пример: $0 projekt-doma https://github.com/Rklm-it/project-house-design.git" >&2
    exit 1
fi

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$WORKDIR/$NAME"
IMAGE="proto-$NAME"

echo "==> Исходники: $SRC"
mkdir -p "$WORKDIR"
if [[ -d "$SRC/.git" ]]; then
    git -C "$SRC" fetch --quiet origin "$BRANCH"
    # Прототип правится в Lovable, локальных изменений здесь быть не должно:
    # берём ровно то, что в ветке, без попыток слить.
    git -C "$SRC" reset --hard "origin/$BRANCH"
else
    git clone --branch "$BRANCH" --depth 1 "$REPO" "$SRC"
fi
echo "    коммит: $(git -C "$SRC" log --oneline -1)"

echo "==> Сборка образа $IMAGE"
docker build -t "$IMAGE" -f "$HERE/Dockerfile" "$SRC"

echo "==> Перезапуск контейнера $IMAGE"
docker rm -f "$IMAGE" >/dev/null 2>&1 || true
docker run -d --name "$IMAGE" --restart unless-stopped --network "$NETWORK" "$IMAGE"

echo "==> Проверка"
for i in $(seq 1 15); do
    if docker exec "$IMAGE" node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))" 2>/dev/null; then
        echo "    отвечает"
        echo
        echo "Готово. Контейнер «$IMAGE» доступен внутри сети как $IMAGE:3000."
        echo "Осталось добавить блок в Caddyfile — см. deploy/prototype/README.md"
        exit 0
    fi
    sleep 2
done

echo "    НЕ отвечает. Логи:" >&2
docker logs --tail 30 "$IMAGE" >&2
exit 1
