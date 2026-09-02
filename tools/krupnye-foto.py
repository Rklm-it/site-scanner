#!/usr/bin/env python3
"""Самые крупные кадры из выгрузки — чтобы посмотреть их глазами.

`otobrat-foto.py` раскладывает картинки по готовым местам в прототипе и
намертво знает про кухни и гардеробные конкретного клиента. Здесь задача
проще и общая для всех: **из двух тысяч файлов выбрать несколько десятков,
на которые вообще стоит смотреть**, и положить их туда, где их видно —
в репозиторий клиента.

Признак один и он решающий: **размер кадра в пикселях**. Вес не отличает
фотографию от нарисованной иконки, обе по 40 КБ, а размер отличает: логотипы,
кнопки и значки редко бывают шире 500 px, фотографии редко бывают уже.
Заголовки читаются без Pillow — его в контейнере нет.

Отсеиваются заодно:

- кадры уже `--min-shirina` (по умолчанию 700) — это иконки и миниатюры;
- почти квадратные и полосатые пропорции вне 0.4–2.6 — баннеры и разделители;
- имена со словами из `NE_FOTO` — они называют брак сами.

Дубли по содержимому убираются по хешу: на сайтах один и тот же кадр лежит
под десятком имён, и без этого половина отбора — одно и то же фото.

    # на сервере сканера, из /root/site-scanner-main
    docker compose exec -T app python - /data/razbor/<тег> /data/razbor/otbor --skolko 40 \
        < tools/krupnye-foto.py

    # или по распакованной папке локально
    python3 tools/krupnye-foto.py clients/домен/full clients/домен/фото --skolko 24
"""

from __future__ import annotations

import hashlib
import shutil
import struct
import sys
from pathlib import Path

_SOF = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}

# Слова, которыми называют не-фотографии. Сравниваем по кускам имени, а не
# вхождением подстроки: короткий маркер внутри слова ловит невиновных.
NE_FOTO = {
    "logo", "logotip", "icon", "ico", "sprite", "bg", "fon", "banner", "baner",
    "btn", "button", "arrow", "strelka", "placeholder", "noimage", "no-photo",
    "favicon", "loader", "spinner", "sert", "shema", "schema", "skhema",
    "payment", "oplata", "dostavka", "social", "vk", "whatsapp", "telegram",
}


def razmer_jpeg(nachalo: bytes) -> tuple[int, int]:
    """(ширина, высота) из заголовка JPEG или (0, 0)."""
    if not nachalo.startswith(b"\xff\xd8"):
        return 0, 0
    i = 2
    while i + 9 < len(nachalo):
        if nachalo[i] != 0xFF:
            i += 1
            continue
        marker = nachalo[i + 1]
        if marker in _SOF:
            h, w = struct.unpack(">HH", nachalo[i + 5:i + 9])
            return w, h
        if marker in (0xD8, 0xD9, 0xFF) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        dlina = struct.unpack(">H", nachalo[i + 2:i + 4])[0]
        if dlina < 2:
            return 0, 0
        i += 2 + dlina
    return 0, 0


def razmer_png(nachalo: bytes) -> tuple[int, int]:
    if nachalo[:8] != b"\x89PNG\r\n\x1a\n" or nachalo[12:16] != b"IHDR":
        return 0, 0
    return struct.unpack(">II", nachalo[16:24])


def razmer_webp(nachalo: bytes) -> tuple[int, int]:
    if nachalo[:4] != b"RIFF" or nachalo[8:12] != b"WEBP":
        return 0, 0
    vid = nachalo[12:16]
    try:
        if vid == b"VP8X":
            w = int.from_bytes(nachalo[24:27], "little") + 1
            h = int.from_bytes(nachalo[27:30], "little") + 1
            return w, h
        if vid == b"VP8 ":
            return (struct.unpack("<H", nachalo[26:28])[0] & 0x3FFF,
                    struct.unpack("<H", nachalo[28:30])[0] & 0x3FFF)
        if vid == b"VP8L":
            b = int.from_bytes(nachalo[21:25], "little")
            return (b & 0x3FFF) + 1, ((b >> 14) & 0x3FFF) + 1
    except (struct.error, IndexError):
        pass
    return 0, 0


def razmer(put: Path) -> tuple[int, int]:
    try:
        with put.open("rb") as f:
            nachalo = f.read(65536)
    except OSError:
        return 0, 0
    for f in (razmer_jpeg, razmer_png, razmer_webp):
        w, h = f(nachalo)
        if w and h:
            return w, h
    return 0, 0


def imya_brakovannoe(imya: str) -> bool:
    kuski = set()
    for kusok in imya.lower().replace(".", "-").replace("_", "-").split("-"):
        if kusok:
            kuski.add(kusok)
    return bool(kuski & NE_FOTO)


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) < 2:
        sys.exit(__doc__)
    otkuda, kuda = Path(args[0]), Path(args[1])
    skolko = 24
    min_shirina = 700
    for klyuch, znachenie in (("--skolko", "skolko"), ("--min-shirina", "min_shirina")):
        if klyuch in argv:
            znach = int(argv[argv.index(klyuch) + 1])
            if znachenie == "skolko":
                skolko = znach
            else:
                min_shirina = znach

    kadry = []
    vsego = 0
    for put in sorted(otkuda.rglob("*")):
        if not put.is_file() or put.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        vsego += 1
        if imya_brakovannoe(put.name):
            continue
        w, h = razmer(put)
        if not w or w < min_shirina:
            continue
        proporcii = w / h
        if not 0.4 <= proporcii <= 2.6:
            continue
        kadry.append((w * h, w, h, put))

    kadry.sort(reverse=True)
    kuda.mkdir(parents=True, exist_ok=True)
    vzyato, heshi = 0, set()
    print(f"файлов всего {vsego}, прошло отбор {len(kadry)}")
    for pikseli, w, h, put in kadry:
        if vzyato >= skolko:
            break
        # Один и тот же кадр на сайте лежит под несколькими именами; без
        # проверки по содержимому отбор наполовину состоит из повторов.
        hesh = hashlib.md5(put.read_bytes()).hexdigest()
        if hesh in heshi:
            continue
        heshi.add(hesh)
        vzyato += 1
        cel = kuda / f"{vzyato:02d}-{w}x{h}-{put.name}"
        shutil.copy2(put, cel)
        print(f"  {w}×{h}  {put.name}")
    print(f"скопировано {vzyato} в {kuda}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
