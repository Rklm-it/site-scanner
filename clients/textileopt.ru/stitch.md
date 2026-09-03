# Промпты для Stitch: textileopt.ru («Текстиль-Сити»)

Собрано после разбора того, **как на самом деле сделан kondi-kaluga** — тот
сайт владелец назвал бомбой, и повторяем не впечатление, а последовательность.
Разбор ниже сделан по данным Stitch API (`list_projects`, `list_screens`) и по
экспорту `stitch_-2.zip`, который лежит в репозитории `kondi-kaluga-fresh-air`
последним коммитом.

## Как сделан kondi-kaluga (факты, не пересказ)

Проект в Stitch: **«Конди Калуга Первый Экран»**, тип **TEXT_TO_UI_PRO**,
устройство **DESKTOP**, 19 экранов. Порядок работы виден по названиям экранов
и по их высоте — она росла от шага к шагу:

| # | Экран | Высота |
|---|---|---|
| 1 | Конди-Калуга — Главный экран | 3048 |
| 2 | Конди-Калуга — Сколько стоит монтаж | 5566 |
| 3 | Конди-Калуга — Что входит в монтаж | 7990 |
| 4 | Конди-Калуга — Полный лендинг с заявкой и контактами | 10952 |
| 5 | Конди-Калуга — Полный лендинг с живой анимацией ветра | 11330 |
| 6 | Конди-Калуга — Полный лендинг с оригинальной анимацией потока | 10956 |
| 7 | Конди-Калуга — Мобильная версия | 2386 (ширина 780) |

Плюс отдельный квадратный экран 512×512 «Shader» — проба самого эффекта в
изоляции, до того как его завели на страницу.

**Пять вещей, из которых получилась «бомба».** Все пять переносимы, ни одна не
про кондиционеры:

1. **Сначала дизайн-система, потом экраны.** В проекте лежит своя система
   `Kondi Kaluga Architectural Climate`: YAML с токенами (49 цветов, 13
   типографических ступеней, скругления, шаг сетки) и следом проза на
   английском — Brand & Style, Colors, Typography, Layout & Spacing, Elevation
   & Depth, Shapes, Components. Это тот же формат, что наш `DESIGN.md`.
   **Именно она держит вид**: дальше можно писать промпты про содержание и не
   бояться, что генератор возьмёт свои дефолты.
2. **Система написана против штампов ниши прямым текстом.** Дословно:
   «repudiates retail air conditioning tropes — such as illustrated snowflakes,
   swirling wind icons, or generic saturated blues». Запрет стоит **в системе**,
   а не в промпте экрана, поэтому действует на все экраны разом.
3. **Экраны наращивались правкой одного экрана, а не собирались заново.**
   Главный экран → к нему прайс → к нему «что входит» → заявка и контакты.
   Каждый шаг — правка предыдущего результата, отсюда и рост высоты.
4. **Движение заказано отдельным шагом, в конце, и своими словами.** Не
   «добавь анимации», а «живая анимация ветра», потом «оригинальная анимация
   потока». Stitch на это выдал **фрагментный шейдер на WebGL**: fbm-шум,
   четыре октавы, смещение от курсора, канвас фоном за текстом. Текст при этом
   остался обычным HTML поверх канваса — то есть LCP не пострадал.
5. **Мобильная версия — отдельным экраном**, а не «сделай адаптив».

Дальше экспорт zip → загрузка в репозиторий проекта Lovable → Lovable собирает
по этим экранам. Именно так там появился коммит «Add files via upload».

## Что меняем для textileopt и почему

**Приём остаётся наш** — линейка ширин (`DESIGN.md`, «ширина рулона показана
физически»). Он держится на данных клиента: ширина зашита в название 198
товаров из 662, потому что это первый вопрос покупателя.

**Фон становится тёмным.** Светлая «Ведомость» дала ровно тот результат,
который владелец забраковал. Тёмный графит здесь не подражание kondi, а то,
что делает акцент `#C2410C` (оранжевый погрузчика, выбранный владельцем)
цветом, а не пятном на сером. Все остальные величины из `DESIGN.md` —
шрифты, кегли, скругление 2 px, запреты — переносятся без изменений.
Вернуть светлый фон, если не зайдёт: в дизайн-системе поменять `surface` на
`#F4F4F2`, `on-surface` на `#101114`, остальное пересчитается.

**Фотографий по-прежнему нет**, и это решается тем же приёмом, что у kondi:
вместо кадра — шейдер. У них поток воздуха, у нас **переплетение нитей**.
Это честно: не сток и не выдуманный склад, а структура их собственного товара.

## Порядок

1. Новый проект в Stitch: тип **Pro (text to UI)**, устройство **Desktop**.
2. Создать дизайн-систему — промпт 0.
3. Экран 1, промпт 1. Дальше правки того же экрана: промпты 2, 3, 4.
4. Движение — промпт 5, отдельным шагом и последним.
5. Мобильная версия — промпт 6, новым экраном.
6. Экспорт проекта в zip → в репозиторий Lovable → промпт 7.

Между шагами ничего не переспрашивать и не «улучшать»: у kondi сработал
именно этот порядок.

---

## Промпт 0. Дизайн-система

В Stitch: создать дизайн-систему и вставить текст целиком. Он на английском
намеренно — у kondi система была на английском, а промпты экранов на русском,
и русские тексты в макетах от этого не пострадали.

Если в списке шрифтов Stitch не окажется **Unbounded** — взять любой близкий
гротеск с широкими знаками и сказать мне: подмена шрифта в коде это одна
строка, а перебранная раскладка — нет.

```markdown
---
name: Textile City Warehouse Grid
colors:
  surface: '#0E0F11'
  surface-dim: '#0A0B0D'
  surface-bright: '#2A2D31'
  surface-container-lowest: '#08090B'
  surface-container-low: '#131519'
  surface-container: '#171A1E'
  surface-container-high: '#1E2126'
  surface-container-highest: '#262A2F'
  on-surface: '#F2F1EE'
  on-surface-variant: '#A8A6A0'
  inverse-surface: '#F2F1EE'
  inverse-on-surface: '#1C1F23'
  outline: '#6E6C67'
  outline-variant: '#33363A'
  surface-tint: '#C2410C'
  primary: '#E8621F'
  on-primary: '#2A0C00'
  primary-container: '#C2410C'
  on-primary-container: '#FFE2D3'
  secondary: '#D6C9A8'
  on-secondary: '#33301F'
  secondary-container: '#4A4530'
  on-secondary-container: '#EFE6CC'
  tertiary: '#A8A6A0'
  on-tertiary: '#26282B'
  tertiary-container: '#33363A'
  on-tertiary-container: '#E4E2DD'
  error: '#FFB4AB'
  on-error: '#690005'
  error-container: '#8A1B1B'
  on-error-container: '#FFDAD6'
  background: '#0E0F11'
  on-background: '#F2F1EE'
  surface-variant: '#262A2F'
typography:
  display-metric:
    fontFamily: Unbounded
    fontSize: 128px
    fontWeight: '600'
    lineHeight: 116px
    letterSpacing: -0.04em
  display-metric-mobile:
    fontFamily: Unbounded
    fontSize: 56px
    fontWeight: '600'
    lineHeight: 52px
    letterSpacing: -0.03em
  display-hero:
    fontFamily: Unbounded
    fontSize: 64px
    fontWeight: '600'
    lineHeight: 62px
    letterSpacing: -0.02em
  display-hero-mobile:
    fontFamily: Unbounded
    fontSize: 36px
    fontWeight: '600'
    lineHeight: 38px
    letterSpacing: -0.02em
  headline-xl:
    fontFamily: Unbounded
    fontSize: 44px
    fontWeight: '600'
    lineHeight: 48px
    letterSpacing: -0.02em
  headline-xl-mobile:
    fontFamily: Unbounded
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: IBM Plex Sans
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 30px
    letterSpacing: -0.01em
  headline-sm:
    fontFamily: IBM Plex Sans
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 26px
    letterSpacing: 0em
  body-lg:
    fontFamily: IBM Plex Sans
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
    letterSpacing: 0em
  body-md:
    fontFamily: IBM Plex Sans
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 26px
    letterSpacing: 0em
  body-sm:
    fontFamily: IBM Plex Sans
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 22px
    letterSpacing: 0.005em
  label-mono-metric:
    fontFamily: IBM Plex Mono
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
    letterSpacing: 0.02em
  label-caps:
    fontFamily: IBM Plex Mono
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 14px
    letterSpacing: 0.14em
rounded:
  sm: 0.125rem
  DEFAULT: 0.125rem
  md: 0.125rem
  lg: 0.25rem
  xl: 0.25rem
  full: 9999px
spacing:
  space-2xs: 0.25rem
  space-xs: 0.5rem
  space-sm: 0.75rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
  space-2xl: 3rem
  space-3xl: 4.5rem
  space-4xl: 6rem
  gutter-mobile: 1rem
  gutter-desktop: 2rem
  max-width-container: 1360px
---

## Brand & Style

This design system serves a wholesale textile supplier in Rostov-on-Don that
stocks fabric, sewing hardware, fillings and mattress components for garment
and furniture factories, hotels and kindergartens. The buyer is a production
manager, not a hobbyist: they think in running metres, roll widths, fabric
weight per square metre and minimum cut length.

The system deliberately **rejects every craft-and-hobby cliché of the textile
category**: no scissors, spools, needles, sewing-machine or thread icons, no
pastel or dusty-rose palettes, no floral or watercolour ornament, no
handwritten or calligraphic type, no rounded card tiles arranged in an even
grid, no gradients anywhere. Flat dyeing is a virtue of real fabric; a gradient
reads as a defect.

The visual language is **a working warehouse at night, seen as a measurement
instrument**: deep graphite fields, hairline rules, tabular figures, and one
loading-dock orange that appears only where the user can act. Tone: precise,
industrial, unsentimental, confident about stock and dimensions.

**The signature mechanic of the whole product is width made physical.** A
single measuring scale running 0 to 330 centimetres recurs across the page.
Every fabric sits on that scale as a horizontal bar whose length is
proportional to its real bolt width, so `Ш-325` is visibly and measurably wider
than `Ш-90` without the user reading a number. This is not one section; it is
the spine. It appears in the hero as data, opens the catalogue as a ruled axis,
sits inside every product row, and becomes the filter control. A layout that
uses it once has failed.

## Colors

- **Fields:** `#0E0F11` base canvas; `#131519` recessed utility zones;
  `#171A1E` primary panel tier; `#1E2126` hover and elevated tier.
- **Ink:** `#F2F1EE` primary type — a warm off-white, the colour of undyed
  cotton, never pure `#FFFFFF`; `#A8A6A0` secondary prose and units;
  `#6E6C67` inactive labels.
- **Action:** `#C2410C` loading-dock orange — buttons, active scale ticks,
  the filled portion of any width bar, focus rings. `#E8621F` is the same hue
  lightened for orange type on dark fields, used only where `#C2410C` fails
  contrast. **No other chromatic colour exists in the interface.**
- **Clearance only:** `#8A1B1B` deep red, permitted exclusively on
  sale/clearance markers. Never for errors of any other kind, never decorative.
- **Product colour is the exception:** fabric swatches and photographs carry
  their own real colours, sampled from the goods themselves. They are content,
  not palette, and are never tinted to match the interface.
- **Rules and dividers:** `rgba(255,255,255,0.10)` standard hairline;
  `rgba(255,255,255,0.05)` internal table grid; `#C2410C` at full strength for
  an active measurement tick.

## Typography

Headings use **Unbounded** (600) — a wide-set geometric display face with real
Cyrillic. Body copy uses **IBM Plex Sans** (400/600). **IBM Plex Mono** is
reserved for one job only: the technical line of a product — width, weight,
article number, minimum cut. That reservation is what makes the mono line read
as a spec plate rather than as decoration.

Rules:
- **Tabular figures everywhere numbers align**: prices, widths, weights,
  quantities, delivery thresholds.
- **One loud element per page, and it is a number, not a sentence.** The hero
  headline count runs at `display-metric`; nothing else on the page comes
  within half that size.
- Measured prose sets to a 68-character measure. Never centre a paragraph.
- Never letterspace lowercase Cyrillic. `label-caps` is uppercase Latin/Cyrillic
  micro-labels only, and only above data, never above every section as a
  decorative eyebrow.
- Banned faces on this project: Inter, Roboto, Open Sans, Montserrat, Lato,
  Playfair Display.

## Layout & Spacing

Blueprint discipline: strict alignment, generous empty field, sections
separated by air and a single hairline rule — never by a boxed frame.

- **Desktop (≥1024px):** 12 columns inside a 1360px maximum, 32px gutters,
  page margins 48–80px. Section rhythm 96px.
- **Tablet (768–1023px):** 8 columns, 24px gutters. Wide data tables scroll
  horizontally inside their own container; the page body never scrolls
  sideways.
- **Mobile (≤767px):** 4 columns, 16px gutters, section rhythm 56px. A
  four-column product row unfolds into two lines rather than compressing.

The measuring scale is always full-bleed to the container edges: it is an axis,
not a component sitting inside a box.

## Elevation & Depth

Depth comes from field value and hairline edges, never from soft drop shadows
and never from glass blur. A panel is distinguished from the canvas by being
two steps lighter and by a 1px `rgba(255,255,255,0.10)` top edge. Overlays
(filters, request dialogs) sit on `#171A1E` at full opacity with a 1px border;
the page behind dims to 60% black. Hover raises a panel one tier and brings its
border to `rgba(194,65,12,0.45)` — no lift, no scale, no shadow bloom.

## Shapes

Radius is **2px everywhere** — buttons, panels, inputs, images, swatches.
Fabric is cut on a straight line and stacked in rectangles; rounded tiles turn
this into a generic marketplace and destroy the width mechanic. Circles are
permitted only for a status dot and for a slider thumb. No pill buttons.

## Components

### Measuring scale (the signature element)
A full-width horizontal axis from 0 to 330 cm. Ticks at 80, 150, 220, 280, 325
with `label-mono-metric` numerals below the line and the unit `см` stated once
at the right end. The line is `rgba(255,255,255,0.25)`, 1px; an active tick is
`#C2410C`, 2px, and full height. Content can stand on the axis; the axis is
never boxed.

### Width bar
A horizontal bar inside a product or section row whose length is proportional
to the real bolt width against the same 0–330 scale. Height 8px, radius 2px,
fill `#C2410C` at 85% opacity over a `rgba(255,255,255,0.06)` track that always
shows the full 330 cm span, so bars are comparable across rows. The numeral
sits to the right in `label-mono-metric`.

### Product row
Not a card. A full-width row separated from the next by a hairline rule:
name in `headline-sm`, technical line in `label-mono-metric`
(`Ш-220 · пл. 120 г/м² · арт. 6165130 · от 1 м`), the width bar, and the
price slot on the right. Rows, not tiles — a tile grid is prohibited in the
catalogue.

### Buttons
Primary: `#C2410C` fill, `#FFF6F1` text, height 56px, radius 2px, no shadow.
Hover darkens the fill and nothing moves. Secondary: transparent with a 1px
`rgba(255,255,255,0.25)` border and `#F2F1EE` text. Text link: `#E8621F` with a
1px underline offset 4px.

### Inputs and the width filter
Inputs: `#08090B` fill, 1px `rgba(255,255,255,0.14)` border, height 52px,
`#F2F1EE` 16px type, unit adornment (`см`, `м`, `г/м²`) pinned right in
`label-mono-metric` `#6E6C67`. Focus snaps the border to `#C2410C` with a 2px
outline — visible focus is mandatory on every interactive element.
The width filter is a slider running on the same 0–330 axis as the hero scale,
with a live readout: «ткань шире 200 см — N позиций».

### Data blocks
Conditions, delivery thresholds and lead times set as a two-column definition
list on a hairline grid, figures in `label-mono-metric`, right-aligned and
tabular. Never as three equal icon cards.

## Motion

The first screen is never animated: it carries the LCP element. Interface
feedback only — 180ms, `cubic-bezier(0.16, 1, 0.3, 1)`, transitioning colour,
border and opacity, never width, height or position. Scroll reveals, where used
at all, are 300–400ms with a 12–16px rise, staggered 60ms, at most five steps,
once per element. Every animated rule ships with a `prefers-reduced-motion:
reduce` counterpart that disables it. One animation approach per project.
```

---

## Промпт 1. Главный экран

Новый экран в проекте. Вставить как есть.

```
Сделай первый экран одностраничного сайта компании «Текстиль-Сити»
(textileopt.ru) — оптовая продажа тканей, швейной фурнитуры, наполнителей и
комплектующих для матрасов со склада в Ростове-на-Дону. Работают с 2009 года,
с 2011 года — официальный представитель компании «Фортекс» по комплектующим
для ортопедических матрасов. Покупатель — снабженец швейного или мебельного
производства, гостиница, детский сад. Он думает погонными метрами и шириной
рулона.

Экран во всю высоту окна, тёмный, без фотографий: фотографий у меня пока нет,
и стоковые ставить нельзя.

Слева, во весь левый край, одна гигантская цифра «55 000» шрифтом заголовков
кеглем display-metric. Это громкое место страницы, второго такого на сайте
нет. Под цифрой в три строки: «наименований на складе в Ростове-на-Дону.
Девять разделов, 300 подразделов. Отгрузка целыми рулонами и упаковками».
Ниже оранжевая кнопка «Подобрать ткань по ширине» и рядом текстовая ссылка
«Позвонить: +7 (863) 273-23-50».

Справа — складская ведомость моноширинным шрифтом, без рамок и карточек,
строки разделены только тонкой линией. Восемь строк, в каждой название,
техстрока и полоса ширины в масштабе общей шкалы 0–330 см:

Бязь отбеленная — Ш-220 см
Брезент огнеупорный — Ш-90 см
Сатин страйп — Ш-240 см
Мех искусственный — Ш-190 см
Ткань палаточная — Ш-150 см
Тик матрасный — Ш-280 см
Полотно вафельное — Ш-45 см
Флизелин клеевой — Ш-90 см

Под ведомостью строка мелким моноширинным: «Актуальные цены и наличие по
запросу».

По самому низу экрана, во всю ширину окна, — измерительная линейка от 0 до
330 сантиметров с рисками 80 · 150 · 220 · 280 · 325 и подписью «см» у
правого края. Она проходит под обеими колонками и служит осью всей страницы:
дальше по сайту она будет повторяться.

Сверху шапка: слева «ТЕКСТИЛЬ-СИТИ» и мелкой строкой «Оптовый склад ·
Ростов-на-Дону · с 2009 года»; в середине ссылки Каталог, Услуги, Условия,
Доставка, Контакты; справа телефон +7 (863) 273-23-50 ссылкой tel: и рядом
мелко «8-800-700-44-75 бесплатно по РФ».

Заголовка H1 крупным кеглем на этом экране быть не должно: громкое место одно
и это цифра. Строку «Всё для швейного и мебельного производства» поставь
мелким текстом над цифрой — это их поисковый заголовок, потерять его нельзя.

Первый экран не анимировать.

Ничего не придумывать: никаких «15 лет на рынке», «более 10 000 клиентов»,
«доставка за 24 часа». Телефоны, адрес и цифры — только те, что я дал.
Никаких иконок ножниц, катушек и швейных машинок. Никаких эмодзи. Никаких
градиентов. Никаких скруглённых карточек-плиток. Все подписи по-русски.
```

## Промпт 2. Каталог по задаче

Правка того же экрана — «добавь ниже».

```
Добавь ниже на этой же странице секцию каталога. Заголовок секции: «Девять
разделов, 300 подразделов».

Открывает секцию та же измерительная линейка 0–330 см, что и на первом
экране, — с рисками 80 · 150 · 220 · 280 · 325.

Дальше девять строк во всю ширину, не плитками и не карточками, разделённых
тонкой линией. В каждой строке слева название раздела, справа моноширинным
число подразделов, между ними полоса в масштабе линейки, если раздел
измеряется шириной:

Ткани оптом со склада — 153 подраздела
Швейная фурнитура оптом — 80 подразделов
Наполнители и утеплители — 15 подразделов
Комплектующие для изготовления матрасов — 11 подразделов
Домашний текстиль — 8 подразделов
Швейное оборудование — 8 подразделов
Упаковка для текстиля оптом — 7 подразделов
Текстиль для отелей — 7 подразделов
Текстиль для детских садов — 2 подраздела

Над этими строками — подбор по ширине: ползунок, идущий по той же шкале
0–330 см, с живой подписью «ткань шире 200 см». Ползунок должен выглядеть
как часть линейки, а не как отдельный элемент формы.

Ниже — пять входов по задаче, строками, каждый со своим коротким пояснением
из их же каталога:

Швейное производство — ткани для спецодежды, пологов и тентов, фурнитура
Мебель и матрасы — тик матрасный, комплектующие «Фортекс», наполнители
Отели и рестораны — постельное бельё, махра, скатерти, салфетки
Детские сады — комплекты постельного, матрасы, полотенца
Розничным клиентам — заказы меньше 3 000 ₽ на нашем розничном сайте
lubodom.com

Пятый вход — честная ссылка на другой сайт, а не форма: розницу компания
развела сама.

Цены не показывай ни у одного товара: у клиента модель «актуальные цены и
наличие по запросу», это их формулировка.
```

## Промпт 3. Услуги и условия

```
Добавь ниже секцию услуг. Заголовок: «Не только продаём — шьём».

Три услуги, строками во всю ширину, разделёнными линией, у каждой настоящие
сроки и объёмы моноширинным шрифтом справа:

1. Пошив постельного белья для гостиниц, пансионатов, больниц и детских садов
   по индивидуальным заказам. Спецификация на каждый заказ, при несоответствии
   параметрам — бесплатная замена. Ткани: страйп-сатин, сатин, перкаль, бязь,
   махровое полотно. Срок: 3–10 дней.
2. Вышивка логотипа на постельное бельё, полотенца, халаты, скатерти и
   салфетки — для гостиниц, салонов красоты, ресторанов. Нитки «Гутерманн»,
   Германия.
3. Изготовление ткани с логотипом заказчика — для мебельного и матрасного
   производства, пошива подушек и одеял. От 15 000 м.п., срок от 2,5 месяцев,
   предоставляем отгрузочные образцы.

Числа не округлять: «от 15 000 м.п.» и «2,5 месяца» — это и есть
доказательство, что услуга настоящая.

Следом секция «Как мы отпускаем товар» — двумя колонками определений на
тонкой сетке, цифры моноширинным и выключены вправо:

Минимальная сумма заказа — 3 000 ₽, можно набирать из разных отделов
Оптовая цена — только целым рулоном или упаковкой
Меньше рулона — можно, от 1 метра, по розничной цене
Отдел распродажи — опт от 3 метров
Фурнитура и упаковка — от 1 000 ₽
Оборудование — от 3 000 ₽
Купонные ткани — режем только по границе купона
Цены — с НДС, юрлицам счёт с выделенным НДС
Бесплатная доставка — от 100 000 ₽
Резерв заказа — до 5 дней
Счёт — от 30 минут до 2 дней

Не превращай это в три карточки с иконками: это таблица условий, её читают
глазами снабженца.
```

## Промпт 4. Доставка, заявка, подвал

```
Добавь ниже три последних блока.

Доставка. Заголовок «Отгружаем по России». Бесплатно от 100 000 ₽ по
Ростовской области, Краснодарскому и Ставропольскому краю, Воронежской
области. Транспортные компании строкой, с ценами до терминала моноширинным:
Деловые Линии от 250 ₽, НЕВА от 250 ₽, Энергия от 400 ₽, ПЭК, КИТ,
Байкал-Сервис, ЦАП, СДЭК 3–5 дней, Почта России 7–14 дней до 20 кг.
Самовывоз со склада: Ростов-на-Дону, пер. Технологический, 4.

Заявка. Заголовок «Пришлём цены и наличие». Форма в одну колонку, поля:
имя, телефон, что нужно (многострочное). Под полем «что нужно» подсказка
мелким шрифтом: «ткань, ширина, метраж — или просто задача, подберём сами».
Кнопка «Отправить заявку» оранжевая. Рядом с формой — способы связи
строками: +7 (863) 273-23-50 склад, многоканальный; 8-800-700-44-75
бесплатно по РФ; +7 918 273-00-95 Viber и WhatsApp; info@textileopt.ru.
Под кнопкой строка: «Отвечаем в рабочее время, обычно в тот же день».

Подвал. «Текстиль-Сити», склад: 344064, Ростов-на-Дону, пер. Технологический,
4 (он же ул. Вавилова, 56, вход с пер. Технологический). Телефоны и почты те
же. ИП Костанова Татьяна Николаевна, ИНН 616112762674, ОГРНИП
309619317300075. Строка «Работаем с 2009 года. С 2011 года — официальный
представитель компании „Фортекс“». Ссылка «Розничный магазин: lubodom.com».

В подвале ещё раз, тонкой линией во всю ширину, — та же измерительная линейка
0–330 см. Она открывает страницу и закрывает её.
```

## Промпт 5. Движение

Отдельным шагом и только сейчас, когда страница целиком собрана. У kondi
сработала ровно такая формулировка — своими словами про вещество, а не
«добавь анимацию».

```
Добавь на страницу одну живую, оригинальную анимацию — переплетение нитей.

Это фон, а не украшение секции: на канвасе за содержимым медленно ткётся
полотно — основа и уток, нити идут перпендикулярно и переплетаются, плотность
и натяжение слегка гуляют, как у настоящей ткани. Курсор тянет нити за собой,
и полотно отзывается волной, будто ткань подхватили за угол. Цвета — только
графит фона и оранжевый акцент, никаких новых цветов, контраст низкий: это
подложка, текст поверх неё должен читаться без усилий.

Сделай это фрагментным шейдером на WebGL внутри canvas, без внешних библиотек.
Канвас лежит фоном за обычным HTML-текстом, текст поверх него остаётся
настоящим текстом.

Ограничения обязательны:
— на первом экране анимации нет вообще, там канвас статичен: это самый
  крупный элемент страницы и он не должен ждать отрисовки;
— уже 768 пикселей ширины анимация выключается и на её месте остаётся
  неподвижная текстура переплетения;
— при prefers-reduced-motion: reduce анимация не запускается совсем;
— анимация останавливается, когда её блок ушёл из окна.

Кроме этого добавь появление строк каталога и ведомости при прокрутке:
300 миллисекунд, подъём на 14 пикселей, лесенкой по 60 миллисекунд, не более
пяти шагов, каждый элемент появляется один раз. И рост полос ширины из нуля
до своей длины, когда строка попадает в окно, — движение должно совпадать со
смыслом: полоса растёт ровно до своей ширины в сантиметрах.

Больше ничего не двигать. Никаких параллаксов, каруселей и всплывающих
элементов.
```

## Промпт 6. Мобильная версия

Новым экраном, устройство Mobile.

```
Сделай мобильную версию этой же страницы, 390 пикселей ширины.

Первый экран: цифра 55 000 кеглем display-metric-mobile, под ней те же три
строки, кнопка «Подобрать ткань по ширине» во всю ширину, под ней телефон
ссылкой. Ведомость переезжает под кнопку и показывает четыре строки вместо
восьми, остальные — по кнопке «Показать все». Линейка 0–330 см остаётся, но
подписаны только риски 80 · 220 · 325, иначе они наезжают друг на друга.

Строка товара разворачивается в две строки: сверху название, снизу техстрока
и полоса ширины. Ничего не сжимать в четыре колонки.

Таблица условий — две колонки, значение выключено вправо, если не помещается
в строку, значение уходит на следующую строку под название, а не переносится
посреди числа.

Горизонтальной прокрутки на странице быть не должно ни в одном месте.
Широкие таблицы прокручиваются внутри себя.

Анимации на мобильной версии нет.
```

## Промпт 7. Из Stitch в Lovable

Экспортировать проект в zip (кнопка экспорта в Stitch), загрузить архив в
репозиторий проекта в GitHub — так же, как это сделано в
`kondi-kaluga-fresh-air` коммитом «Add files via upload». Затем в Lovable:

```
В корне репозитория лежит архив с экранами из Stitch: в каждой папке файл
code.html и screenshot экрана. Собери по ним одностраничный сайт.

Экраны десктопные — основной; мобильный — второй. Разметку и стили брать из
code.html, а не придумывать заново: цвета, кегли, отступы и скругления должны
совпасть с макетом до пикселя.

Шейдер переплетения перенести как есть, вместе со всеми его ограничениями:
статичен на первом экране, выключен уже 768 пикселей, выключен при
prefers-reduced-motion, останавливается вне окна.

Тексты, телефоны, адреса и цифры — ровно те, что в макете. Ничего не
дописывать и не «улучшать» формулировки.

Убрать всё, что добавляет конструктор: скрипт cdn.gpteng.co, бейдж в углу,
og:image и favicon по умолчанию, заголовок вида Lovable Generated Project,
meta name="generator". Поставить lang="ru".
```

После сборки я прогоняю по проекту `check-lovable.sh`, `check-shablon.sh`,
`check-skuchno.sh` и `check-anim.sh` — до выкладки, а не после.

## Чего в этих промптах намеренно нет

- **Слов-настроений** — современный, минималистичный, спокойный, много
  воздуха. Генератор читает их как «возьми свои дефолты».
- **Цен в макете.** У клиента модель «актуальные цены и наличие по запросу»,
  и это его собственная формулировка, а не наша заглушка.
- **Числа 145 000.** На главной и в «О компании» у них «более 55 000
  наименований», в «Как купить» — «свыше 145 000 товаров». Расхождение в 2,6
  раза, спрашивать у клиента на созвоне. До ответа везде 55 000.
- **Минимального отреза числом.** Поле у них есть у каждого товара, но в
  выгрузку не попало. Пока не достали — в макете его нет вовсе, выдуманного
  числа не ставим.
- **Фотографий.** До прихода кадров из выгрузки первый экран держится на
  типографике, линейке и шейдере.
