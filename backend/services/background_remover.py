"""
Сервис для удаления фона с изображений мебели
"""
from pathlib import Path
from typing import Optional
from PIL import Image
import io

# Используем rembg (встроенная библиотека)
try:
    from rembg import remove
    REMBG_AVAILABLE = True
except ImportError:
    REMBG_AVAILABLE = False
    print("⚠️  rembg не установлен. Удаление фона будет пропущено.")


class BackgroundRemover:
    """
    Класс для удаления фона с изображений
    Вариант A: используем rembg (бесплатно, работает локально)
    Вариант B: можно заменить на Remove.bg API (платно, но качественнее)
    """
    
    def __init__(self, use_api: bool = False):
        """
        Инициализация
        
        Args:
            use_api: Использовать Remove.bg API (требует API ключ)
        """
        self.use_api = use_api
        
        if use_api:
            from ..utils.load_env import get_env_variable
            self.api_key = get_env_variable('REMOVEBG_API_KEY', None)
            if not self.api_key:
                print("⚠️  REMOVEBG_API_KEY не установлен, используем rembg")
                self.use_api = False
    
    def remove_background(
        self,
        input_path: str,
        output_path: Optional[str] = None
    ) -> str:
        """
        Удаляет фон с изображения
        
        Args:
            input_path: Путь к входному изображению
            output_path: Путь для сохранения (если None, перезаписываем)
            
        Returns:
            Путь к изображению без фона
        """
        if output_path is None:
            output_path = input_path
        
        if self.use_api:
            return self._remove_with_api(input_path, output_path)
        else:
            return self._remove_with_rembg(input_path, output_path)
    
    def _remove_with_rembg(self, input_path: str, output_path: str) -> str:
        """
        Удаляет фон используя rembg (локально, бесплатно)
        
        Args:
            input_path: Входное изображение
            output_path: Выходное изображение
            
        Returns:
            Путь к результату
        """
        # Проверяем доступность rembg
        if not REMBG_AVAILABLE:
            print(f"⚠️  rembg не установлен, пропускаем удаление фона")
            if input_path != output_path:
                import shutil
                shutil.copy(input_path, output_path)
            return output_path
        
        try:
            # Открываем изображение
            with open(input_path, 'rb') as input_file:
                input_data = input_file.read()
            
            # Удаляем фон
            output_data = remove(input_data)
            
            # Сохраняем
            output_image = Image.open(io.BytesIO(output_data))
            output_image.save(output_path, 'PNG')
            
            print(f"✅ Фон удален (rembg): {output_path}")
            return output_path
            
        except Exception as e:
            print(f"❌ Ошибка удаления фона (rembg): {e}")
            # В случае ошибки возвращаем оригинал
            if input_path != output_path:
                import shutil
                shutil.copy(input_path, output_path)
            return output_path
    
    def _remove_with_api(self, input_path: str, output_path: str) -> str:
        """
        Удаляет фон используя Remove.bg API (платно, качественнее)
        
        Args:
            input_path: Входное изображение
            output_path: Выходное изображение
            
        Returns:
            Путь к результату
        """
        try:
            import requests
            
            # Отправляем запрос к Remove.bg API
            with open(input_path, 'rb') as input_file:
                response = requests.post(
                    'https://api.remove.bg/v1.0/removebg',
                    files={'image_file': input_file},
                    data={'size': 'auto'},
                    headers={'X-Api-Key': self.api_key},
                    timeout=30
                )
            
            if response.status_code == 200:
                # Сохраняем результат
                with open(output_path, 'wb') as output_file:
                    output_file.write(response.content)
                
                print(f"✅ Фон удален (Remove.bg API): {output_path}")
                return output_path
            else:
                print(f"⚠️  Remove.bg API ошибка: {response.status_code}")
                print(f"Ответ: {response.text}")
                # Откатываемся на rembg
                return self._remove_with_rembg(input_path, output_path)
            
        except Exception as e:
            print(f"❌ Ошибка Remove.bg API: {e}")
            # Откатываемся на rembg
            return self._remove_with_rembg(input_path, output_path)
    
    def check_has_transparency(self, image_path: str) -> bool:
        """
        Проверяет есть ли у изображения прозрачность
        
        Args:
            image_path: Путь к изображению
            
        Returns:
            True если есть альфа-канал
        """
        try:
            image = Image.open(image_path)
            return image.mode in ('RGBA', 'LA') or (
                image.mode == 'P' and 'transparency' in image.info
            )
        except Exception:
            return False
