"""
Сервис для простого наложения мебели без AI генерации
"""
import uuid
from pathlib import Path
from typing import Dict, Any
from PIL import Image

from .base_inpainting import BaseInpaintingService


class SimpleCompositeService(BaseInpaintingService):
    """
    Простое наложение изображения мебели на комнату без AI
    Мебель остается 100% оригинальной
    """
    
    def __init__(self):
        """Инициализация сервиса"""
        pass
    
    def place_furniture(
        self,
        room_image_path: str,
        furniture_image_path: str,
        placement_params: Dict[str, Any],
        output_dir: Path
    ) -> str:
        """
        Размещает мебель простым наложением (композитинг)
        
        Args:
            room_image_path: Путь к изображению комнаты
            furniture_image_path: Путь к изображению мебели (без фона)
            placement_params: Параметры размещения от GPT-4V
            output_dir: Директория для сохранения результата
            
        Returns:
            Путь к результирующему изображению
        """
        try:
            print(f"🎨 Простое наложение мебели (без AI)...")
            
            # Открываем изображения
            room = Image.open(room_image_path).convert('RGB')
            furniture = Image.open(furniture_image_path).convert('RGBA')
            
            # Получаем параметры размещения
            placement = placement_params.get('placement', {})
            
            # Размеры комнаты
            room_width, room_height = room.size
            
            # Вычисляем позицию и размер мебели
            x_percent = placement.get('x_percent', 50)
            y_percent = placement.get('y_percent', 50)
            width_percent = placement.get('width_percent', 30)
            height_percent = placement.get('height_percent', 30)
            scale = placement.get('scale', 1.0)
            
            # Масштабируем мебель
            target_width = int(room_width * width_percent / 100 * scale)
            target_height = int(room_height * height_percent / 100 * scale)
            
            # Сохраняем пропорции мебели
            furniture_aspect = furniture.width / furniture.height
            target_aspect = target_width / target_height
            
            if furniture_aspect > target_aspect:
                # Мебель шире - подгоняем по ширине
                new_width = target_width
                new_height = int(target_width / furniture_aspect)
            else:
                # Мебель выше - подгоняем по высоте
                new_height = target_height
                new_width = int(target_height * furniture_aspect)
            
            # Масштабируем мебель с высоким качеством
            furniture_resized = furniture.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )
            
            print(f"   Размер мебели: {furniture.size} → {furniture_resized.size}")
            
            # Вычисляем позицию вставки
            x_pos = int(room_width * x_percent / 100 - new_width / 2)
            y_pos = int(room_height * y_percent / 100 - new_height / 2)
            
            # Убеждаемся что мебель внутри границ
            x_pos = max(0, min(x_pos, room_width - new_width))
            y_pos = max(0, min(y_pos, room_height - new_height))
            
            print(f"   Позиция вставки: ({x_pos}, {y_pos})")
            
            # Конвертируем комнату в RGBA для наложения
            room_rgba = room.convert('RGBA')
            
            # Накладываем мебель поверх комнаты
            # Используем альфа-канал мебели как маску
            room_rgba.paste(furniture_resized, (x_pos, y_pos), furniture_resized)
            
            # Конвертируем обратно в RGB
            result = room_rgba.convert('RGB')
            
            # Сохраняем результат
            output_path = output_dir / f"result_{uuid.uuid4()}.png"
            result.save(output_path, quality=95)
            
            print(f"✅ Наложение завершено мгновенно!")
            print(f"   Сохранено: {output_path}")
            
            return str(output_path)
            
        except Exception as e:
            print(f"❌ Ошибка при наложении: {e}")
            raise
    
    def get_model_name(self) -> str:
        """Возвращает название модели"""
        return "Simple Composite (без AI)"
    
    def get_estimated_time(self) -> int:
        """Возвращает примерное время генерации"""
        return 1  # Мгновенно
    
    def preserves_original(self) -> bool:
        """Сохраняет оригинальный вид мебели"""
        return True  # 100% оригинал!
