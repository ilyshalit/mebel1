"""
Базовый класс для всех сервисов размещения мебели
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any


class BaseInpaintingService(ABC):
    """
    Абстрактный базовый класс для всех моделей размещения мебели
    """
    
    @abstractmethod
    def place_furniture(
        self,
        room_image_path: str,
        furniture_image_path: str,
        placement_params: Dict[str, Any],
        output_dir: Path
    ) -> str:
        """
        Размещает мебель в комнате
        
        Args:
            room_image_path: Путь к изображению комнаты
            furniture_image_path: Путь к изображению мебели (без фона)
            placement_params: Параметры размещения от GPT-4V
            output_dir: Директория для сохранения результата
            
        Returns:
            Путь к результирующему изображению
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """
        Возвращает название модели
        
        Returns:
            Название модели для отображения пользователю
        """
        pass
    
    @abstractmethod
    def get_estimated_time(self) -> int:
        """
        Возвращает примерное время генерации в секундах
        
        Returns:
            Время в секундах
        """
        pass
    
    @abstractmethod
    def preserves_original(self) -> bool:
        """
        Сохраняет ли модель оригинальный вид мебели
        
        Returns:
            True если сохраняет 100% оригинал, False если может изменить
        """
        pass
