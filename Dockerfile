# Dockerfile для backend
FROM python:3.11-slim

WORKDIR /app

# Установка системных зависимостей для обработки изображений
RUN apt-get update && apt-get install -y \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libgthread-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Копируем requirements
COPY backend/requirements.txt /app/requirements.txt

# Устанавливаем Python зависимости
RUN pip install --no-cache-dir -r /app/requirements.txt

# Копируем backend код как пакет /app/backend
COPY backend/ /app/backend/

# Создаем директории для данных
RUN mkdir -p /app/data/uploads /app/data/results /app/data/catalog

# Expose port
EXPOSE 8000

# Команда запуска
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
