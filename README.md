# site-scanner

Бот для поиска потенциальных клиентов веб-студии. Идёт по **выдаче Яндекса
и Google** для заданных категорий/городов, сканирует найденные сайты,
оценивает «устаревание» дизайна по набору эвристик, вытаскивает контакты и
выгружает **ранжированный список лидов** (CSV + JSON).

Логика простая: у кого сайт древний и кривой — тот кандидат на редизайн.
Чем выше `outdated_score`, тем «горячее» лид.

## Как это работает

```
поисковый запрос ──▶ список URL ──▶ убираем агрегаторы и дубли доменов
        ──▶ качаем каждый сайт ──▶ считаем outdated_score по эвристикам
        ──▶ вытаскиваем контакты ──▶ сортируем ──▶ leads.csv / leads.json
```

### Эвристики устаревания (файл `scanner/heuristics.py`)

| Сигнал | Баллы |
|---|---|
| Нет `<meta viewport>` (не адаптивный) | +22 |
| Нет HTTPS | +15 |
| Устаревшие теги (`font`, `center`, `marquee`, `frameset`…) | +15 |
| Flash-контент (`.swf`, `<embed>`) | +15 |
| Табличная вёрстка (≥3 таблиц с `width`) | +12 |
| Устаревшая CMS (Joomla 1.x, WordPress 1-3, uCoz, FrontPage…) | +10 |
| Копирайт в футере устарел (© на 3+ года назад) | до +12 |
| Нет DOCTYPE / старый DOCTYPE (HTML4/XHTML) | +7 |
| Старый серверный софт (PHP 4/5, Apache 2.2, IIS 5-7) | до +6 |
| Старый jQuery (< 1.9) | +6 |
| Нет Open Graph / нет `@media` / нет favicon | +5 / +5 / +3 |

Итог обрезается до 100. Все сработавшие сигналы попадают в колонку
`signals`, чтобы было видно, *почему* сайт помечен как старый.

### Что вытаскивается из контактов (`scanner/contacts.py`)

Email, телефоны (нормализуются в `+7 ...`), соцсети (VK, Telegram,
Instagram, WhatsApp, OK…), ИНН, ОГРН, название компании и ссылка на
страницу «Контакты».

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Запуск

> Поиск идёт через официальные API Яндекса и Google — для них нужны ключи
> (см. раздел «Поисковые провайдеры» ниже). Без ключей бот подскажет, что
> задать, и вернёт пустой список.

По одному запросу:

```bash
python -m scanner --query "стоматология Казань" --top 15
```

По списку запросов из файла (см. `queries.example.txt`):

```bash
python -m scanner --queries-file queries.example.txt --out out/kazan
```

Генерация «категория × город»:

```bash
python -m scanner \
  --category "автосервис" --category "натяжные потолки" \
  --city "Казань" --city "Челны" \
  --max-per-query 20 --min-score 30 --out out/leads
```

Результат — `out/leads.csv` (открывается в Excel/Google Sheets, кодировка
UTF-8 BOM) и `out/leads.json`. Лиды отсортированы по `outdated_score`.

### Основные флаги

| Флаг | Назначение |
|---|---|
| `-q, --query` | поисковый запрос (можно несколько раз) |
| `--queries-file` | файл со списком запросов |
| `--category` / `--city` | генерируют запросы «категория город» |
| `--provider` | движок поиска, можно несколько раз: `yandex`, `google`, `serpapi_google`, `serpapi_yandex`, `duckduckgo` (по умолчанию `yandex` + `google`) |
| `--max-per-query` | сколько результатов брать на запрос (по умолчанию 20) |
| `--concurrency` | параллельных сканов (по умолчанию 8) |
| `--min-score` | не включать сайты с баллом ниже порога |
| `-o, --out` | базовое имя файлов вывода |
| `--top` | вывести топ-N в консоль |

## Поисковые провайдеры

По умолчанию бот опрашивает **Яндекс и Google** и объединяет их выдачу
(round-robin, дубли доменов убираются). Прямой скрапинг выдачи не
используется — оба движка быстро отдают капчу и банят по IP, поэтому только
официальные API.

### Google — Custom Search JSON API

1. Создай API-ключ: <https://developers.google.com/custom-search/v1/overview>
2. Создай Programmable Search Engine и включи «Search the entire web»:
   <https://programmablesearchengine.google.com/> — получишь `cx`.
3. Задай переменные окружения:
   ```bash
   export GOOGLE_API_KEY=...      # ключ
   export GOOGLE_CSE_CX=...       # id поисковой системы (cx)
   ```
   Бесплатно — 100 запросов/день.

### Яндекс — Search API / XML

Вариант А (Yandex Cloud, актуальный): <https://yandex.cloud/ru/docs/search-api/>
```bash
export YANDEX_API_KEY=...         # API-ключ сервисного аккаунта
export YANDEX_FOLDER_ID=...       # id каталога в облаке
```
Вариант Б (классический Яндекс.XML): <https://yandex.ru/dev/xml/>
```bash
export YANDEX_XML_USER=...        # логин
export YANDEX_XML_KEY=...         # ключ
```

### SerpAPI — турнкей на оба движка

Если не хочешь возиться с двумя API — SerpAPI умеет и Google, и Яндекс:
```bash
export SERPAPI_KEY=...
python -m scanner --provider serpapi_yandex --provider serpapi_google -q "..."
```

### Выбор провайдеров вручную

```bash
# только Яндекс
python -m scanner --provider yandex -q "стоматология Казань"
# Яндекс + Google (то же, что по умолчанию)
python -m scanner --provider yandex --provider google -q "стоматология Казань"
```

## Тесты

```bash
pip install pytest
python -m pytest -q
```

Тесты покрывают эвристики, извлечение контактов и полный прогон конвейера
на моках (без обращения к сети).

## Замечания и планы

- Скан идёт по «сырому» HTML через `requests`. Сайты на чистом JS-рендере
  (SPA) распознаются хуже — под это можно подключить Playwright
  (headless-браузер) отдельным фетчером.
- Оценку оборота компании по ИНН/ОГРН (как в исходной идее) можно добавить
  отдельным обогащением через API реестров — сейчас ИНН/ОГРН только
  извлекаются со страницы.
- Соблюдай приличия: не долби сайты в тысячу потоков, уважай частоту
  запросов у поисковика. Инструмент для B2B-лидогенерации, а не для нагрузки.
```

## Структура

```
scanner/
  __main__.py    CLI
  search.py      поисковые провайдеры (DuckDuckGo / Google CSE / SerpAPI)
  fetcher.py     загрузка страниц
  heuristics.py  оценка устаревания дизайна
  contacts.py    извлечение контактов
  pipeline.py    оркестрация поиск→скан→ранжирование
  report.py      выгрузка CSV / JSON
  models.py      модели данных
tests/           pytest
```
