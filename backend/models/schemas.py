"""
Pydantic модели для API
"""
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PlacementMode(BaseModel):
    """Режим размещения мебели"""
    mode: str = Field(..., description="auto или manual")
    position: Optional[Dict[str, int]] = Field(None, description="Позиция для manual режима {x, y}")


class AnalyzeRequest(BaseModel):
    """Запрос на анализ изображений"""
    room_image_path: str = Field(..., description="Путь к изображению комнаты")
    furniture_image_path: str = Field(..., description="Путь к изображению мебели")
    mode: str = Field(default="auto", description="Режим: auto или manual")
    manual_position: Optional[Dict[str, int]] = Field(None, description="Позиция для manual режима")


class AnalyzeResponse(BaseModel):
    """Ответ анализа"""
    room_analysis: str = Field(..., description="Анализ комнаты")
    furniture_analysis: str = Field(..., description="Анализ мебели")
    placement_suggestion: str = Field(..., description="Предложение по размещению")
    placement_area: Dict[str, int] = Field(..., description="Область размещения {x, y, width, height}")
    inpainting_prompt: str = Field(..., description="Промпт для inpainting")


class GenerateRequest(BaseModel):
    """Запрос на генерацию"""
    room_image_path: str = Field(..., description="Путь к изображению комнаты")
    furniture_image_path: str = Field(..., description="Путь к изображению мебели")
    analysis: AnalyzeResponse = Field(..., description="Результат анализа")


class GenerateResponse(BaseModel):
    """Ответ генерации"""
    result_image_path: str = Field(..., description="Путь к результату")
    result_image_url: str = Field(..., description="URL результата")
    generation_time: float = Field(..., description="Время генерации в секундах")


class UpsellRequest(BaseModel):
    """Запрос рекомендаций"""
    furniture_type: str = Field(..., description="Тип размещенной мебели")
    room_style: str = Field(..., description="Стиль комнаты")
    catalog_items: List[Dict[str, Any]] = Field(..., description="Каталог доступной мебели")


class UpsellItem(BaseModel):
    """Рекомендуемый товар"""
    item_id: str = Field(..., description="ID товара")
    name: str = Field(..., description="Название")
    reason: str = Field(..., description="Почему рекомендуем")
    image_url: Optional[str] = Field(None, description="URL изображения")


class UpsellResponse(BaseModel):
    """Ответ с рекомендациями"""
    recommendations: List[UpsellItem] = Field(..., description="Список рекомендаций")


class CatalogItem(BaseModel):
    """Элемент каталога мебели"""
    id: str = Field(..., description="ID товара")
    name: str = Field(..., description="Название")
    type: str = Field(..., description="Тип мебели (диван, кресло, стол и тд)")
    style: str = Field(..., description="Стиль (современный, классический и тд)")
    image_path: str = Field(..., description="Путь к изображению")
    description: Optional[str] = Field(None, description="Описание")
    price: Optional[float] = Field(None, description="Цена")


class ErrorResponse(BaseModel):
    """Ответ с ошибкой"""
    error: str = Field(..., description="Описание ошибки")
    details: Optional[str] = Field(None, description="Детали ошибки")
