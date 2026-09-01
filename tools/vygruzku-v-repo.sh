#!/usr/bin/env bash
# Забрать выгрузку из релиза GitHub прямо в репозиторий клиента — одной
# командой на сервере сканера.
#
# Зачем скрипт, если есть vzyat-vygruzku.py: с галочкой «сразу в GitHub» на
# томе не остаётся ничего, части лежат ассетами релиза, и достать их умеет
# только сервер — у сессии api.github.com закрыт («GitHub access is not
# enabled for this session»). Каждый новый клиент упирался в один и тот же
# ручной ряд из пяти шагов: скачать части, распаковать, вынести из
# контейнера, прибрать том, закоммитить. Ряд длинный, а ошибка в середине
# оставляет том забитым — при 533 МБ свободных это ломает и базу лидов.
#
# Выполнять на СЕРВЕРЕ СКАНЕРА, из /root/site-scanner-main.
#
#   ./tools/vygruzku-v-repo.sh kondi-kaluga.ru-2026-09-01-1812 claude/moya-vetka
#   ./tools/vygruzku-v-repo.sh <тег> --manifest      # только карта сайта
#
# Ключи:
#   --manifest      забрать только manifest.json (килобайты) — для сайтов,
#                   которые в репозиторий целиком не кладут
#   --perezapisat   затереть уже лежащую clients/<домен>/full
#   --vsyo-ravno    не смотреть на свободное место на томе
#   --bez-pusha     закоммитить, но не пушить

set -euo pipefail

KOREN="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$KOREN"

teg=""
vetka=""
manifest=0
perezapisat=0
vsyo_ravno=0
bez_pusha=0

for arg in "$@"; do
    case "$arg" in
        --manifest)     manifest=1 ;;
        --perezapisat)  perezapisat=1 ;;
        --vsyo-ravno)   vsyo_ravno=1 ;;
        --bez-pusha)    bez_pusha=1 ;;
        --*)            echo "неизвестный ключ: $arg" >&2; exit 2 ;;
        *)              if [ -z "$teg" ]; then teg="$arg"; else vetka="$arg"; fi ;;
    esac
done

if [ -z "$teg" ]; then
    echo "укажи тег релиза, например kondi-kaluga.ru-2026-09-01-1812" >&2
    echo "список релизов:  docker compose exec -T app python - --spisok < tools/vzyat-vygruzku.py" >&2
    exit 2
fi

if [ ! -f docker-compose.yml ]; then
    echo "здесь нет docker-compose.yml — это не сервер сканера или не тот каталог." >&2
    echo "сканер живёт в /root/site-scanner-main, прототипы — в /root/site-scanner." >&2
    exit 2
fi

# Домен — это часть тега до даты: kondi-kaluga.ru-2026-09-01-1812 → kondi-kaluga.ru
domen="$(printf '%s' "$teg" | sed -E 's/-[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{4}$//')"
kuda="clients/$domen/full"

echo "== выгрузка $teg → $kuda"

# Ветку переключаем ДО скачивания: иначе файлы лягут в рабочий каталог, а
# checkout о них споткнётся. Форма с -B — единственная безопасная: она
# одинаково работает, есть ветка на машине или её тут ещё не было.
if [ -n "$vetka" ]; then
    # Смотрим только на отслеживаемые файлы: неотслеживаемые checkout переносит
    # между ветками как есть и теряет их только если бы затирал. На первом же
    # запуске гвард встал из-за забытого clients/textileopt.ru/ЦЕНЫ.tsv, к
    # переключению ветки отношения не имевшего.
    if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
        echo "в рабочем каталоге есть незакоммиченные правки — разберись с ними," >&2
        echo "иначе переключение ветки их утащит:" >&2
        git status --short --untracked-files=no >&2
        exit 1
    fi
    lishnee="$(git status --porcelain --untracked-files=all | grep '^??' || true)"
    if [ -n "$lishnee" ]; then
        echo "рядом лежат неотслеживаемые файлы, их не трогаю:"
        printf '%s\n' "$lishnee"
    fi
    git fetch origin
    if git rev-parse --verify -q "origin/$vetka" >/dev/null; then
        git checkout -B "$vetka" "origin/$vetka"
    else
        # Ветки на GitHub ещё нет — заводим от текущего коммита, пуш её создаст.
        echo "ветки origin/$vetka нет, завожу от $(git rev-parse --abbrev-ref HEAD)"
        git checkout -B "$vetka"
    fi
fi

if [ -d "$kuda" ] && [ -n "$(ls -A "$kuda" 2>/dev/null)" ] && [ "$perezapisat" = 0 ]; then
    echo "$kuda уже не пустой. Это прошлая выгрузка того же клиента:" >&2
    echo "  перевыгрузка — добавь --perezapisat, разбор старой — переименуй папку." >&2
    exit 1
fi

# Свободное место на томе. Части распаковываются на нём же, и пик — это
# распакованная выгрузка плюс одна качающаяся часть. Тройной запас берём
# потому, что html и css жмутся в разы: 11 МБ архива легко дают 40 на диске.
if [ "$vsyo_ravno" = 0 ] && [ "$manifest" = 0 ]; then
    stroka="$(docker compose exec -T app python - --spisok < tools/vzyat-vygruzku.py \
              | tr -d '\r' | grep -F "$teg " || true)"
    if [ -n "$stroka" ]; then
        echo "релиз: $stroka"
        ves="$(printf '%s' "$stroka" | sed -E 's/.*, ([0-9]+) МБ.*/\1/')"
        svobodno="$(docker compose exec -T app df -Pm /data | tr -d '\r' | awk 'NR==2 {print $4}')"
        echo "на томе свободно ${svobodno} МБ"
        if [ -n "$ves" ] && [ "$svobodno" -lt $((ves * 3)) ]; then
            echo "мало места: под выгрузку в ${ves} МБ нужно примерно $((ves * 3)) МБ." >&2
            echo "чистить так:  docker image prune -f  и удалить старые архивы на томе." >&2
            echo "docker builder prune реального места не даёт — верить df, а не его отчёту." >&2
            echo "забрать только карту сайта:  --manifest" >&2
            exit 1
        fi
    fi
fi

kluchi=()
[ "$manifest" = 1 ] && kluchi+=(--manifest)

docker compose exec -T app python - "$teg" "${kluchi[@]}" < tools/vzyat-vygruzku.py

mkdir -p "clients/$domen"
rm -rf "$kuda"
# docker compose cp с несуществующим приёмником делает его копией папки —
# то есть содержимое релиза оказывается сразу в full/, как и при распаковке
# zip-а руками: manifest.json в корне.
docker compose cp "app:/data/razbor/$teg" "$kuda"

# Том освобождаем сразу: держать выгрузку и там, и в репозитории — ровно та
# беда с диском, от которой всё это и затевалось.
docker compose exec -T app rm -rf "/data/razbor/$teg"

if [ ! -f "$kuda/manifest.json" ]; then
    echo "в выгрузке нет manifest.json — разбирать нечего, проверь тег." >&2
    exit 1
fi

stranic="$(python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['pages'])" \
           "$kuda/manifest.json" 2>/dev/null || echo '?')"
fajlov="$(find "$kuda" -type f | wc -l | tr -d ' ')"
ves="$(du -sh "$kuda" | cut -f1)"
echo "== в репозитории: страниц $stranic, файлов $fajlov, $ves"

git add "clients/$domen"
if git diff --cached --quiet; then
    echo "нечего коммитить: то же самое уже в репозитории."
    exit 0
fi
git commit -q -m "Выгрузка $domen для разбора: страниц $stranic, файлов $fajlov"
echo "== коммит сделан"

if [ "$bez_pusha" = 1 ]; then
    echo "пуш пропущен (--bez-pusha)"
    exit 0
fi

tekushchaya="$(git rev-parse --abbrev-ref HEAD)"
for pauza in 2 4 8 16 0; do
    if git push -u origin "$tekushchaya"; then
        echo "== запушено в $tekushchaya"
        exit 0
    fi
    [ "$pauza" = 0 ] && break
    echo "пуш не прошёл, повтор через ${pauza}с…" >&2
    sleep "$pauza"
done
echo "запушить не удалось — коммит на месте, попробуй git push вручную." >&2
exit 1
