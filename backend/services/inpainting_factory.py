"""
Фабрика для создания нужного сервиса размещения мебели
"""
from .base_inpainting import BaseInpaintingService
from .simple_composite import SimpleCompositeService
from .qwen_service import QwenService
from .nano_banana import NanoBananaService


class InpaintingFactory:
    """
    Фабрика для выбора модели размещения мебели
    """
    
    # Доступные модели
    MODELS = {
        'simple': {
            'name': 'Simple Composite',
            'description': 'Быстрое наложение без AI (сохраняет 100% оригинал)',
            'class': SimpleCompositeService,
            'time': '< 1 сек',
            'preserves_original': True,
            'cost': 'Бесплатно'
        },
        'qwen': {
            'name': 'Qwen Image Edit',
            'description': 'AI генерация (Kie.ai) - реалистичные тени и освещение',
            'class': QwenService,
            'time': '~80 сек',
            'preserves_original': False,
            'cost': '$0.01'
        },
        'nano-banana': {
            'name': 'Nano Banana Pro',
            'description': 'Google DeepMind - 2K/4K качество, улучшенная точность',
            'class': NanoBananaService,
            'time': '~60 сек',
            'preserves_original': False,
            'cost': '$0.02'
        }
    }
    
    @staticmethod
    def create(model_type: str = 'simple') -> BaseInpaintingService:
        """
        Создает экземпляр сервиса для выбранной модели
        
        Args:
            model_type: Тип модели ('simple', 'qwen', 'nano-banana')
            
        Returns:
            Экземпляр BaseInpaintingService
            
        Raises:
            ValueError: Если модель не найдена
        """
        if model_type not in InpaintingFactory.MODELS:
            raise ValueError(
                f"Unknown model: {model_type}. "
                f"Available: {', '.join(InpaintingFactory.MODELS.keys())}"
            )
        
        model_class = InpaintingFactory.MODELS[model_type]['class']
        return model_class()
    
    @staticmethod
    def get_available_models():
        """
        Возвращает список доступных моделей с описанием
        
        Returns:
            Словарь с информацией о доступных моделях
        """
        return {
            key: {
                'name': info['name'],
                'description': info['description'],
                'time': info['time'],
                'preserves_original': info['preserves_original'],
                'cost': info['cost']
            }
            for key, info in InpaintingFactory.MODELS.items()
        }
