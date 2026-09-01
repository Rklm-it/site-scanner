#!/usr/bin/env python3
"""Разбор manifest.json выгрузки textileopt.ru.

Зачем отдельным скриптом: manifest весит мегабайт, руками его не прочитать, а
пересобирать выводы придётся каждой следующей сессии — после дозагрузки
выгрузки цифры поменяются. Печатает то, из чего собраны КАРТА.md и КАТАЛОГ.md.

    python3 clients/textileopt.ru/razbor.py [--tree|--seo|--tovary|--ceny]
"""
import json, re, sys, collections, os
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.abspath(__file__))
M = json.load(open(os.path.join(BASE, 'manifest.json'), encoding='utf-8'))

# www и без www — один и тот же сайт, в выгрузке половина страниц продублирована
seen, PAGES = set(), []
for p in M['index']:
    path = urlparse(p['url']).path
    if path in seen:
        continue
    seen.add(path)
    PAGES.append((path, p))

TOVAR = re.compile(r'/(\d+)/$')
CENY_TSV = os.path.join(BASE, 'ЦЕНЫ.tsv')


def ceny() -> dict:
    """id товара -> цена в рублях, из ЦЕНЫ.tsv.

    Файл снят с выгрузки на сервере: цен в манифесте нет, они внутри HTML.
    Строки страниц-разделов сюда не идут — цена на листинге принадлежит
    первому товару в списке, а не разделу, и «от» из неё не получается:
    на 47 разделах, где есть и листинг, и карточки, она совпала с минимумом
    только в 26.
    """
    out = {}
    if not os.path.exists(CENY_TSV):
        return out
    with open(CENY_TSV, encoding='utf-8') as f:
        for stroka in f:
            chasti = stroka.rstrip('\n').split('\t')
            if len(chasti) < 3:
                continue
            m = re.search(r'/(\d+)\.html$', chasti[0])
            if not m or not chasti[2].strip():
                continue
            try:
                out[m.group(1)] = float(chasti[2].replace(' ', '').replace(',', '.'))
            except ValueError:
                pass
    return out


def razdely():
    """Разделы каталога: путь -> русское название из h1."""
    out = {}
    for path, p in PAGES:
        if not path.startswith('/catalog/') or TOVAR.search(path):
            continue
        if 'filter' in path or path.endswith('.php'):
            continue
        parts = [s for s in path.split('/') if s][1:]
        if parts:
            out['/'.join(parts)] = p['h1'].strip()
    return out


def tovary():
    """Карточки товаров: раздел -> [(id, название)]."""
    out = collections.defaultdict(list)
    for path, p in PAGES:
        m = TOVAR.search(path)
        if not m or not path.startswith('/catalog/'):
            continue
        parts = [s for s in path.split('/') if s][1:-1]
        out['/'.join(parts)].append((m.group(1), p['h1'].strip()))
    return out


def tree():
    r, t = razdely(), tovary()
    for key in sorted(r):
        depth = key.count('/')
        n = len(t.get(key, ()))
        print('  ' * depth + f'- {r[key]}  ({key})' + (f' — {n} карточек в выгрузке' if n else ''))


def seo():
    print('страниц в выгрузке: %d (уникальных адресов %d), файлов %d' % (M['pages'], len(PAGES), M['assets']))
    print('обход остановлен: %s, не добрано страниц %d, файлов %d' % (M['stopped_by'], M['pages_left'], M['assets_left']))
    print('ссылок на картинки в разметке: %d, пропущено: %s' % (M['asset_refs'], M['asset_skipped']))
    dubli = [path for path, p in PAGES if 'filter/clear/apply' in path]
    print('\nмусорных адресов фильтра (/filter/clear/apply): %d' % len(dubli))
    d = collections.Counter(p['description'] for _, p in PAGES)
    print('\nсамые частые description:')
    for k, v in d.most_common(6):
        print('  %3d  %s' % (v, k[:100]))
    t = collections.Counter(p['title'] for path, p in PAGES if TOVAR.search(path))
    print('\nодинаковые title у разных карточек товара:')
    for k, v in t.most_common(6):
        if v > 1:
            print('  %3d  %s' % (v, k[:100]))
    b = sorted(p['bytes'] for _, p in PAGES)
    print('\nвес HTML одной страницы: медиана %d КБ, макс %d КБ' % (b[len(b) // 2] / 1024, b[-1] / 1024))


if __name__ == '__main__':
    what = sys.argv[1] if len(sys.argv) > 1 else '--seo'
    if what == '--tree':
        tree()
    elif what == '--tovary':
        c = ceny()
        for k, v in sorted(tovary().items()):
            for i, name in v:
                print(f'{k}\t{i}\t{name}\t{c.get(i, "")}')
    elif what == '--ceny':
        c, t = ceny(), tovary()
        r = razdely()
        print('товаров с ценой: %d' % len(c))
        for key in sorted(t):
            ceny_razdela = [c[i] for i, _ in t[key] if i in c]
            if ceny_razdela:
                print('%8.2f – %8.2f  (%2d)  %s' % (min(ceny_razdela), max(ceny_razdela),
                                                    len(ceny_razdela), r.get(key, key)))
    else:
        seo()
