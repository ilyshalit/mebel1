"""
Сервис для создания публичных URL для изображений
Использует ImgBB API для стабильной загрузки
"""
from typing import Optional
from pathlib import Path
import requests
import base64
from ..utils.load_env import get_env_variable


class ImageUploader:
    """
    Загружает изображения на ImgBB и возвращает публичные URL
    """
    
    def __init__(self):
        # ImgBB API ключ
        self.api_key = get_env_variable('IMGBB_API_KEY', '')
        self.api_url = "https://api.imgbb.com/1/upload"
    
    def upload_image(self, image_path: str, expiration: int = 600) -> Optional[str]:
        """
        Загружает изображение на ImgBB
        
        Args:
            image_path: Путь к изображению
            expiration: Время жизни в секундах (600 = 10 минут)
            
        Returns:
            Публичный URL изображения
        """
        try:
            if not self.api_key:
                print(f"⚠️  IMGBB_API_KEY не установлен!")
                return None
            
            # Читаем изображение и конвертируем в base64
            with open(image_path, 'rb') as file:
                image_data = base64.b64encode(file.read()).decode('utf-8')
            
            # Отправляем на ImgBB
            payload = {
                'key': self.api_key,
                'image': image_data,
                'expiration': expiration  # 10 минут
            }
            
            print(f"📤 Загрузка изображения на ImgBB...")
            response = requests.post(self.api_url, data=payload, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get('success'):
                url = result['data']['url']
                print(f"✅ Изображение загружено на ImgBB: {url}")
                return url
            else:
                print(f"❌ Ошибка ImgBB: {result}")
                return None
                
        except Exception as e:
            print(f"❌ Ошибка при загрузке на ImgBB: {e}")
            return None
