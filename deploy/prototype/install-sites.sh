#!/usr/bin/env bash
#
# Разложить стартовый набор блоков Caddy по каталогу, из которого их читает
# контейнер, и завести каталог под логи. Выполняется на СЕРВЕРЕ ПРОТОТИПОВ:
#
#   cd /root/site-scanner/deploy/prototype && ./install-sites.sh
#
# Идемпотентно и НИЧЕГО НЕ ЗАТИРАЕТ: файл, который уже лежит в /root/caddy-sites,
# остаётся как есть. Это важно, потому что после переезда правда живёт на
# сервере — блоки пишет приложение «Выкладка», а не git. Копия в репозитории
# нужна ровно один раз, при первом разворачивании или на новой машине.

set -euo pipefail

ISHODNIK="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/sites"
SAYTY="${CADDY_SITES_DIR:-/root/caddy-sites}"
LOGI="${CADDY_LOGS_DIR:-/root/caddy-logs}"

mkdir -p "$SAYTY" "$LOGI"

polozheno=0
propushcheno=0
for f in "$ISHODNIK"/*.caddy; do
    [[ -e "$f" ]] || continue
    imya="$(basename "$f")"
    if [[ -e "$SAYTY/$imya" ]]; then
        echo "    уже есть, не трогаю: $imya"
        propushcheno=$((propushcheno + 1))
    else
        cp "$f" "$SAYTY/$imya"
        echo "==> положил: $imya"
        polozheno=$((polozheno + 1))
    fi
done

echo
echo "Положено: $polozheno, пропущено (уже было): $propushcheno"
echo "Блоки сайтов: $SAYTY"
echo "Логи посещений: $LOGI"
echo
echo "Дальше — пересоздать контейнер, чтобы он увидел новые монтирования:"
echo "    docker compose up -d --force-recreate caddy"
echo
echo "Проверить, что конфиг собрался и домены на месте:"
echo "    docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile"
