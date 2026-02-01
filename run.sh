#!/bin/bash

echo "🚀 Запуск серверов..."

# Переходим в директорию проекта
cd "/Users/ilyshalit/Desktop/Примерка мебели"

# Проверка .env
if [ ! -f .env ]; then
    echo "❌ Файл .env не найден!"
    exit 1
fi

echo "✅ Файл .env найден"

# Запуск backend
echo "🔧 Запуск backend на порту 8000..."
cd backend
python3 -m uvicorn app:app --reload --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "✅ Backend запущен (PID: $BACKEND_PID)"

# Ждем
sleep 3

# Запуск frontend
echo "🌐 Запуск frontend на порту 8080..."
cd ../frontend
python3 -m http.server 8080 &
FRONTEND_PID=$!
echo "✅ Frontend запущен (PID: $FRONTEND_PID)"

echo ""
echo "✅ Серверы запущены!"
echo "📱 Откройте в браузере: http://localhost:8080"
echo "📡 API: http://localhost:8000"
echo ""
echo "Для остановки: kill $BACKEND_PID $FRONTEND_PID"
echo ""

# Сохраняем PIDs в файл
echo "$BACKEND_PID" > /tmp/furniture_backend.pid
echo "$FRONTEND_PID" > /tmp/furniture_frontend.pid

echo "PIDs сохранены в /tmp/furniture_*.pid"
