"""
FastAPI приложение для виртуальной примерки мебели
"""
import time
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

# Проверяем откуда запускается приложение
import sys
from pathlib import Path

# Добавляем корневую директорию в путь поиска модулей
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Импорты - теперь всегда работают из корня проекта
from backend.services.gpt4_analyzer import GPT4Analyzer
from backend.services.background_remover import BackgroundRemover
from backend.services.nano_banana import NanoBananaService
from backend.services.upsell import UpsellService
from backend.utils.image_utils import save_uploaded_image
from backend.utils.load_env import load_environment
from backend.models.schemas import (
    CatalogItem,
    ErrorResponse
)

# Загружаем переменные окружения
load_environment()

# Инициализация FastAPI
app = FastAPI(
    title="Furniture Placement API",
    description="AI-powered виртуальная примерка мебели",
    version="1.0.0"
)

# CORS middleware для работы с frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Директории (BASE_DIR уже определен выше)
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
RESULTS_DIR = DATA_DIR / "results"
CATALOG_DIR = DATA_DIR / "catalog"

# Создаем директории если не существуют
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_DIR.mkdir(parents=True, exist_ok=True)

# Монтируем статические файлы
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")
app.mount("/catalog", StaticFiles(directory=str(CATALOG_DIR)), name="catalog")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Инициализация сервисов
gpt4_analyzer = GPT4Analyzer()
background_remover = BackgroundRemover(use_api=False)  # Используем rembg
inpainting_service = NanoBananaService()
upsell_service = UpsellService()

# Временное хранилище каталога (в продакшене использовать БД)
CATALOG_ITEMS: List[Dict[str, Any]] = []


@app.get("/")
async def root():
    """Главная страница API"""
    return {
        "message": "🛋️ Furniture Placement API",
        "version": "1.0.0",
        "endpoints": {
            "upload_room": "/api/upload/room",
            "upload_furniture": "/api/upload/furniture",
            "generate": "/api/generate",
            "catalog": "/api/catalog",
            "upsell": "/api/upsell"
        }
    }


@app.post("/api/upload/room")
async def upload_room(file: UploadFile = File(...)):
    """
    Загрузка фото комнаты
    """
    try:
        # Проверка типа файла
        if not file.content_type.startswith('image/'):
            raise HTTPException(400, "Файл должен быть изображением")
        
        # Сохраняем изображение
        image_data = await file.read()
        file_path = save_uploaded_image(image_data, UPLOADS_DIR)
        
        return {
            "success": True,
            "file_path": file_path,
            "filename": Path(file_path).name
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@app.post("/api/upload/furniture")
async def upload_furniture(file: UploadFile = File(...)):
    """
    Загрузка фото мебели и удаление фона
    """
    try:
        # Проверка типа файла
        if not file.content_type.startswith('image/'):
            raise HTTPException(400, "Файл должен быть изображением")
        
        # Сохраняем изображение
        image_data = await file.read()
        file_path = save_uploaded_image(image_data, UPLOADS_DIR)
        
        # Удаляем фон
        print(f"🔄 Удаление фона с мебели...")
        furniture_no_bg = background_remover.remove_background(file_path)
        
        return {
            "success": True,
            "file_path": furniture_no_bg,
            "filename": Path(furniture_no_bg).name,
            "background_removed": True
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


@app.post("/api/generate")
async def generate_placement(
    room_image_path: str = Form(...),
    furniture_image_path: str = Form(...),
    mode: str = Form(default="auto"),
    # manual bbox (в пикселях исходного изображения комнаты)
    manual_box_x: Optional[int] = Form(None),
    manual_box_y: Optional[int] = Form(None),
    manual_box_w: Optional[int] = Form(None),
    manual_box_h: Optional[int] = Form(None),
    # совместимость со старым manual кликом
    manual_x: Optional[int] = Form(None),
    manual_y: Optional[int] = Form(None),
    # поворот мебели: 0 или 90 градусов
    furniture_rotation: int = Form(default=0),
    # вдоль какой стены ставить (auto/right/left/back)
    wall_alignment: str = Form(default="auto")
):
    """
    Генерация результата с размещенной мебелью
    
    Modes:
    - auto: AI сам выбирает лучшее место
    - manual: Пользователь указывает позицию (manual_x, manual_y)
    
    Используется Nano Banana Pro (Google DeepMind) через Kie.ai.
    """
    try:
        start_time = time.time()
        
        # Формируем manual position если указан
        manual_position = None
        manual_box = None
        if mode == "manual":
            # Новый режим: прямоугольник (bbox)
            if None not in (manual_box_x, manual_box_y, manual_box_w, manual_box_h):
                manual_box = (manual_box_x, manual_box_y, manual_box_w, manual_box_h)
                manual_position = (manual_box_x + manual_box_w // 2, manual_box_y + manual_box_h // 2)
            # Старый режим: клик по точке
            elif manual_x is not None and manual_y is not None:
                manual_position = (manual_x, manual_y)
        
        # Шаг 1: Анализ с GPT-4V
        print(f"🔍 Анализ изображений с GPT-4 Vision...")
        analysis = gpt4_analyzer.analyze_placement(
            room_image_path,
            furniture_image_path,
            manual_position
        )

        # Если пользователь указал прямоугольник — жестко задаём placement по нему
        if manual_box is not None:
            from PIL import Image
            room_img = Image.open(room_image_path)
            rw, rh = room_img.size
            bx, by, bw, bh = manual_box
            # clamp на всякий случай
            bx = max(0, min(bx, rw - 1))
            by = max(0, min(by, rh - 1))
            bw = max(1, min(bw, rw - bx))
            bh = max(1, min(bh, rh - by))
            analysis.setdefault("placement", {})
            analysis["placement"].update({
                "x_percent": ((bx + bw / 2) / rw) * 100,
                "y_percent": ((by + bh / 2) / rh) * 100,
                "width_percent": (bw / rw) * 100,
                "height_percent": (bh / rh) * 100,
                "rotation": 0,
                "reasoning": "User selected target rectangle (bbox). Place furniture inside this area."
            })

            # auto wall inference if not explicitly set
            if wall_alignment == "auto":
                left_margin = bx
                right_margin = rw - (bx + bw)
                top_margin = by
                # heuristic: choose nearest side; map top -> back wall
                m = min(left_margin, right_margin, top_margin)
                if m == right_margin:
                    wall_alignment = "right"
                elif m == left_margin:
                    wall_alignment = "left"
                else:
                    wall_alignment = "back"

        # Поворот мебели (0 или 90) — сохраняем в analysis для сервиса
        if furniture_rotation not in (0, 90):
            raise HTTPException(400, "furniture_rotation должен быть 0 или 90")
        analysis.setdefault("placement", {})
        analysis["placement"]["rotation"] = furniture_rotation
        analysis["placement"]["wall_alignment"] = wall_alignment
        
        # Шаг 2: Размещение мебели выбранной моделью
        print(f"🍌 Размещение мебели с помощью {inpainting_service.get_model_name()}...")
        result_path = inpainting_service.place_furniture(
            room_image_path,
            furniture_image_path,
            analysis,
            RESULTS_DIR
        )
        
        # Формируем URL для доступа к результату
        result_filename = Path(result_path).name
        result_url = f"/results/{result_filename}"
        
        generation_time = time.time() - start_time
        
        print(f"✅ Генерация завершена за {generation_time:.2f}с")
        
        return {
            "success": True,
            "result_image_path": result_path,
            "result_image_url": result_url,
            "generation_time": generation_time,
            "model_used": inpainting_service.get_model_name(),
            "preserves_original": inpainting_service.preserves_original(),
            "analysis": analysis
        }
        
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        raise HTTPException(500, f"Ошибка генерации: {str(e)}")


@app.post("/api/upsell")
async def get_upsell_recommendations(
    furniture_analysis: Dict[str, Any] = Form(...),
    room_analysis: Dict[str, Any] = Form(...)
):
    """
    Получить рекомендации дополнительных товаров
    """
    try:
        # Если каталог пуст, возвращаем пустой список
        if not CATALOG_ITEMS:
            return {
                "success": True,
                "recommendations": []
            }
        
        # Генерируем рекомендации
        recommendations = upsell_service.generate_recommendations(
            furniture_analysis,
            room_analysis,
            CATALOG_ITEMS,
            max_recommendations=4
        )
        
        return {
            "success": True,
            "recommendations": recommendations
        }
        
    except Exception as e:
        print(f"⚠️  Ошибка генерации рекомендаций: {e}")
        # В случае ошибки возвращаем простые рекомендации
        furniture_type = furniture_analysis.get('type', 'мебель')
        simple_recs = upsell_service.get_simple_recommendations(
            furniture_type,
            CATALOG_ITEMS,
            count=3
        )
        return {
            "success": True,
            "recommendations": simple_recs
        }


@app.get("/api/catalog")
async def get_catalog():
    """
    Получить каталог доступной мебели
    """
    return {
        "success": True,
        "items": CATALOG_ITEMS
    }


@app.post("/api/catalog")
async def add_catalog_item(
    name: str = Form(...),
    item_type: str = Form(...),
    style: str = Form(...),
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    price: Optional[float] = Form(None)
):
    """
    Добавить товар в каталог
    """
    try:
        # Сохраняем изображение
        image_data = await file.read()
        file_path = save_uploaded_image(image_data, CATALOG_DIR)
        
        # Удаляем фон
        file_path_no_bg = background_remover.remove_background(file_path)
        
        # Создаем запись в каталоге
        item_id = str(uuid.uuid4())
        catalog_item = {
            "id": item_id,
            "name": name,
            "type": item_type,
            "style": style,
            "image_path": file_path_no_bg,
            "image_url": f"/catalog/{Path(file_path_no_bg).name}",
            "description": description,
            "price": price
        }
        
        CATALOG_ITEMS.append(catalog_item)
        
        return {
            "success": True,
            "item": catalog_item
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка добавления в каталог: {str(e)}")


@app.delete("/api/catalog/{item_id}")
async def delete_catalog_item(item_id: str):
    """
    Удалить товар из каталога
    """
    global CATALOG_ITEMS
    
    # Находим товар
    item = next((i for i in CATALOG_ITEMS if i['id'] == item_id), None)
    
    if not item:
        raise HTTPException(404, "Товар не найден")
    
    # Удаляем файл
    try:
        Path(item['image_path']).unlink(missing_ok=True)
    except Exception as e:
        print(f"⚠️  Не удалось удалить файл: {e}")
    
    # Удаляем из каталога
    CATALOG_ITEMS = [i for i in CATALOG_ITEMS if i['id'] != item_id]
    
    return {
        "success": True,
        "message": "Товар удален"
    }


@app.get("/api/health")
async def health_check():
    """
    Проверка работоспособности API
    """
    return {
        "status": "healthy",
        "services": {
            "gpt4_vision": "ready",
            "background_removal": "ready",
            "inpainting": "ready",
            "upsell": "ready"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
