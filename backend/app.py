"""
FastAPI приложение для виртуальной примерки мебели
"""
import time
import uuid
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Header, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, Response

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
from backend.utils.load_env import load_environment, get_env_variable, get_env_optional
from backend.models.schemas import (
    CatalogItem,
    ErrorResponse
)
from backend import database as db

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


# Учёт визитов в SQLite (data/visits.db) — все обращения к /api/* кроме админки
@app.middleware("http")
async def log_visits_middleware(request, call_next):
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/api/") and not path.startswith("/api/admin/"):
        try:
            ip = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (request.client.host if request.client else "")
            ua = request.headers.get("user-agent", "")
            db.log_visit(ip or "?", ua, path, request.method)
        except Exception:
            pass
    return response

# Директории (BASE_DIR уже определен выше)
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
RESULTS_DIR = DATA_DIR / "results"
CATALOG_DIR = DATA_DIR / "catalog"
CATALOG_DB_FILE = DATA_DIR / "catalog.json"

# Создаем директории если не существуют
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_DIR.mkdir(parents=True, exist_ok=True)

# Загружаем каталог из файла
def load_catalog() -> List[Dict[str, Any]]:
    """Загружает каталог из JSON файла"""
    if CATALOG_DB_FILE.exists():
        try:
            with open(CATALOG_DB_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Ошибка загрузки каталога: {e}")
    return []

def save_catalog(items: List[Dict[str, Any]]):
    """Сохраняет каталог в JSON файл"""
    try:
        with open(CATALOG_DB_FILE, 'w', encoding='utf-8') as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️  Ошибка сохранения каталога: {e}")

# Загружаем каталог при старте
CATALOG_ITEMS: List[Dict[str, Any]] = load_catalog()

# Инициализация БД визитов (SQLite: data/visits.db)
db.init_db()


def resolve_furniture_path(path: str) -> str:
    """
    Преобразует путь к мебели в путь на текущей машине.
    В catalog.json могут быть абсолютные пути с другого ПК или относительные (catalog/xxx.png).
    """
    p = Path(path)
    if p.is_absolute() and p.exists():
        return str(p)
    # Относительный путь (catalog/xxx.png) или только имя файла
    for candidate in (DATA_DIR / path, CATALOG_DIR / p.name):
        if candidate.exists():
            return str(candidate)
    return str(path)

# Монтируем статические файлы
app.mount("/results", StaticFiles(directory=str(RESULTS_DIR)), name="results")
app.mount("/catalog", StaticFiles(directory=str(CATALOG_DIR)), name="catalog")
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")

# Инициализация сервисов
gpt4_analyzer = GPT4Analyzer()
background_remover = BackgroundRemover(use_api=False)  # Используем rembg
inpainting_service = NanoBananaService()
upsell_service = UpsellService()


@app.get("/")
async def root():
    """Главная страница API"""
    return {
        "message": "🛋️ Furniture Placement API",
        "version": "1.0.0",
        "endpoints": {
            "admin_visits": "/api/admin/visits",
            "upload_room": "/api/upload/room",
            "upload_furniture": "/api/upload/furniture",
            "analyze_room_replace": "/api/analyze-room-replace",
            "generate": "/api/generate",
            "catalog": "/api/catalog",
            "upsell": "/api/upsell"
        }
    }


@app.get("/api/admin/visits")
async def admin_get_visits(
    limit: int = Query(500, ge=1, le=2000),
    key: Optional[str] = Query(None),
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
):
    """
    Список визитов из БД (data/visits.db). Доступ по ключу ADMIN_API_KEY из .env.
    Передайте ключ в заголовке X-Admin-Key или в query: ?key=...
    """
    admin_key = get_env_optional("ADMIN_API_KEY")
    if not admin_key:
        raise HTTPException(503, "Учёт визитов отключён: не задан ADMIN_API_KEY в .env")
    provided = x_admin_key or key
    if provided != admin_key:
        raise HTTPException(403, "Неверный ключ доступа")
    visits = db.get_visits(limit=limit)
    return {"success": True, "visits": visits, "total": len(visits)}


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
async def upload_furniture(files: List[UploadFile] = File(...)):
    """
    Загрузка фото мебели (до 5 предметов) и удаление фона
    """
    try:
        # Ограничение на количество
        if len(files) > 5:
            raise HTTPException(400, "Максимум 5 предметов мебели за раз")
        
        results = []
        
        for file in files:
            # Проверка типа файла
            if not file.content_type.startswith('image/'):
                raise HTTPException(400, f"Файл {file.filename} должен быть изображением")
            
            # Сохраняем изображение
            image_data = await file.read()
            file_path = save_uploaded_image(image_data, UPLOADS_DIR)
            
            # Удаляем фон
            print(f"🔄 Удаление фона с мебели {file.filename}...")
            furniture_no_bg = background_remover.remove_background(file_path)
            
            results.append({
                "file_path": furniture_no_bg,
                "filename": Path(furniture_no_bg).name,
                "background_removed": True
            })
        
        return {
            "success": True,
            "items": results,
            "count": len(results)
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка загрузки: {str(e)}")


def resolve_room_path(path: str) -> str:
    """Путь к фото комнаты: абсолютный или относительно data/uploads."""
    p = Path(path)
    if p.is_absolute() and p.exists():
        return str(p)
    for candidate in (DATA_DIR / path, UPLOADS_DIR / p.name):
        if candidate.exists():
            return str(candidate)
    return str(path)


@app.post("/api/analyze-room-replace")
async def analyze_room_for_replace(room_image_path: str = Form(...)):
    """
    Анализирует фото комнаты и возвращает список мебели, которую можно заменить
    (диван, стол, кресло и т.д.). Используется в режиме «Заменить мебель».
    """
    try:
        room_path = resolve_room_path(room_image_path)
        result = gpt4_analyzer.analyze_room_for_replace(room_path)
        return result
    except Exception as e:
        raise HTTPException(500, f"Ошибка анализа комнаты: {str(e)}")


TRIAL_LIMIT = int(get_env_optional("TRIAL_LIMIT") or "3")


@app.post("/api/generate")
async def generate_placement(
    request: Request,
    room_image_path: str = Form(...),
    furniture_image_paths: str = Form(...),  # JSON array строка
    mode: str = Form(default="auto"),
    # placement_mode: "place" — разместить в пустом месте, "replace" — заменить мебель в комнате
    placement_mode: str = Form(default="place"),
    # replace_what: что именно заменить (например "sofa on the left") — из анализа комнаты
    replace_what: Optional[str] = Form(None),
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
    Генерация: размещение мебели (place) или замена мебели в комнате (replace).
    placement_mode=replace: комната со старой мебелью + один новый предмет → замена.
    """
    try:
        import json
        client_ip = (request.headers.get("x-forwarded-for") or "").strip().split(",")[0].strip() or (request.client.host if request.client else "")
        used = db.get_generate_count(client_ip)
        if used >= TRIAL_LIMIT:
            raise HTTPException(
                403,
                f"Пробный период: использовано {used} из {TRIAL_LIMIT} бесплатных визуализаций. Для продолжения свяжитесь с нами."
            )
        start_time = time.time()
        
        furniture_paths = json.loads(furniture_image_paths)
        if not isinstance(furniture_paths, list) or len(furniture_paths) == 0:
            raise HTTPException(400, "furniture_image_paths должен быть непустым массивом")
        furniture_paths = [resolve_furniture_path(p) for p in furniture_paths]
        
        # Режим «Заменить мебель»: один предмет, без анализа позиции
        if (placement_mode or "").strip().lower() == "replace":
            if len(furniture_paths) != 1:
                raise HTTPException(400, "В режиме «Заменить мебель» выберите ровно один предмет (новую мебель)")
            replace_hint = (replace_what or "").strip() or None
            print(f"🔄 Режим замены: подставляем новую мебель вместо старой" + (f" ({replace_hint})" if replace_hint else "") + "...")
            result_path = inpainting_service.place_furniture_replace(
                resolve_room_path(room_image_path),
                furniture_paths[0],
                RESULTS_DIR,
                replace_what=replace_hint
            )
            from backend.utils.image_utils import limit_image_size
            result_path = limit_image_size(result_path, max_long_side=1200)
            result_filename = Path(result_path).name
            result_url = f"/results/{result_filename}"
            generation_time = time.time() - start_time
            print(f"✅ Замена завершена за {generation_time:.2f}с")
            analysis = {
                "room_analysis": {"style": "modern", "lighting": "natural"},
                "furniture_analysis": {"type": "мебель", "style": "современный", "color": "нейтральный"},
                "furniture_items": [{"index": 0, "type": "мебель", "placement": {}}]
            }
            return {
                "success": True,
                "result_image_path": result_path,
                "result_image_url": result_url,
                "generation_time": generation_time,
                "model_used": inpainting_service.get_model_name(),
                "preserves_original": False,
                "analysis": analysis,
                "furniture_count": 1
            }
        
        if len(furniture_paths) > 5:
            raise HTTPException(400, "Максимум 5 предметов мебели")
        
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
        
        # Шаг 1: Анализ с Gemini Vision (при ошибке — запасной режим без AI)
        print(f"🔍 Анализ комнаты и {len(furniture_paths)} предмет(ов) мебели...")
        try:
            analysis = gpt4_analyzer.analyze_multi_furniture_placement(
                room_image_path,
                furniture_paths,
                manual_position
            )
        except Exception as e:
            print(f"⚠️  Gemini недоступен ({e}), используем стандартное размещение")
            n = len(furniture_paths)
            analysis = {
                "room_analysis": {"style": "modern", "lighting": "natural"},
                "placement": {"x_percent": 50, "y_percent": 60, "width_percent": 35, "height_percent": 25, "rotation": 0, "wall_alignment": "auto"},
                "furniture_items": [
                    {
                        "index": i,
                        "type": "furniture",
                        "placement": {
                            "x_percent": 25 + (i * 50 / max(1, n - 1)),
                            "y_percent": 55 + (i % 2) * 8,
                            "width_percent": 30 / n,
                            "height_percent": 25 / n,
                            "rotation": 0,
                            "wall_alignment": "auto"
                        }
                    }
                    for i in range(n)
                ]
            }

        # Если пользователь указал прямоугольник — используем его
        if manual_box is not None:
            from PIL import Image
            room_img = Image.open(room_image_path)
            rw, rh = room_img.size
            bx, by, bw, bh = manual_box
            # clamp
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

            # auto wall inference
            if wall_alignment == "auto":
                left_margin = bx
                right_margin = rw - (bx + bw)
                top_margin = by
                m = min(left_margin, right_margin, top_margin)
                if m == right_margin:
                    wall_alignment = "right"
                elif m == left_margin:
                    wall_alignment = "left"
                else:
                    wall_alignment = "back"

        # Поворот и wall alignment
        if furniture_rotation not in (0, 90):
            raise HTTPException(400, "furniture_rotation должен быть 0 или 90")
        analysis.setdefault("placement", {})
        analysis["placement"]["rotation"] = furniture_rotation
        analysis["placement"]["wall_alignment"] = wall_alignment
        
        # Шаг 2: Размещение мебели (последовательно или композитом)
        print(f"🍌 Размещение {len(furniture_paths)} предмет(ов) мебели...")
        result_path = inpainting_service.place_multi_furniture(
            room_image_path,
            furniture_paths,
            analysis,
            RESULTS_DIR
        )
        
        # Ограничиваем размер результата (макс. 1200px по длинной стороне)
        from backend.utils.image_utils import limit_image_size
        result_path = limit_image_size(result_path, max_long_side=1200)
        
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
            "analysis": analysis,
            "furniture_count": len(furniture_paths)
        }
        
    except Exception as e:
        print(f"❌ Ошибка генерации: {e}")
        raise HTTPException(500, f"Ошибка генерации: {str(e)}")


@app.post("/api/upsell")
async def get_upsell_recommendations(
    furniture_analysis: str = Form(...),
    room_analysis: str = Form(...),
    exclude_paths: str = Form(default="[]")
):
    """
    Рекомендации допродаж из каталога: только то, что реально подойдёт.
    exclude_paths — JSON-массив путей к мебели, которую уже разместили (не рекомендуем её снова).
    """
    try:
        furniture_data = json.loads(furniture_analysis) if isinstance(furniture_analysis, str) else furniture_analysis
        room_data = json.loads(room_analysis) if isinstance(room_analysis, str) else room_analysis
        exclude_list = json.loads(exclude_paths) if isinstance(exclude_paths, str) and exclude_paths.strip() else []
        if not isinstance(exclude_list, list):
            exclude_list = []
    except (json.JSONDecodeError, TypeError):
        furniture_data = {}
        room_data = {}
        exclude_list = []
    
    try:
        if not CATALOG_ITEMS:
            return {"success": True, "recommendations": []}
        
        recommendations = upsell_service.generate_recommendations(
            furniture_data,
            room_data,
            CATALOG_ITEMS,
            max_recommendations=4,
            exclude_item_paths=exclude_list
        )
        
        if not recommendations:
            furniture_type = furniture_data.get("type", "мебель") if isinstance(furniture_data, dict) else "мебель"
            room_style = room_data.get("style", "") if isinstance(room_data, dict) else ""
            simple_recs = upsell_service.get_simple_recommendations(
                furniture_type,
                CATALOG_ITEMS,
                count=4,
                exclude_item_paths=exclude_list,
                room_style=room_style
            )
            recommendations = simple_recs
        
        # Если нечего рекомендовать (всё из каталога уже применили) — сообщение пользователю
        message = None
        if not recommendations and CATALOG_ITEMS:
            message = (
                "Вы уже применили все предметы из каталога. "
                "Добавьте в каталог светильники, тумбочки, стулья, столы — и появятся новые рекомендации."
            )
        return {"success": True, "recommendations": recommendations, "message": message}
        
    except Exception as e:
        print(f"⚠️  Ошибка генерации рекомендаций: {e}")
        furniture_type = furniture_data.get("type", "мебель") if isinstance(furniture_data, dict) else "мебель"
        room_style = room_data.get("style", "") if isinstance(room_data, dict) else ""
        simple_recs = upsell_service.get_simple_recommendations(
            furniture_type,
            CATALOG_ITEMS,
            count=4,
            exclude_item_paths=exclude_list,
            room_style=room_style
        )
        message = (
            "Вы уже применили все предметы из каталога. "
            "Добавьте в каталог светильники, тумбочки, стулья, столы — и появятся новые рекомендации."
        ) if not simple_recs and CATALOG_ITEMS else None
        return {"success": True, "recommendations": simple_recs, "message": message}


@app.get("/api/catalog")
async def get_catalog():
    """
    Получить каталог доступной мебели
    """
    return {
        "success": True,
        "items": CATALOG_ITEMS
    }


@app.get("/api/catalog/img/{filename}")
async def get_catalog_image(filename: str):
    """
    Отдать изображение каталога с белым фоном (без прозрачности).
    Всегда возвращает PNG без альфа-канала — без «шахматной доски».
    """
    # Убираем query string (?v=2) если есть
    safe_name = Path(filename.split("?")[0]).name
    file_path = CATALOG_DIR / safe_name
    if not file_path.exists():
        raise HTTPException(404, "Изображение не найдено")
    try:
        from backend.utils.image_utils import ensure_rgb_png
        png_bytes = ensure_rgb_png(str(file_path))
        return Response(
            content=png_bytes,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=3600"}
        )
    except Exception as e:
        raise HTTPException(500, f"Ошибка обработки изображения: {e}")


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
        
        # Удаляем фон (если установлен rembg)
        file_path_no_bg = background_remover.remove_background(file_path)
        
        # ВАЖНО: Добавляем белый фон к PNG с прозрачностью (убираем "шахматную доску")
        from backend.utils.image_utils import add_white_background_to_png
        file_path_final = add_white_background_to_png(file_path_no_bg)
        
        # Создаем запись в каталоге (относительный путь — чтобы работало на любом сервере)
        item_id = str(uuid.uuid4())
        filename = Path(file_path_final).name
        image_path_stored = f"catalog/{filename}"
        catalog_item = {
            "id": item_id,
            "name": name,
            "type": item_type,
            "style": style,
            "image_path": image_path_stored,
            "image_url": f"/catalog/{filename}",
            "description": description,
            "price": price
        }
        
        CATALOG_ITEMS.append(catalog_item)
        save_catalog(CATALOG_ITEMS)  # Сохраняем в файл
        
        return {
            "success": True,
            "item": catalog_item
        }
        
    except Exception as e:
        raise HTTPException(500, f"Ошибка добавления в каталог: {str(e)}")


@app.post("/api/catalog/fix-backgrounds")
async def fix_catalog_backgrounds():
    """
    Добавить белый фон ко всем изображениям в каталоге (убрать шахматную доску).
    Вызови один раз после обновления или для старых товаров.
    """
    from backend.utils.image_utils import add_white_background_to_png
    
    fixed = 0
    for item in CATALOG_ITEMS:
        path = item.get("image_path")
        if path:
            resolved = resolve_furniture_path(path)
            if Path(resolved).exists():
                add_white_background_to_png(resolved)
                fixed += 1
    
    return {
        "success": True,
        "message": f"Обработано {fixed} изображений",
        "fixed_count": fixed
    }


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
    
    # Удаляем файл (путь может быть относительным или с другой машины)
    try:
        Path(resolve_furniture_path(item['image_path'])).unlink(missing_ok=True)
    except Exception as e:
        print(f"⚠️  Не удалось удалить файл: {e}")
    
    # Удаляем из каталога
    CATALOG_ITEMS = [i for i in CATALOG_ITEMS if i['id'] != item_id]
    save_catalog(CATALOG_ITEMS)  # Сохраняем в файл
    
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
