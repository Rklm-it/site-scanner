"""Срез базы лидов для разбора в сессии: кому звонить.

Запускается на сервере владельца, потому что база живёт на docker-томе:

    docker compose exec -T app python - < clients/выборка.py

Скрипт скармливается питону через stdin намеренно. В образ копируются только
``scanner/`` и ``webapp/`` (см. Dockerfile), каталога ``clients/`` внутри
контейнера нет, а бинд-монта репозитория тоже нет. Через stdin достаточно
``git pull`` на хосте — пересобирать образ не нужно.

Чем отличается от команды в ``README.md``: та печатает первые 50 строк по
баллу «как есть». По такому списку звонить нельзя — половина строк отваливается
на первом же взгляде (нет телефона, сайт свежий, уже отказали). Здесь мусор
отсеивается до печати, а причины отсева выводятся числами: по ним видно, надо
ли гнать новый скан и по каким запросам.

Аргументы (необязательные):
    --limit N        сколько строк печатать, по умолчанию 60
    --min-outdated N нижняя граница балла старости, по умолчанию 40
    --max-outdated N верхняя, по умолчанию 100 (не режем, только помечаем)
    --city ТЕКСТ     оставить только лидов, у которых текст встречается
                     в поисковом запросе или адресе (например: --city Ростов)
"""

from __future__ import annotations

import json
import os
import re
import signal
import sqlite3
import sys

# Вывод почти всегда уходит в head/less/tee — без этого питон валится
# трейсбеком BrokenPipeError вместо тихого выхода.
signal.signal(signal.SIGPIPE, signal.SIG_DFL)

# Статусы, при которых лид в партию не идёт: либо закрыт, либо уже в работе.
# «недозвон» и «перезвонить» — наоборот, звонить надо, они остаются.
CLOSED = {"мусор", "отказ", "клиент", "интерес", "написал", "звонил", "ответили"}

# Подсказка «похоже на интернет-магазин»: переделка от 250к, обычно свой
# подрядчик. Ищем только в заголовке и поисковом запросе — в остальных полях
# слова «товар» и «каталог» приходят из наших же шаблонов письма и брифа,
# и любой лид ложно помечается магазином.
SHOP = re.compile(
    r"интернет-магазин|магазин|купить|каталог товаров|прайс-лист|оптом|доставка по росс",
    re.I)


def arg(name: str, default):
    """Значение аргумента --name, если передан."""
    if name in sys.argv:
        i = sys.argv.index(name)
        if i + 1 < len(sys.argv):
            return sys.argv[i + 1]
    return default


def clean(value, width: int = 0) -> str:
    """Плоская строка без табов и переносов — иначе поедет TSV."""
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:width] if width else text


def db_path() -> str:
    data = os.environ.get("SCANNER_DATA", "/data/webapp_data")
    return os.path.join(data, "leads.sqlite")


def load() -> list[dict]:
    """Лиды из базы со свежим статусом из lead_state.

    Статус берём из ``lead_state``, а не из json лида: в json он записан на
    момент скана и с тех пор мог поменяться руками в интерфейсе.
    """
    path = db_path()
    if not os.path.exists(path):
        # Ошибка почти всегда в SCANNER_DATA, поэтому сразу показываем, что
        # лежит рядом: гадать про путь на чужом сервере дороже.
        near = os.path.dirname(path) or "/"
        listing = os.listdir(near) if os.path.isdir(near) else "каталога нет"
        sys.exit(f"Базы нет: {path}\nВ {near}: {listing}")
    conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=10)
    states = {}
    try:
        for dom, st, note, cb in conn.execute(
                "SELECT domain, status, note, callback FROM lead_state"):
            states[dom] = (st or "", note or "", cb or "")
    except sqlite3.OperationalError:
        pass  # старая база без части колонок — статусы просто не покажем
    rows = []
    for (data,) in conn.execute("SELECT data FROM leads ORDER BY outreach_score DESC"):
        r = json.loads(data)
        st, note, cb = states.get(r.get("domain", ""), ("", "", ""))
        r["_status"], r["_note"], r["_callback"] = st, note, cb
        rows.append(r)
    conn.close()
    return rows


def tech(r: dict) -> str:
    """Технические изъяны одной строкой — из них берётся зацепка для звонка."""
    flags = []
    if r.get("tls_error") == "да":
        flags.append("битый-tls")
    elif r.get("https") != "да":
        flags.append("http")
    if r.get("mobile_friendly") != "да":
        flags.append("неадапт")
    return ",".join(flags)


def main() -> None:
    limit = int(arg("--limit", 60))
    lo = int(arg("--min-outdated", 40))
    hi = int(arg("--max-outdated", 100))
    city = clean(arg("--city", ""))

    rows = load()
    skip = {"уже трогали": 0, "нет телефона": 0, "сайт не старый": 0,
            "балл выше потолка": 0, "не тот город": 0, "ошибка скана": 0}
    touched: list[dict] = []
    good: list[dict] = []

    for r in rows:
        if r.get("error"):
            skip["ошибка скана"] += 1
            continue
        if r["_status"] in CLOSED:
            skip["уже трогали"] += 1
            touched.append(r)
            continue
        if not clean(r.get("phones")):
            skip["нет телефона"] += 1          # звонить нечем — это про обзвон
            continue
        outdated = int(r.get("outdated_score") or 0)
        if outdated < lo:
            skip["сайт не старый"] += 1        # аргумент «у вас старый сайт» не работает
            continue
        if outdated > hi:
            skip["балл выше потолка"] += 1
            continue
        if city and city.lower() not in (clean(r.get("source_query")) + " "
                                         + clean(r.get("address"))).lower():
            skip["не тот город"] += 1
            continue
        good.append(r)

    out = sys.stdout
    print("=== СВОДКА ===", file=out)
    print(f"всего в базе: {len(rows)}", file=out)
    print("отсеяно: " + " | ".join(f"{k} {v}" for k, v in skip.items() if v), file=out)
    print(f"осталось: {len(good)}, показано {min(limit, len(good))} "
          f"(по убыванию аутрич-балла)", file=out)
    print(f"фильтр: балл старости {lo}-{hi}"
          + (f", город: {city}" if city else ""), file=out)

    queries = {}
    for r in good:
        q = clean(r.get("source_query"), 40)
        queries[q] = queries.get(q, 0) + 1
    top = sorted(queries.items(), key=lambda kv: -kv[1])[:10]
    print("запросы, давшие годных: "
          + ", ".join(f"{q} — {n}" for q, n in top if q), file=out)

    cols = ["домен", "тир", "аут", "стар", "ИНН", "компания", "оборот_млн", "форма",
            "орг", "почта", "реклама", "CMS", "год", "тех", "телефон", "магаз",
            "запрос", "сигналы"]
    print("\n=== ЛИДЫ ===", file=out)
    print("\t".join(cols), file=out)

    for r in good[:limit]:
        revenue = r.get("revenue")
        try:
            rev = f"{int(revenue) / 1_000_000:.1f}"
        except (TypeError, ValueError):
            rev = ""
        status = clean(r.get("company_status"), 12).lower()
        title_q = clean(r.get("title")) + " " + clean(r.get("source_query"))
        print("\t".join([
            clean(r.get("domain"), 34),
            clean(r.get("priority"), 1),
            str(r.get("outreach_score") or ""),
            str(r.get("outdated_score") or ""),
            # Пусто = ИНН на сайте не нашёлся, компания подтянута по названию.
            # Тогда оборот и директор могут быть от чужой фирмы — не верить.
            "да" if clean(r.get("inn")) else "",
            clean(r.get("company"), 40),
            rev,
            "ИП" if r.get("is_individual") == "да" else "",
            "действ" if "действ" in status else clean(status, 8),
            "да" if r.get("corp_email") == "да" else "",
            clean(r.get("marketing"), 24),
            clean(r.get("cms"), 20),
            str(r.get("copyright_year") or ""),
            tech(r),
            clean(r.get("phones")).split(",")[0],
            "да" if SHOP.search(title_q) else "",
            clean(r.get("source_query"), 32),
            clean(r.get("signals"), 80),
        ]), file=out)

    if touched:
        print("\n=== УЖЕ ТРОГАЛИ (в партию не идут) ===", file=out)
        for r in touched[:40]:
            print("\t".join([clean(r.get("domain"), 34), r["_status"],
                             clean(r["_callback"], 12), clean(r["_note"], 60)]), file=out)


if __name__ == "__main__":
    main()
