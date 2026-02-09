# Загрузка на Git и деплой на сервер

## Что сделано в проекте

- Удалены неиспользуемые сервисы: `inpainting.py`, `qwen_service.py`, `simple_composite.py`, `inpainting_factory.py` (используется только Nano Banana Pro).
- Обновлён README под текущий стек (Gemini 2.5 Pro + Nano Banana Pro).
- В .gitignore добавлены `.cursor/` и `*.code-workspace`.

---

## 1. Закоммитить и запушить на GitHub

В терминале из корня проекта:

```bash
cd "/Users/ilyshalit/Desktop/Примерка мебели"

# Все нужные файлы уже добавлены в индекс (git add выполнен)
git commit -m "Gemini base64, Nano Banana один вызов коллаж, каталог, тест Kie API, удалены старые сервисы"

git push origin main
```

Если попросит логин/пароль — используйте GitHub логин и **Personal Access Token** (не пароль от аккаунта).  
Или настройте SSH и замените remote на `git@github.com:ilyshalit/mebel1.git`.

---

## 2. На сервере (VDS)

Подключитесь по SSH, перейдите в папку приложения и подтяните изменения:

```bash
ssh root@<IP_ВАШЕГО_СЕРВЕРА>

cd /root/app   # или путь, где у вас клонирован репозиторий

git pull origin main
```

Если проект на сервер ещё не клонирован:

```bash
git clone https://github.com/ilyshalit/mebel1.git app
cd app
```

Создайте на сервере файл `.env` (его нет в git):

```bash
nano .env
```

Вставьте те же переменные, что и локально (KIE_AI_API_KEY, IMGBB_API_KEY и т.д.). Сохраните (Ctrl+O, Enter, Ctrl+X).

Запуск через Docker (если используете):

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Или по инструкции из `DEPLOY_PROD.md` (без Docker — через venv и uvicorn).

---

## 3. Проверка

- Сайт: https://mebel1.ru (или ваш домен)
- API доки: https://mebel1.ru/docs (если проксируете к backend)

После `git push` и `git pull` на сервере приложение будет с актуальным кодом (коллаж мебели, base64 для Gemini, каталог, тест API).
