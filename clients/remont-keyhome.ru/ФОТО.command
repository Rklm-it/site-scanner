#!/usr/bin/env bash
#
# Забрать оригиналы фотографий сайта «Баланс» с сервера Tilda.
#
# Запуск: двойным щелчком в Finder или `bash ФОТО.command`.
# Файлы лягут в папку foto/ рядом с этим скриптом — то есть сразу в
# репозиторий, останется только закоммитить.
#
# Почему это нельзя сделать из сессии: песочница не пускает к
# static.tildacdn.com, прокси отдаёт 403. Команду выполняет владелец.
#
# Имя файла берём из адреса (tild3034-…), а не из хвоста: на сайте половина
# снимков называется photo_2025-11-26_10-.jpg, и по именам они затрут друг
# друга.
#
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p foto

ok=0; fail=0
while read -r u; do
    [ -z "$u" ] && continue
    n="$(echo "$u" | sed -E 's#.*/(tild[^/]+)/.*#\1#').${u##*.}"
    if curl -sSfL --max-time 30 "$u" -o "foto/$n"; then
        echo "ок  $n"; ok=$((ok+1))
    else
        echo "НЕТ $u"; fail=$((fail+1))
    fi
done <<'URLS'
https://static.tildacdn.com/tild3034-3633-4030-a530-366631383734/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3132-3061-4938-a436-613330343166/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3132-3661-4063-a566-336365326337/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3132-6439-4435-b238-336364633137/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3233-3537-4632-a565-303634373633/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3237-3262-4461-b261-663836383361/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3261-3666-4731-b738-393661653336/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3263-3935-4735-b934-346133323365/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3265-3164-4832-b634-623033396364/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3337-3430-4563-a564-313462636435/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3431-3635-4138-a431-643337626130/123.jpeg
https://static.tildacdn.com/tild3436-6164-4632-b030-636139376634/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3438-6234-4961-b930-343263663263/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3536-6230-4632-b932-346537366166/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3539-3735-4831-b136-316330376330/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3636-3433-4234-a366-373534313031/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3662-6561-4434-b438-353930346536/b52bd162bf4411f0a200.jpeg
https://static.tildacdn.com/tild3663-6362-4239-b831-393863343062/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3665-3335-4838-b464-306330326434/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3737-6332-4830-a362-336465646138/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3762-6437-4836-b836-313162613732/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3764-6537-4333-b232-386562626631/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3838-3261-4934-b931-306436363062/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3861-6362-4865-b732-373861363230/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild3934-3031-4764-b131-623462383563/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild3962-3830-4265-b566-316435343731/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild6130-6363-4233-b331-376436323236/11111111111.jpeg
https://static.tildacdn.com/tild6161-6237-4366-b162-663236623036/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild6163-3832-4236-b230-343430623339/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild6361-3836-4164-b733-636230663966/0ec085d4bf4911f08898.jpeg
https://static.tildacdn.com/tild6463-6363-4630-a666-386163666137/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild6532-6234-4864-b434-626166393539/510371a1bf4a11f0b6cf.jpeg
https://static.tildacdn.com/tild6539-3361-4138-b461-646263393036/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild6562-3362-4534-b231-336134623236/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild6565-3664-4362-b739-346533343462/photo_2025-11-27_21-.jpg
https://static.tildacdn.com/tild6638-6664-4335-b237-393962386262/photo_2025-11-26_10-.jpg
https://static.tildacdn.com/tild6664-6636-4734-b662-383337353530/photo_2025-11-26_10-.jpg
URLS

echo
echo "Скачано: $ok, не отдали: $fail. Объём: $(du -sh foto | cut -f1)"
echo
echo "Проверьте размеры: настоящие фото — сотни килобайт."
echo "Если файл на 1–2 КБ, это опять заглушка."
ls -lS foto | head -6
echo
echo "Дальше: git add clients/remont-keyhome.ru/foto && git commit && git push"
