# 🚀 Деплой на Ubuntu (IHOR VDS) + HTTPS (Caddy)

Этот гайд делает сайт доступным **с любого устройства** по `https://<DOMAIN>`.

## 0) Что нужно заранее

- Ubuntu 20.04/22.04 на VDS (у вас `amd64`)
- Домен (например `mebel1.ru`)
- DNS A‑record: `mebel1.ru` → публичный IP VDS
- Открытые порты в firewall провайдера/сервера: **80** и **443**

## 1) Подключение к серверу

Подключитесь по SSH (логин/пароль/ключ даст провайдер):

```bash
ssh root@<SERVER_IP>
```

## 2) Установка Docker + Compose

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg

sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo \"$VERSION_CODENAME\") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
```

Проверка:

```bash
docker --version
docker compose version
```

## 3) Залить проект на сервер

### Вариант A (рекомендуется): через GitHub
1) Создайте репозиторий на GitHub
2) Залейте туда проект (без `.env`)
3) На сервере:

```bash
git clone <REPO_URL> app
cd app
```

### Вариант B: через SCP (быстро)
На Mac:

```bash
scp -r "/Users/ilyshalit/Desktop/Примерка мебели" root@<SERVER_IP>:/root/app
```

На сервере:

```bash
cd /root/app
```

## 4) Создать `.env` на сервере (важно)

`.env` **не хранить** в git. На сервере создайте вручную:

```bash
nano .env
```

Нужно минимум:

```env
OPENAI_API_KEY=...
KIE_AI_API_KEY=...
IMGBB_API_KEY=...
DOMAIN=mebel1.ru
```

## 5) Запуск production compose (Caddy выдаст HTTPS)

```bash
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
```

## 6) Проверка

- Сайт: `https://mebel1.ru`
- Логи:

```bash
docker compose -f docker-compose.prod.yml logs -f caddy
docker compose -f docker-compose.prod.yml logs -f backend
```

## 7) Обновление

Если код обновили:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

