# Чеклист перед обновлением сервера

Проверено локально перед деплоем:

- [x] **Caddyfile** — синтаксис валиден (`caddy validate`), отформатирован (`caddy fmt`)
- [x] **Доступ по IP** — блок `95.81.123.106` для HTTP без SSL
- [x] **Домен** — блок `{$DOMAIN}` для HTTPS (когда DNS настроен)
- [x] **Backend (Dockerfile.light)** — образ собирается, контейнер стартует, `/api/health` отвечает
- [x] **Frontend** — есть `index.html`, `css/style.css`, `js/app.js`
- [x] **docker-compose.prod.yml** — backend + caddy, volumes для `.env`, `data`, `frontend`

На сервере перед обновлением убедись:

1. В `~/app/.env` есть: `OPENAI_API_KEY`, `KIE_AI_API_KEY`, `IMGBB_API_KEY`, `DOMAIN=mebel1.ru`
2. После `git pull` выполни: `docker compose -f docker-compose.prod.yml up -d --build`
3. Проверь: `http://95.81.123.106` (по IP), затем при настроенном DNS — `https://mebel1.ru`
