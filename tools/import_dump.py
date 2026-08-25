#!/usr/bin/env python3
"""Приём чужой выгрузки сайта в репозиторий: архив → clients/<домен>/full/.

Зачем отдельный приёмник, если есть вкладка «📦 Выгрузки». Сайт не всегда
снимаем мы: у клиента бывает архив от прошлого подрядчика, экспорт из
конструктора или папка, скачанная чем-то вроде HTTrack. Разбор такой папки
упирается в три одинаковые вещи, и каждый раз в одни и те же:

* `manifest.json` в ней отсутствует, а разбор по СХЕМА.md начинается именно с
  него — карта страниц с заголовками и описаниями, по ней сразу видно, что
  живое, а что дубль. Без карты новая сессия читает сорок файлов подряд;
* старые сайты рунета лежат в windows-1251, и в репозитории такой файл
  читается мусором. Ровно та же беда, из-за которой в mirror.py появился
  свой декодер: тексты клиента — это то, ради чего выгрузка и делается;
* внутри лежит тяжёлое (PDF-прайсы, шрифты, видео), которое всё равно
  отсеет .gitignore. Молча — и потом непонятно, потерялось оно или его не было.

Порядок определения кодировки повторяет `mirror._decode_page` — намеренно, не
из лени: автодетектор врёт на коротких страницах (карточка «Дом 1» приезжала
как «ﾄ黑 1»), и второй разной логики на один и тот же случай в проекте быть
не должно. Сам mirror сюда не импортируется: скрипт должен запускаться
системным python3 на маке владельца, без venv, requests и bs4.

Запуск:

    python3 tools/import_dump.py ~/Downloads/sait-druga.zip drug-domain.ru

Дальше — `git add clients/<домен> && git commit && git push`, и выгрузку
видит новая сессия.
"""

from __future__ import annotations

import argparse
import hashlib
import html as html_mod
import json
import re
import shutil
import sys
import tarfile
import tempfile
import time
import zipfile
from pathlib import Path

# Списки намеренно совпадают с mirror.py и с правилами clients/** в .gitignore:
# принять то, что потом всё равно не закоммитить, — худший из исходов, потому
# что обнаруживается это уже после `git push`.
SKIP_EXT = {
    ".zip", ".rar", ".7z", ".gz", ".tar", ".pdf", ".doc", ".docx", ".xls",
    ".xlsx", ".ppt", ".pptx", ".mp4", ".avi", ".mov", ".wmv", ".mkv", ".mp3",
    ".wav", ".exe", ".msi", ".apk", ".iso", ".dmg", ".woff", ".woff2", ".ttf",
    ".eot", ".otf",
}
PAGE_EXT = {".html", ".htm", ".xhtml", ".php", ".asp", ".aspx", ".jsp", ".shtml"}
ASSET_EXT = {
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".ico", ".bmp",
    ".css", ".js", ".json", ".xml", ".txt", ".map",
}
# Мусор упаковщиков: в macOS-архиве это половина файлов, и все пустые.
JUNK = re.compile(r"(^|/)(__MACOSX|\.DS_Store|Thumbs\.db|\.git|\.svn)(/|$)")

_META_CHARSET = re.compile(rb"""charset=["']?([\w\-]+)""", re.I)
_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.I | re.S)
_META_TAG = re.compile(r"<meta\s+[^>]*>", re.I)
_ATTR = re.compile(r"""(\w[\w:-]*)\s*=\s*("([^"]*)"|'([^']*)'|([^\s>]+))""")
_TAG = re.compile(r"<[^>]+>")
_SCRIPTS = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
# Признаки сборки на скриптах: разметка приезжает пустой оболочкой, и разбирать
# в ней нечего — об этом надо сказать сразу, а не после часа чтения файлов.
JS_SHELL = {
    "__NEXT_DATA__": "Next.js",
    "data-reactroot": "React",
    "window.wixapps": "Wix",
    "ng-version": "Angular",
    "id=\"__nuxt\"": "Nuxt",
    "data-server-rendered": "Vue",
}


def decode_page(raw: bytes, learned: str | None) -> tuple[str, str]:
    """HTML → текст. Возвращает (текст, применённая кодировка).

    Порядок как в mirror._decode_page: объявление в самом файле → строгий
    utf-8 (он сам себе проверка — байты 1251 в валидный utf-8 почти не
    складываются) → кодировка, уже опознанная на этом сайте → windows-1251
    последним, потому что он декодирует что угодно и без ошибки.
    """
    m = _META_CHARSET.search(raw[:4096])
    if m:
        enc = m.group(1).decode("ascii", errors="ignore")
        try:
            return raw.decode(enc), enc.lower()
        except (UnicodeDecodeError, LookupError):
            pass
    try:
        return raw.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        pass
    for enc in (learned, "windows-1251"):
        if not enc or enc == "utf-8":
            continue
        try:
            return raw.decode(enc), enc
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace"), "utf-8"


def retag_charset(text: str) -> str:
    """Переписать объявление кодировки на utf-8.

    Файл на диске уже перекодирован, а объявление внутри осталось прежним —
    браузер поверит объявлению и покажет мусор. mirror.py этого не делает
    (его выгрузки читает сессия, а не человек в браузере), но чужой дамп
    владелец открывает двойным щелчком, чтобы просто посмотреть сайт.
    """
    head, tail = text[:4096], text[4096:]
    head = re.sub(r"""(charset=["']?)([\w\-]+)""", r"\1utf-8", head, count=2,
                  flags=re.I)
    return head + tail


def attrs(tag: str) -> dict:
    out = {}
    for m in _ATTR.finditer(tag):
        out[m.group(1).lower()] = (m.group(3) or m.group(4) or m.group(5) or "")
    return out


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", html_mod.unescape(_TAG.sub(" ", text))).strip()


def page_facts(text: str) -> dict:
    """Заголовок, h1, description и объём видимого текста — поля manifest.json."""
    title = _TITLE.search(text)
    h1 = _H1.search(text)
    desc = ""
    for tag in _META_TAG.findall(text[:8192]):
        a = attrs(tag)
        if a.get("name", "").lower() == "description":
            desc = html_mod.unescape(a.get("content", ""))
            break
    body = clean(_SCRIPTS.sub(" ", text))
    return {
        "title": clean(title.group(1))[:200] if title else "",
        "h1": clean(h1.group(1))[:200] if h1 else "",
        "description": desc[:300],
        "text_len": len(body),
    }


def unpack(src: Path, work: Path) -> Path:
    """Архив или папка → папка с файлами. Пути из архива чистятся от `..`:
    чужой архив разворачивается в чужом каталоге, и запись выше папки
    назначения — это не гипотетическая, а известная дыра упаковщиков."""
    if src.is_dir():
        return src
    dest = work / "unpacked"
    dest.mkdir()
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as zf:
            for info in zf.infolist():
                name = info.filename.replace("\\", "/")
                parts = [p for p in name.split("/") if p not in ("", ".", "..")]
                if not parts or info.is_dir():
                    continue
                out = dest.joinpath(*parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(info) as fh, open(out, "wb") as w:
                    shutil.copyfileobj(fh, w)
        return dest
    if tarfile.is_tarfile(src):
        with tarfile.open(src) as tf:
            for member in tf.getmembers():
                if not member.isfile():
                    continue
                parts = [p for p in member.name.split("/")
                         if p not in ("", ".", "..")]
                if not parts:
                    continue
                out = dest.joinpath(*parts)
                out.parent.mkdir(parents=True, exist_ok=True)
                fh = tf.extractfile(member)
                if fh is None:
                    continue
                with fh, open(out, "wb") as w:
                    shutil.copyfileobj(fh, w)
        return dest
    sys.exit(f"Не понимаю формат: {src.name}. Нужен zip, tar.gz или папка.")


def find_root(base: Path) -> Path:
    """Где в распакованном лежит собственно сайт.

    Упаковщики оборачивают всё в одну-две папки («Архив/сайт/…»), а иногда
    рядом кладут readme и логи. Корнем считаем каталог, в котором лежит
    index-страница; если такого нет — самый населённый html-ом.
    """
    pages = [p for p in base.rglob("*")
             if p.is_file() and p.suffix.lower() in PAGE_EXT
             and not JUNK.search(p.as_posix())]
    if not pages:
        return base
    index = sorted((p for p in pages if p.stem.lower() == "index"),
                   key=lambda p: len(p.relative_to(base).parts))
    if index:
        return index[0].parent
    counts: dict = {}
    for p in pages:
        counts[p.parent] = counts.get(p.parent, 0) + 1
    return max(counts, key=lambda d: (counts[d], -len(d.parts)))


def url_for(domain: str, rel: str) -> str:
    """Путь в дампе → адрес на живом сайте. Нужен для мета-тегов и
    переадресаций: старый сайт уже ранжируется, и после переезда сломанные
    адреса стоят клиенту заказов."""
    if rel.lower() in ("index.html", "index.htm", "index.php"):
        return f"https://{domain}/"
    return f"https://{domain}/{rel}"


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Принять чужую выгрузку сайта в clients/<домен>/full/")
    ap.add_argument("source", help="zip, tar.gz или папка с выгрузкой")
    ap.add_argument("domain", help="домен клиента, например drug-domain.ru")
    ap.add_argument("--force", action="store_true",
                    help="перезаписать, если выгрузка уже лежит")
    args = ap.parse_args()

    domain = re.sub(r"^[a-z]+://|/.*$", "", args.domain.strip().lower())
    domain = domain.strip(".")
    if not domain:
        sys.exit("Домен не указан.")

    src = Path(args.source).expanduser()
    if not src.exists():
        sys.exit(f"Не нашёл {src}")

    repo = Path(__file__).resolve().parent.parent
    dest = repo / "clients" / domain / "full"
    if dest.exists() and any(dest.iterdir()) and not args.force:
        sys.exit(f"В {dest.relative_to(repo)} уже что-то лежит. "
                 f"Перезаписать — добавьте --force.")

    work = Path(tempfile.mkdtemp(prefix="import-dump-"))
    try:
        root = find_root(unpack(src, work))
        if dest.exists():
            shutil.rmtree(dest)
        dest.mkdir(parents=True)

        index, encodings, heavy, big, js_shell = [], {}, [], [], {}
        seen_hash: dict = {}
        dupes, assets, total = [], 0, 0
        learned = None

        for path in sorted(root.rglob("*")):
            if not path.is_file() or JUNK.search(path.as_posix()):
                continue
            rel = path.relative_to(root).as_posix()
            ext = path.suffix.lower()
            size = path.stat().st_size

            if ext in SKIP_EXT:
                heavy.append((rel, size))
                continue

            out = dest / rel
            out.parent.mkdir(parents=True, exist_ok=True)

            if ext in PAGE_EXT:
                raw = path.read_bytes()
                text, enc = decode_page(raw, learned)
                if learned is None and enc != "utf-8":
                    learned = enc          # подсказка для коротких страниц
                encodings[enc] = encodings.get(enc, 0) + 1
                text = retag_charset(text)
                # .php/.asp в дампе — это уже готовый HTML, отданный сервером.
                # Расширение оставляем: по нему видно исходную структуру
                # адресов, а она нужна для переадресаций после переезда.
                out.write_bytes(text.encode("utf-8"))
                facts = page_facts(text)
                digest = hashlib.sha1(
                    re.sub(r"\s+", " ", clean(_SCRIPTS.sub(" ", text)))
                    .encode("utf-8")).hexdigest()
                if digest in seen_hash and facts["text_len"] > 200:
                    dupes.append((rel, seen_hash[digest]))
                else:
                    seen_hash[digest] = rel
                for marker, name in JS_SHELL.items():
                    if marker in text:
                        js_shell[name] = js_shell.get(name, 0) + 1
                index.append({
                    "url": url_for(domain, rel),
                    "file": rel,
                    "title": facts["title"],
                    "h1": facts["h1"],
                    "description": facts["description"],
                    "bytes": len(raw),
                    "text_len": facts["text_len"],
                    "encoding": enc,
                })
            else:
                shutil.copy2(path, out)
                if ext in ASSET_EXT or ext == "":
                    assets += 1
                if size > 25 * 1024 * 1024:
                    big.append((rel, size))
            total += out.stat().st_size

        if not index:
            print("⚠️  HTML-страниц в выгрузке нет. Что внутри:")
            kinds: dict = {}
            for p in root.rglob("*"):
                if p.is_file():
                    kinds[p.suffix.lower() or "(без расширения)"] = \
                        kinds.get(p.suffix.lower() or "(без расширения)", 0) + 1
            for k, n in sorted(kinds.items(), key=lambda kv: -kv[1])[:15]:
                print(f"    {k:<20} {n}")
            print("\nПохоже, это не выгрузка сайта, а экспорт чего-то другого "
                  "(база CMS, макеты, бэкап). Скажите, что это, — разберёмся.")

        (dest / "manifest.json").write_text(json.dumps({
            "domain": domain,
            "collected": time.strftime("%Y-%m-%d %H:%M"),
            "pages": len(index),
            "assets": assets,
            "stopped_by": "imported",
            # Откуда пришло — важнее, чем кажется: у выгрузки не нашим движком
            # нет гарантий полноты, и «страниц 12» может значить и маленький
            # сайт, и оборванную закачку. Перед разбором это надо знать.
            "source": {"kind": "import", "archive": src.name},
            "index": index,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        rel_dest = dest.relative_to(repo)
        print(f"\nПринято в {rel_dest}: страниц {len(index)}, "
              f"файлов {assets}, {total / 1048576:.1f} МБ")
        if encodings:
            print("    кодировки:", ", ".join(
                f"{k} — {v}" for k, v in sorted(encodings.items(),
                                                key=lambda kv: -kv[1])))
        if heavy:
            mb = sum(s for _, s in heavy) / 1048576
            print(f"    не взято тяжёлого: {len(heavy)} файлов, {mb:.1f} МБ "
                  f"(их всё равно отсеет .gitignore)")
            for rel, size in sorted(heavy, key=lambda x: -x[1])[:5]:
                print(f"        {rel} — {size / 1048576:.1f} МБ")
        if big:
            print("    ⚠️  крупные файлы, GitHub ругается от 50 МБ:")
            for rel, size in big:
                print(f"        {rel} — {size / 1048576:.1f} МБ")
        if dupes:
            print(f"    дублей по тексту: {len(dupes)} "
                  f"(например {dupes[0][0]} = {dupes[0][1]})")
        if js_shell:
            print("    ⚠️  разметка собрана скриптами: "
                  + ", ".join(f"{k} — {v} стр." for k, v in js_shell.items())
                  + ". Тексты в такой выгрузке могут быть неполными.")
        thin = [p for p in index if p["text_len"] < 400]
        if thin:
            print(f"    пустых или почти пустых страниц: {len(thin)} из "
                  f"{len(index)}")
        notitle = [p for p in index if not p["title"]]
        if notitle:
            print(f"    без <title>: {len(notitle)}")

        print(f"""
Дальше:

    git add clients/{domain}
    git commit -m "Выгрузка {domain} для разбора: ..."
    git push

И в новой сессии: «Работаем над сайтом клиента {domain}. Возьми скил
lovable-site и иди по нему. Выгрузка в clients/{domain}/full/.»
""")
        return 0
    finally:
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
