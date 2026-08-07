# Образ прототипа клиента, собранного в Lovable.
#
# Файл лежит здесь, а не в репозитории прототипа, намеренно: тот репозиторий
# двусторонне синхронизирован с Lovable, и всё лишнее в нём рано или поздно
# попадёт в чужую сборку или будет затёрто. Собирать так:
#
#   docker build -t proto-<имя> -f deploy/prototype/Dockerfile <путь-к-прототипу>
#
# Ключевое место — NITRO_PRESET. Lovable собирает проект под Cloudflare, и
# такой вывод обычным node не запускается: `node .output/server/index.mjs`
# падает на ERR_MODULE_NOT_FOUND. Пресет переключается переменной окружения,
# поэтому vite.config.ts трогать не нужно — иначе сломается превью в Lovable.

FROM oven/bun:1 AS build
WORKDIR /app

# Зависимости отдельным слоем — кэшируется между сборками
COPY package.json bun.lock* ./
RUN bun install --frozen-lockfile

COPY . .
ENV NITRO_PRESET=node-server
RUN bun run build

# Готовую сборку запускает node: в рантайме bun не нужен, образ легче
FROM node:22-slim AS run
WORKDIR /app
COPY --from=build /app/.output ./.output

ENV NODE_ENV=production \
    HOST=0.0.0.0 \
    PORT=3000
EXPOSE 3000

# Свой пользователь: наружу торчит Caddy, но лишний root в контейнере не нужен
RUN useradd -m app && chown -R app:app /app
USER app

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", ".output/server/index.mjs"]
