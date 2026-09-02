#!/usr/bin/env python3
"""Три первых экрана «Текстиль-Сити» одним самодостаточным HTML.

Шаг 2.5 по `/lovable-site`: клиенту показывают **три разных первых экрана**, а
не один «поправим». Разные — значит с разным громким местом, а не три оттенка
одного.

Почему статикой, а не в Stitch: результат Stitch из облачной сессии не
забрать — прокси режет хосты Google, откуда он отдаёт HTML и картинку. Значит
по нему нельзя ни прогнать проверки, ни положить его в репозиторий. Здесь файл
свой: открывается с флешки, уходит клиенту одним вложением, проверяется
скриптами.

Данные — только из выгрузки: названия и ширины тканей из `manifest.json`,
разделы оттуда же, контакты из `ТЕКСТЫ.md`. Ничего не выдумано; цен на экранах
нет намеренно — у клиента на сайте написано «Актуальные цены и наличие по
запросу».

    python3 clients/textileopt.ru/экраны/собрать.py [куда.html]
"""

from __future__ import annotations

import base64
import os
import re
import sys

ЗДЕСЬ = os.path.dirname(os.path.abspath(__file__))

# Названия дословные из manifest.json — вместе с их кривизной, потому что
# клиент узнаёт свои строки, а причёсанное название выдаёт, что писали не с его
# данных. Плотность, состав и артикул НЕ дописываем: показываем ровно то, что
# стоит в названии. Пять товаров подобраны по разбросу ширины: 90–280 см.
ТКАНИ_СЫРЬЁ = [
    'Ткань Брезент СКПВ Ш-90 пл.540гр 511252-СКПВ, м',
    'Бязь суровая Ш-165 пл 120 гр 6165130, м',
    'Ткань Гобелен "Дикая орхидея" цв.1 Ш-200 см пл.325гр 100% пэ Россия 3107431, м',
    'П/лён набивной Ш-220см 30% лён,70% хл.,пл.140 гр "Райский сад синий" Г.-Я. 5220-13341, м',
    'ткань Сатин-страйп полоса 3 см, белый, Ш-280 см',
]


def razobrat(polnoe: str):
    """Название -> (имя до ширины, ширина в см, всё остальное дословно).

    Разрезаем по «Ш-» и ничего не дописываем: если в названии нет плотности,
    её не будет и на экране. Это и есть правило «не выдумывать»: техстрока
    показывает данные клиента, а не наши представления о них.
    """
    m = re.search(r'Ш[-\s]?(\d{2,3})\s*(?:см)?', polnoe)
    shirina = int(m.group(1))
    imya = polnoe[:m.start()].strip(' ,')
    # Из хвоста берём только плотность — она есть не у всех, и если её нет,
    # строка просто короче. Артикул и «, м» на первом экране не нужны и ломали
    # вёрстку: у гобелена хвост длиннее самого названия.
    p = re.search(r'пл\.?\s*(\d+)\s*гр', polnoe)
    plotnost = f'пл. {p.group(1)} г/м²' if p else ''
    return imya, shirina, plotnost


ТКАНИ = [razobrat(n) for n in ТКАНИ_СЫРЬЁ]
# На первом экране показываем три ткани из пяти. Не из вкуса: на 1440×900
# четыре ряда уводили под сгиб кнопку «Запросить прайс», а кнопка на первом
# экране — это то, ради чего он есть. Три оставшиеся дают крайние точки шкалы
# и середину — 90 · 165 · 280, — и приём читается ровно так же.
ПЕРВЫЙ_ЭКРАН = [t for t in ТКАНИ if t[1] in (90, 165, 280)]
# Шкала кончается на 300: самая широкая ткань в выгрузке — 280 см, а риска 325
# налезала на подпись «см» у правого края. Крайние значения каталога (305 и 325)
# встречаются у единиц товаров и шкалу растягивают зря.
ШКАЛА = 300
РИСКИ = [80, 150, 220, 280]

РАЗДЕЛЫ = [
    ("Ткани", "153 подраздела"),
    ("Швейная фурнитура", "80 подразделов"),
    ("Наполнители и утеплители", "15 подразделов"),
    ("Комплектующие для матрасов", "11 подразделов"),
    ("Домашний текстиль", "8 подразделов"),
    ("Швейное оборудование", "8 подразделов"),
    ("Упаковка для текстиля", "7 подразделов"),
    ("Текстиль для отелей", "7 подразделов"),
    ("Текстиль для детских садов", "2 подраздела"),
]

ФАКТЫ = [
    "Работаем с 2009 года",
    "Более 55 000 товаров на складе",
    "Новое поступление каждую неделю",
    "Отгружаем во все регионы России",
]

МЕНЮ = ["Каталог", "Услуги", "Оптовикам", "Доставка", "О компании", "Контакты"]
ТЕЛЕФОН = "+7 (863) 273-23-50"

# Полоса ткани во всю ширину — ответ на то, чего у клиента нет. Кадров склада
# и цеха в выгрузке ноль, а самая крупная картинка вообще 640×480: растянуть
# её на 1440 нельзя, будет каша. Но ткань — это повторяющийся рисунок, и её
# честно класть плиткой: так она и выглядит в рулоне. Кадр настоящий, из их
# же каталога, ничего не додумано и не растянуто.
ФАКТУРА = os.path.join(os.path.dirname(ЗДЕСЬ), "фото",
                       "18-550x366-b0b46df1531be68930c2edb694a493ac.png")


def фактура_base64() -> str:
    """Кадр ткани строкой data:. Файл уходит клиенту одним вложением, поэтому
    картинка вшивается внутрь, а не лежит рядом."""
    try:
        with open(ФАКТУРА, "rb") as f:
            return "data:image/png;base64," + base64.b64encode(f.read()).decode()
    except OSError:
        return ""

СТИЛЬ = """
@import url('https://fonts.googleapis.com/css2?family=Unbounded:wght@400;600&family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;600&display=swap');

:root{
  --fon:#EDE7DA; --tekst:#16181C; --akcent:#6E7A5E; --rasprodazha:#B23A20;
  --belyj:#FFFFFF;
  --zag:'Unbounded','Arial Black','Trebuchet MS',sans-serif;
  --osn:'IBM Plex Sans','Segoe UI',system-ui,sans-serif;
  --mono:'IBM Plex Mono','SFMono-Regular',Consolas,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:#c9c3b6;color:var(--tekst);font-family:var(--osn);
     font-size:18px;line-height:1.55}
.podpis{max-width:1440px;margin:0 auto;padding:48px 40px 16px;font-family:var(--mono);
        font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:#3b3f36}
.podpis b{font-family:var(--osn);font-size:20px;letter-spacing:0;text-transform:none;
          display:block;margin-top:6px;font-weight:600;color:var(--tekst)}
.podpis span{font-family:var(--osn);font-size:16px;letter-spacing:0;text-transform:none;
             display:block;margin-top:4px;color:#3b3f36;max-width:80ch}

.ekran{max-width:1440px;margin:0 auto 8px;background:var(--fon);
       min-height:900px;display:flex;flex-direction:column}

/* ——— шапка, общая для всех трёх ——— */
.shapka{display:flex;align-items:center;gap:32px;padding:24px 56px;
        border-bottom:1px solid var(--tekst)}
.logo{font-family:var(--zag);font-weight:600;font-size:20px;letter-spacing:-.02em;
      white-space:nowrap}
/* Без nowrap «О компании» ломалось на две строки и роняло всю шапку. */
.menu{display:flex;gap:24px;font-size:15px;margin-left:24px}
.menu a{white-space:nowrap}
.shapka .spravа{margin-left:auto;display:flex;align-items:center;gap:20px}
.tel{font-family:var(--mono);font-size:15px;white-space:nowrap}
.knopka{background:var(--akcent);color:#fff;border:0;border-radius:2px;
        padding:12px 22px;font-family:var(--osn);font-size:15px;font-weight:600;
        cursor:pointer;white-space:nowrap}
.knopka.pusto{background:transparent;color:var(--tekst);border:1px solid var(--tekst)}

.telo{flex:1;padding:24px 56px;display:flex;flex-direction:column;
      justify-content:center}

h1{font-family:var(--zag);font-weight:600;line-height:.98;letter-spacing:-.02em;
   margin:0}
.pod{font-size:18px;margin:16px 0 0;max-width:68ch}

/* ——— линейка ——— */
.lineika{position:relative;height:46px;margin-top:22px;
         border-bottom:1px solid var(--tekst)}
.riska{position:absolute;bottom:0;width:1px;background:var(--tekst)}
.riska.krupno{height:26px;background:var(--akcent);width:2px}
.riska.melko{height:9px}
.riska b{position:absolute;bottom:32px;left:50%;transform:translateX(-50%);
         font-family:var(--mono);font-size:13px;font-weight:500;color:var(--akcent)}
.sm{position:absolute;right:0;bottom:32px;font-family:var(--mono);font-size:13px;
    color:#5b6052}

/* ——— полосы ширины ——————————————————————————————————————————————
   Две строки на товар, а не одна: в первой версии название и техстрока стояли
   в ряд с полосой и уезжали за правый край — у гобелена название с артикулом
   длиной в полстроки. Теперь текст сверху, полоса под ним, и полоса меряется
   от того же левого края, что и линейка. */
.polosy{margin-top:4px}
.polosa{padding:9px 0 6px;border-bottom:1px solid rgba(22,24,28,.18)}
.polosa .stroka{display:flex;align-items:baseline;gap:16px}
.polosa .imya{font-size:16px;overflow:hidden;text-overflow:ellipsis;
              white-space:nowrap}
.polosa .shirina{margin-left:auto;font-family:var(--mono);font-size:13px;
                 color:#3b3f36;white-space:nowrap;flex:none}
.polosa .plashka{display:block;height:10px;background:var(--tekst);margin-top:8px}

.fakty{display:flex;border-top:1px solid var(--tekst);
       font-family:var(--mono);font-size:13px;letter-spacing:.04em}
.fakty div{flex:1;padding:15px 56px 15px 0;border-right:1px solid rgba(22,24,28,.2)}
.fakty div:last-child{border-right:0}
.fakty-obertka{padding:0 56px}

/* ——— вариант 2: цветные полосы во весь экран ——— */
.krupnye{display:flex;flex-direction:column;gap:0;margin-top:auto}
.krupnaya{position:relative;display:flex;align-items:flex-end;
          border-top:1px solid var(--tekst)}
.krupnaya .zaliv{height:100%;position:absolute;left:0;top:0}
.krupnaya .nadpis{position:relative;padding:14px 0 14px 20px;font-family:var(--mono);
                  font-size:14px}
.krupnaya.temnaya .nadpis{color:#F2EEE6}
.krupnaya.glavnaya{min-height:300px}
.krupnaya.glavnaya h1{position:relative;padding:32px 20px}

/* ——— вариант 3: складская ведомость ——— */
.vedomost{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:14px}
.vedomost th{text-align:left;font-weight:500;padding:10px 16px 10px 0;
             border-bottom:1px solid var(--tekst);letter-spacing:.06em;
             text-transform:uppercase;font-size:12px;color:#3b3f36}
.vedomost td{padding:12px 16px 12px 0;border-bottom:1px solid rgba(22,24,28,.15)}
/* Ширина, плотность и «цена по запросу» рвались на две строки, как только
   окно становилось уже 1440. Переносить в ведомости можно только название. */
.vedomost td+td{white-space:nowrap}
/* Первая колонка забирает весь остаток ширины: иначе «Ткань Брезент СКПВ»
   рвалось на три строки, а справа оставалось пустое место. */
.vedomost td:first-child,.vedomost th:first-child{width:100%}
.vedomost tr td:last-child{text-align:right;color:var(--akcent)}
.vedomost tr.razdel td{border-top:1px solid var(--tekst);padding-top:14px}
.vedomost tr.razdel ~ tr.razdel td{border-top:0;padding-top:12px}
.vedomost tr.razdel td:first-child{font-family:var(--osn);font-size:15px}
/* Цифра меряется по своей колонке, а не в пикселях. В колонке
   minmax(0,430px) трек умеет сжиматься, когда окно уже 1440, — а 118 px
   не умеют, и «55 000» наезжало на таблицу. cqw = 1% ширины колонки:
   «55 000» в Unbounded занимает около 3.1 своей кегли, поэтому 30cqw
   помещается с запасом на любой ширине. */
.levaya{container-type:inline-size}
.schet{font-family:var(--zag);font-weight:600;font-size:min(118px,30cqw);
       line-height:.92;letter-spacing:-.03em;margin:0;white-space:nowrap}
/* white-space:nowrap у самой цифры наследуется вниз, и подпись под ней шла
   одной строкой через весь экран поверх таблицы. Возвращаем перенос явно. */
.schet small{display:block;white-space:normal;font-family:var(--osn);
             font-size:17px;font-weight:400;line-height:1.5;letter-spacing:0;
             margin-top:18px;color:#3b3f36;max-width:44ch}
.dve{display:grid;grid-template-columns:minmax(0,430px) minmax(0,1fr);gap:56px;
     align-items:start}

/* Полоса ткани: кадр 550×366 повторяется плиткой во всю ширину окна. Высота
   ровно в высоту кадра — увеличивать нельзя, разъедется в кашу. */
.polosa-tkani{height:120px;background-repeat:repeat;background-size:auto 366px;
              border-top:1px solid var(--tekst)}

/* Между 900 и 1180 меню с телефоном и кнопкой не помещались в строку, и
   «О компании» переносилось на второй ряд. Телефон уходит первым: он
   продублирован в подвале, а кнопка — нет. */
@media (max-width:1180px){
  .shapka .spravа .tel{display:none}
  .menu{gap:18px;margin-left:12px}
  .shapka{gap:20px}
  /* Ниже 1180 таблице оставалось около 400 px, и названия рвались на три
     строки. Ставим цифру и ведомость друг под другом: ведомость получает
     всю ширину, а цифра остаётся такой же крупной. */
  .dve{grid-template-columns:1fr;gap:32px}
  .levaya{max-width:520px}
}
@media (max-width:560px){
  .riska.poslednyaya b{display:none}
}
/* Ведомость на телефоне: четыре колонки в 390 px не помещаются никак, и
   таблица уезжала за край. Разворачиваем каждую строку в две: название
   сверху, характеристики под ним одной моноширинной строкой через точку.
   Шапку колонок убираем — подписи «Ш-90 см» и «пл. 540 г/м²» сами себя
   называют. */
@media (max-width:700px){
  .vedomost tr:first-child{display:none}
  .vedomost tr{display:block;padding:12px 0;
               border-bottom:1px solid rgba(22,24,28,.15)}
  .vedomost td{display:inline;border:0;padding:0;white-space:normal}
  .vedomost td:first-child{display:block;font-family:var(--osn);font-size:15px;
                           margin-bottom:5px;width:auto}
  .vedomost td+td:not(:last-child)::after{content:' · '}
  /* У сатин-страйпа плотности в названии нет, и пустая ячейка давала
     вторую точку подряд: «Ш-280 см · · цена по запросу». */
  .vedomost td:empty::after{content:none}
  .vedomost tr td:last-child{text-align:left}
  .vedomost tr.razdel td{border-top:0;padding-top:0}
}
@media (max-width:900px){
  .menu,.shapka .spravа .tel{display:none}
  .telo{padding:32px 20px}
  .shapka{padding:16px 20px}
  .fakty{flex-direction:column}
  .fakty-obertka{padding:0 20px}
  .fakty div{border-right:0;border-bottom:1px solid rgba(22,24,28,.2);padding:14px 0}
  .dve{grid-template-columns:1fr;gap:28px}
  .schet{font-size:min(72px,26cqw)}
}
"""


def шапка() -> str:
    punkty = "".join(f"<a>{p}</a>" for p in МЕНЮ)
    return (f'<div class="shapka"><div class="logo">Текстиль-Сити</div>'
            f'<nav class="menu">{punkty}</nav>'
            f'<div class="spravа"><span class="tel">{ТЕЛЕФОН}</span>'
            f'<button class="knopka">Запросить прайс</button></div></div>')


def факты() -> str:
    return ('<div class="fakty-obertka"><div class="fakty">'
            + "".join(f"<div>{f}</div>" for f in ФАКТЫ) + "</div></div>")


def линейка() -> str:
    riski = []
    for sm in range(0, ШКАЛА + 1, 10):
        krupno = sm in РИСКИ
        cls = "riska krupno" if krupno else "riska melko"
        # На узком экране подпись последней риски налезала на «см» у правого
        # края. Помечаем её, чтобы спрятать подпись на телефоне; сама риска
        # остаётся — шкала не должна обрываться.
        if sm == РИСКИ[-1]:
            cls += " poslednyaya"
        podpis = f"<b>{sm}</b>" if krupno else ""
        riski.append(f'<i class="{cls}" style="left:{sm / ШКАЛА * 100:.3f}%">{podpis}</i>')
    return f'<div class="lineika">{"".join(riski)}<span class="sm">см</span></div>'


def экран_линейка() -> str:
    polosy = "".join(
        f'<div class="polosa"><div class="stroka">'
        f'<span class="imya">{imya}</span>'
        f'<span class="shirina">Ш-{sh} см{" · " + plotnost if plotnost else ""}</span>'
        f'</div><span class="plashka" style="width:{sh / ШКАЛА * 100:.2f}%"></span></div>'
        for imya, sh, plotnost in ПЕРВЫЙ_ЭКРАН)
    return f"""<section class="ekran">{шапка()}
  <div class="telo">
    <h1 style="font-size:clamp(40px,7vw,104px)">Всё для швейного<br>и мебельного производства</h1>
    <p class="pod">Более 55 000 товаров в наличии на складе в Ростове-на-Дону.
       Отгружаем целыми рулонами и упаковками, минимальный заказ 3 000 ₽.</p>
    {линейка()}
    <div class="polosy">{polosy}</div>
    <div style="margin-top:22px"><button class="knopka">Запросить прайс</button>
      <button class="knopka pusto" style="margin-left:12px">Подобрать ткань под изделие</button></div>
  </div>
  {факты()}
</section>"""


ТЁМНЫЕ = ("#6E7A5E", "#3E4038")


def экран_polosy() -> str:
    # Цвета — из самого товара: небелёный хлопок, брезент, графит.
    cveta = ["#D8CDB6", "#C3BBA6", "#8E8C7E", "#6E7A5E", "#3E4038"]
    # Последние два цвета тёмные, и подпись по ним читается только светлой:
    # в первой версии «Сатин-страйп» на графите почти пропал.
    krupnye = "".join(
        f'<div class="krupnaya{" temnaya" if cvet in ТЁМНЫЕ else ""}">'
        f'<span class="zaliv" style="width:{sh / ШКАЛА * 100:.2f}%;background:{cvet}"></span>'
        f'<span class="nadpis">{imya} · Ш-{sh} см</span></div>'
        for (imya, sh, _plotnost), cvet in zip(ТКАНИ, cveta))
    return f"""<section class="ekran">{шапка()}
  <div class="telo" style="padding-bottom:0">
    <div class="krupnaya glavnaya">
      <span class="zaliv" style="width:100%;background:#D8CDB6"></span>
      <h1 style="font-size:clamp(36px,5.6vw,84px)">Всё для швейного<br>и мебельного производства</h1>
    </div>
    {krupnye}
    <p class="pod" style="margin-top:28px">Ширина полосы — настоящая ширина рулона.
       Более 55 000 товаров на складе в Ростове-на-Дону.</p>
    <div style="margin:24px 0 32px"><button class="knopka">Запросить прайс</button></div>
  </div>
  {факты()}
</section>"""


def экран_vedomost() -> str:
    stroki = "".join(
        f"<tr><td>{imya}</td><td>Ш-{sh} см</td><td>{plotnost}</td>"
        f"<td>цена по запросу</td></tr>"
        for imya, sh, plotnost in ТКАНИ)
    razdely = "".join(
        f"<tr class='razdel'><td colspan='2'>{imya}</td><td colspan='2'>{skolko}</td></tr>"
        for imya, skolko in РАЗДЕЛЫ[:5])
    return f"""<section class="ekran">{шапка()}
  <div class="telo">
    <div class="dve">
      <div class="levaya">
        <p class="schet">55&nbsp;000<small>наименований на складе в Ростове-на-Дону.
          Девять разделов, 300 подразделов, отгрузка целыми рулонами
          и упаковками.</small></p>
        <div style="margin-top:32px"><button class="knopka">Запросить прайс</button></div>
      </div>
      <div>
        <table class="vedomost">
          <tr><th>Наименование</th><th>Ширина</th><th>Плотность</th><th>Цена</th></tr>
          {stroki}
          {razdely}
        </table>
      </div>
    </div>
  </div>
  <div class="polosa-tkani" style="background-image:url({фактура_base64()})"></div>
  {факты()}
</section>"""


ОПИСАНИЯ = [
    ("Вариант 1 — «Линейка»", "Громкое место: заголовок 104 px.",
     "Фирменный приём в чистом виде: измерительная шкала во всю ширину, под ней "
     "полосы настоящей ширины рулона. Ни одной фотографии — экран держится на "
     "типографике, и его можно показывать уже сегодня."),
    ("Вариант 2 — «Полосы ткани»", "Громкое место: цветные полосы во весь экран.",
     "Тот же приём, но ширина показана заливкой, а не линейкой. Цвета взяты из "
     "самого товара — небелёный хлопок, брезент, графит. Заголовок меньше: "
     "громким здесь работает цвет."),
    ("Вариант 3 — «Ведомость» (выбран)", "Громкое место: цифра 55 000.",
     "Экран как складская ведомость: слева одна огромная цифра, справа таблица "
     "моноширинным. Ставка на ассортимент, а не на ширину. Внизу полоса "
     "настоящей ткани из их каталога — она повторяется плиткой, а не "
     "растянута: кадров крупнее 640 px у клиента нет ни одного."),
]


def собрать() -> str:
    ekrany = [экран_линейка(), экран_polosy(), экран_vedomost()]
    kuski = []
    for (nazv, gromko, pояснение), ekran in zip(ОПИСАНИЯ, ekrany):
        kuski.append(f'<div class="podpis">{gromko}<b>{nazv}</b>'
                     f'<span>{pояснение}</span></div>{ekran}')
    return f"""<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Текстиль-Сити — три первых экрана</title>
<style>{СТИЛЬ}</style></head>
<body>{''.join(kuski)}
<div class="podpis" style="padding-bottom:64px">Макет, не сайт<span>
Собрано по clients/textileopt.ru/DESIGN.md на данных выгрузки от 1 сентября 2026.
Фотографий нет: они ещё не выгружены, и генерировать «наш склад» нельзя.
Цены не показаны намеренно — на сайте клиента написано «Актуальные цены
и наличие по запросу».</span></div>
</body></html>"""


if __name__ == "__main__":
    # --только N печатает один экран без подписей: нужно, чтобы снимать
    # варианты по одному и смотреть их глазами, а не гадать по общей странице.
    tolko = None
    argi = sys.argv[1:]
    if "--только" in argi:
        i = argi.index("--только")
        tolko = int(argi[i + 1])
        argi = argi[:i] + argi[i + 2:]
    if tolko:
        ekran = [экран_линейка, экран_polosy, экран_vedomost][tolko - 1]()
        put = argi[0] if argi else os.path.join(ЗДЕСЬ, f"экран-{tolko}.html")
        with open(put, "w", encoding="utf-8") as f:
            f.write(f'<!doctype html><html lang="ru"><head><meta charset="utf-8">'
                    f'<style>{СТИЛЬ}</style></head><body style="background:var(--fon)">'
                    f'{ekran}</body></html>')
        print(f"готово: {put}")
        sys.exit(0)
    kuda = argi[0] if argi else os.path.join(ЗДЕСЬ, "три-экрана.html")
    with open(kuda, "w", encoding="utf-8") as f:
        f.write(собрать())
    print(f"готово: {kuda}")
