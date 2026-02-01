# 📡 API Документация

REST API для системы виртуальной примерки мебели.

## Базовый URL

```
http://localhost:8000
```

## Интерактивная документация

FastAPI автоматически генерирует интерактивную документацию:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

---

## 📤 Endpoints

### 1. Загрузка фото комнаты

**POST** `/api/upload/room`

Загружает и сохраняет фото комнаты.

**Request:**
```http
POST /api/upload/room
Content-Type: multipart/form-data

file: <image file>
```

**Response:**
```json
{
  "success": true,
  "file_path": "/path/to/saved/room.png",
  "filename": "abc123.png"
}
```

**cURL пример:**
```bash
curl -X POST http://localhost:8000/api/upload/room \
  -F "file=@room.jpg"
```

---

### 2. Загрузка фото мебели

**POST** `/api/upload/furniture`

Загружает фото мебели и автоматически удаляет фон.

**Request:**
```http
POST /api/upload/furniture
Content-Type: multipart/form-data

file: <image file>
```

**Response:**
```json
{
  "success": true,
  "file_path": "/path/to/furniture_no_bg.png",
  "filename": "def456.png",
  "background_removed": true
}
```

**cURL пример:**
```bash
curl -X POST http://localhost:8000/api/upload/furniture \
  -F "file=@sofa.jpg"
```

---

### 3. Генерация результата

**POST** `/api/generate`

Генерирует изображение с размещенной мебелью.

**Request:**
```http
POST /api/generate
Content-Type: application/x-www-form-urlencoded

room_image_path: /path/to/room.png
furniture_image_path: /path/to/furniture.png
mode: auto
manual_x: (optional) 300
manual_y: (optional) 450
```

**Parameters:**
- `room_image_path` (string, required) - Путь к комнате из upload/room
- `furniture_image_path` (string, required) - Путь к мебели из upload/furniture
- `mode` (string, optional) - "auto" или "manual" (default: "auto")
- `manual_x` (integer, optional) - X координата для manual режима
- `manual_y` (integer, optional) - Y координата для manual режима

**Response:**
```json
{
  "success": true,
  "result_image_path": "/path/to/result.png",
  "result_image_url": "/results/result123.png",
  "generation_time": 12.5,
  "analysis": {
    "room_analysis": { ... },
    "furniture_analysis": { ... },
    "placement": { ... }
  }
}
```

**cURL пример:**
```bash
curl -X POST http://localhost:8000/api/generate \
  -F "room_image_path=/path/to/room.png" \
  -F "furniture_image_path=/path/to/furniture.png" \
  -F "mode=auto"
```

---

### 4. Получить каталог мебели

**GET** `/api/catalog`

Возвращает список всех товаров в каталоге.

**Request:**
```http
GET /api/catalog
```

**Response:**
```json
{
  "success": true,
  "items": [
    {
      "id": "uuid-123",
      "name": "Диван 'Скандинавия'",
      "type": "диван",
      "style": "современный",
      "image_path": "/path/to/image.png",
      "image_url": "/catalog/image.png",
      "description": "Удобный диван...",
      "price": 45000
    }
  ]
}
```

---

### 5. Добавить товар в каталог

**POST** `/api/catalog`

Добавляет новый товар в каталог.

**Request:**
```http
POST /api/catalog
Content-Type: multipart/form-data

name: Диван 'Лофт'
item_type: диван
style: лофт
file: <image file>
description: (optional) Стильный диван
price: (optional) 55000
```

**Response:**
```json
{
  "success": true,
  "item": {
    "id": "uuid-456",
    "name": "Диван 'Лофт'",
    "type": "диван",
    "style": "лофт",
    "image_path": "/path/to/image.png",
    "image_url": "/catalog/image.png",
    "description": "Стильный диван",
    "price": 55000
  }
}
```

**cURL пример:**
```bash
curl -X POST http://localhost:8000/api/catalog \
  -F "name=Диван 'Лофт'" \
  -F "item_type=диван" \
  -F "style=лофт" \
  -F "file=@sofa.jpg" \
  -F "price=55000"
```

---

### 6. Удалить товар из каталога

**DELETE** `/api/catalog/{item_id}`

Удаляет товар из каталога.

**Request:**
```http
DELETE /api/catalog/{item_id}
```

**Response:**
```json
{
  "success": true,
  "message": "Товар удален"
}
```

---

### 7. Получить рекомендации (upsell)

**POST** `/api/upsell`

Возвращает рекомендации дополнительных товаров.

**Request:**
```http
POST /api/upsell
Content-Type: application/x-www-form-urlencoded

furniture_analysis: {"type": "диван", "style": "современный"}
room_analysis: {"style": "минимализм"}
```

**Response:**
```json
{
  "success": true,
  "recommendations": [
    {
      "id": "uuid-789",
      "name": "Журнальный столик",
      "recommendation_reason": "Отлично дополнит диван",
      "recommendation_category": "функциональное дополнение",
      "image_url": "/catalog/table.png",
      "price": 15000
    }
  ]
}
```

---

### 8. Проверка здоровья

**GET** `/api/health`

Проверяет работоспособность API и сервисов.

**Request:**
```http
GET /api/health
```

**Response:**
```json
{
  "status": "healthy",
  "services": {
    "gpt4_vision": "ready",
    "background_removal": "ready",
    "inpainting": "ready",
    "upsell": "ready"
  }
}
```

---

## 🔒 Аутентификация

В текущей версии (Вариант A) аутентификация не требуется.

Для продакшена рекомендуется добавить:
- JWT токены
- API ключи
- Rate limiting

---

## ⚠️ Коды ошибок

| Код | Описание |
|-----|----------|
| 200 | Успешно |
| 400 | Неверный запрос |
| 404 | Ресурс не найден |
| 500 | Внутренняя ошибка сервера |

**Формат ошибки:**
```json
{
  "detail": "Описание ошибки"
}
```

---

## 💡 Примеры использования

### Python

```python
import requests

# Загрузка комнаты
with open('room.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/upload/room',
        files={'file': f}
    )
    room_path = response.json()['file_path']

# Загрузка мебели
with open('sofa.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/api/upload/furniture',
        files={'file': f}
    )
    furniture_path = response.json()['file_path']

# Генерация
response = requests.post(
    'http://localhost:8000/api/generate',
    data={
        'room_image_path': room_path,
        'furniture_image_path': furniture_path,
        'mode': 'auto'
    }
)

result = response.json()
print(f"Результат: {result['result_image_url']}")
print(f"Время: {result['generation_time']}с")
```

### JavaScript (fetch)

```javascript
// Загрузка комнаты
const formData = new FormData();
formData.append('file', roomFile);

const response = await fetch('http://localhost:8000/api/upload/room', {
    method: 'POST',
    body: formData
});

const data = await response.json();
console.log('Room uploaded:', data.file_path);
```

---

## 📊 Rate Limits

В текущей версии rate limits нет.

Для продакшена рекомендуется:
- 100 запросов/час на IP
- 1000 запросов/день на пользователя

---

**Документация обновлена:** 2026-01-29
