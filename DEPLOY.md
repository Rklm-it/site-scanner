# Развёртывание на VPS (Docker)

Схема: контейнер `app` (веб-интерфейс) наружу не публикуется, доступен только
внутри docker-сети. Наружу торчит `caddy` — он даёт **HTTPS** (сам выпускает и
продлевает сертификат) и **пароль** (basic-auth). Данные (кэш, ключи,
результаты) лежат на постоянном томе и переживают перезапуски и обновления.

## 1. Сервер

Подойдёт самый дешёвый VPS: 1–2 ГБ RAM, Ubuntu 22.04. Для рунет-сервисов
удобнее РФ-провайдер (Timeweb Cloud, Selectel, Beget, reg.ru).

Открой порты (если есть firewall):
```bash
sudo ufw allow 22,80,443/tcp && sudo ufw enable
```

(Опционально) Если есть домен — заведи A-запись на IP сервера. Без домена
тоже можно, будет доступ по IP без HTTPS (см. шаг 4).

## 2. Docker

```bash
curl -fsSL https://get.docker.com | sh
```
В комплекте идёт плагин `docker compose`.

## 3. Код

```bash
git clone https://github.com/Rklm-it/site-scanner.git
cd site-scanner
```

## 4. Настройка (scanner.env)

```bash
cp scanner.env.example scanner.env
```

> Файл называется `scanner.env`, а **не** `.env` — намеренно.

Проще всего сгенерировать всё одной командой — она создаёт хэш пароля и
корректно записывает его в `scanner.env` (удваивая `$`, как того требует
docker compose):

```bash
DOMAIN=scanner.example.com          # или :80, если домена нет
PASSWORD='ПРИДУМАЙ_ПАРОЛЬ'
HASH=$(docker run --rm caddy caddy hash-password --plaintext "$PASSWORD")
printf 'DOMAIN=%s\nBASIC_AUTH_USER=admin\nBASIC_AUTH_HASH=%s\n' \
  "$DOMAIN" "${HASH//\$/\$\$}" > scanner.env
cat scanner.env
```

Поля:
- `DOMAIN` — твой домен (`scanner.example.com`) для авто-HTTPS.
  **Нет домена?** Поставь `:80` — доступ по `http://IP-сервера` (под паролем,
  но без шифрования — для теста ок).
- `BASIC_AUTH_USER` — логин (в примере `admin`).
- `BASIC_AUTH_HASH` — хэш с **удвоенными** `$` (команда выше делает это сама).
  Если правишь вручную — замени каждый `$` на `$$`, иначе compose испортит хэш
  и вход не сработает.

## 5. Запуск

```bash
docker compose up -d --build
```

Открой `https://твой-домен` (или `http://IP`), введи логин/пароль — попадёшь
в интерфейс. Дальше в панели **«API-ключи»** введи ключи Яндекса/Google
(и DaData, если нужен оборот) — они сохранятся на томе.

Логи:
```bash
docker compose logs -f app
```

## 6. Обновление

```bash
git pull
docker compose up -d --build
```
Данные и ключи на томе `scanner-data` сохранятся.

## 7. Бэкап данных

Всё ценное (ключи, кэш, результаты) — в томе `scanner-data`:
```bash
docker run --rm -v site-scanner_scanner-data:/data -v "$PWD":/backup \
  busybox tar czf /backup/scanner-backup.tgz -C /data .
```

## Заметки

- **Один процесс — намеренно.** Список задач скана хранится в памяти
  процесса, поэтому масштабировать `app` в несколько реплик нельзя (браузер
  при опросе попадёт «не в ту» реплику). Для одного-двух пользователей это
  не проблема. Понадобится масштаб — выносим задачи в БД/очередь.
- **Не выставляй `app` напрямую в интернет** без Caddy — там нет своей
  авторизации, видны твои ключи и лиды.
- Ресурсы: базовый образ лёгкий. Playwright-рендер для SPA (из планов) в
  образ не входит — добавим отдельным слоем, когда понадобится.
