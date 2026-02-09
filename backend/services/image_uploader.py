"""
Сервис для создания публичных URL для изображений
Использует ImgBB API для стабильной загрузки
"""
import time
from typing import Optional
from pathlib import Path
import requests
import base64
from ..utils.load_env import get_env_variable

IMGBB_RETRIES = 3
IMGBB_RETRY_DELAY = 8
IMGBB_TIMEOUT = 45


class ImageUploader:
    """
    Загружает изображения на ImgBB и возвращает публичные URL
    """
    
    def __init__(self):
        try:
            self.api_key = get_env_variable('IMGBB_API_KEY')
        except ValueError:
            self.api_key = ''
        self.api_url = "https://api.imgbb.com/1/upload"
    
    def upload_image(self, image_path: str, expiration: int = 600) -> Optional[str]:
        """
        Загружает изображение на ImgBB (с повторами при 503/таймауте).
        
        Args:
            image_path: Путь к изображению
            expiration: Время жизни в секундах (600 = 10 минут)
            
        Returns:
            Публичный URL изображения или None
        """
        if not self.api_key:
            print(f"⚠️  IMGBB_API_KEY не установлен!")
            return None
        
        try:
            with open(image_path, 'rb') as file:
                image_data = base64.b64encode(file.read()).decode('utf-8')
        except Exception as e:
            print(f"❌ Не удалось прочитать файл: {e}")
            return None
        
        payload = {
            'key': self.api_key,
            'image': image_data,
            'expiration': expiration
        }
        
        last_error = None
        for attempt in range(IMGBB_RETRIES):
            try:
                print(f"📤 Загрузка на ImgBB... (попытка {attempt + 1}/{IMGBB_RETRIES})")
                response = requests.post(self.api_url, data=payload, timeout=IMGBB_TIMEOUT)
                response.raise_for_status()
                result = response.json()
                if result.get('success'):
                    url = result['data']['url']
                    print(f"✅ Изображение загружено на ImgBB: {url}")
                    return url
                last_error = result
            except requests.exceptions.Timeout as e:
                last_error = e
                if attempt < IMGBB_RETRIES - 1:
                    print(f"⏳ Таймаут ImgBB, повтор через {IMGBB_RETRY_DELAY} сек...")
                    time.sleep(IMGBB_RETRY_DELAY)
            except requests.exceptions.HTTPError as e:
                last_error = e
                if response.status_code == 503 and attempt < IMGBB_RETRIES - 1:
                    print(f"⏳ ImgBB 503, повтор через {IMGBB_RETRY_DELAY} сек...")
                    time.sleep(IMGBB_RETRY_DELAY)
                else:
                    break
            except Exception as e:
                last_error = e
                break
        
        print(f"❌ Ошибка при загрузке на ImgBB после {IMGBB_RETRIES} попыток: {last_error}")
        return None
    
    def image_to_data_url(self, image_path: str) -> Optional[str]:
        """
        Возвращает data URL (base64) для изображения — запасной вариант без ImgBB.
        Подходит для API, которые принимают data:image/... в url.
        """
        try:
            ext = (Path(image_path).suffix or "").lower()
            mime = "image/png"
            if ext in (".jpg", ".jpeg"):
                mime = "image/jpeg"
            elif ext == ".webp":
                mime = "image/webp"
            with open(image_path, 'rb') as f:
                b64 = base64.b64encode(f.read()).decode('utf-8')
            return f"data:{mime};base64,{b64}"
        except Exception as e:
            print(f"❌ Ошибка чтения для data URL: {e}")
            return None
