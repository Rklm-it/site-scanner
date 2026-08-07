# Прототипы клиентов на своём сервере

Прототип, собранный в Lovable, живёт по адресу вида `…lovable.app`. Показывать
клиенту такую ссылку можно, но свой домен выглядит солиднее, не зависит от
чужого сервиса и не пропадёт, когда проект в Lovable переделают под
следующего клиента.

Здесь — как выложить прототип на свой VPS рядом со сканером.

## Разово: домен

Заведите поддомен и направьте его A-записью на IP сервера. Например
`pd.nexus-flow.ru` для `projekt-doma.ru`. Сертификат Caddy выпустит сам.

Один поддомен на клиента — так их не перепутать, и каждый можно погасить
отдельно, когда сделка закрыта.

## Выкладка

```bash
cd /root/site-scanner-main
./deploy/prototype/deploy.sh projekt-doma https://github.com/Rklm-it/project-house-design.git
```

Скрипт склонирует репозиторий прототипа в `/root/prototypes/projekt-doma`,
соберёт образ и поднимет контейнер `proto-projekt-doma` в той же сети, где
работает Caddy.

**Обновить после правок в Lovable — та же команда.** Скрипт подтянет свежий
коммит, пересоберёт и перезапустит.

## Блок в Caddyfile

Один раз на каждый прототип, в конец `Caddyfile`:

```
pd.nexus-flow.ru {
	encode gzip
	header {
		Strict-Transport-Security "max-age=31536000"
		X-Content-Type-Options nosniff
		Referrer-Policy no-referrer
	}
	reverse_proxy proto-projekt-doma:3000
}
```

Пароля здесь **нет намеренно**: ссылку открывает клиент, и упереться в окно
авторизации он не должен. В отличие от панели сканера, где пароль обязателен —
там телефоны, ключи и почта.

`X-Frame-Options` тоже не ставим: прототип иногда удобно показать во фрейме.

После правки перечитать конфиг без простоя:

```bash
docker compose exec caddy caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
docker compose exec caddy caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile
```

Сначала `validate`: если Caddy не примет конфиг, `reload` не тронет рабочий,
и панель сканера не ляжет.

## Почему так, а не иначе

**Почему не статикой.** Nitro умеет пресет `static`, но сборка Lovable с ним
падает: `rolldownOptions.input should not be an html file when building for
SSR`. Пресет `node-server` работает, и заодно страница приезжает клиенту
готовой разметкой — 30 КБ со всем текстом, а не пустой оболочкой. Для сайта,
который потом будут индексировать, это правильнее.

**Почему переменная окружения, а не правка конфига.** Lovable собирает проект
под Cloudflare, и `node .output/server/index.mjs` на таком выводе падает с
`ERR_MODULE_NOT_FOUND`. Чинится переключением пресета — но если поменять
`vite.config.ts`, изменение уедет обратно в Lovable и сломает превью.
`NITRO_PRESET` задаётся только в момент сборки образа и в репозиторий не
попадает.

**Почему не добавили сервис в общий `docker-compose.yml`.** Прототипов будет
по одному на клиента, и каждый в своём репозитории. Дописывать сервис на
каждого — значит на каждого править файл, который отвечает за боевой сканер.
Отдельный скрипт с параметром безопаснее.

## Снять прототип

Когда сделка закрыта или клиент отказался:

```bash
docker rm -f proto-projekt-doma
rm -rf /root/prototypes/projekt-doma
```

И убрать блок из `Caddyfile` с последующим `reload`.
