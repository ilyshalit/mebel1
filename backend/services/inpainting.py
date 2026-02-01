"""
Сервис для редактирования изображений с помощью Qwen Image Edit через Kie.ai
"""
import time
import requests
import json
from pathlib import Path
from typing import Dict, Any, Tuple
from PIL import Image
import base64
import io
import uuid

from ..utils.load_env import get_env_variable
from ..utils.image_utils import download_image
from .image_uploader import ImageUploader


class InpaintingService:
    """
    Сервис для композиции изображений с помощью Qwen Image Edit на Kie.ai
    """
    
    def __init__(self):
        """Инициализация клиента Kie.ai"""
        api_key = get_env_variable('KIE_AI_API_KEY')
        self.api_key = api_key
        
        # API endpoint для Kie.ai
        self.api_url = "https://api.kie.ai/api/v1/jobs/createTask"
        self.model_name = "qwen/image-edit"
        
        # Image uploader для создания публичных URL
        self.uploader = ImageUploader()
    
    def place_furniture(
        self,
        room_image_path: str,
        furniture_image_path: str,
        placement_params: Dict[str, Any],
        output_dir: Path
    ) -> str:
        """
        Размещает мебель в комнате используя Qwen Image Edit
        
        Args:
            room_image_path: Путь к изображению комнаты
            furniture_image_path: Путь к изображению мебели (без фона)
            placement_params: Параметры размещения от GPT-4V
            output_dir: Директория для сохранения результата
            
        Returns:
            Путь к результирующему изображению
        """
        try:
            # Загружаем изображение на imgbb для получения публичного URL
            print(f"📤 Загрузка изображения на временный хостинг...")
            room_url = self.uploader.upload_image(room_image_path, expiration=600)
            
            if not room_url:
                raise ValueError("Не удалось загрузить изображение на хостинг")
            
            # Формируем промпт для Qwen Image Edit
            prompt = self._create_semantic_prompt(placement_params, furniture_image_path)
            
            print(f"🎨 Запуск Qwen Image Edit на Kie.ai...")
            print(f"   Промпт: {prompt}")
            print(f"   Image URL: {room_url}")
            
            # Подготавливаем payload согласно документации Kie.ai
            payload = {
                "model": self.model_name,
                "input": {
                    "prompt": prompt,
                    "image_url": room_url,  # Публичный URL изображения
                    "acceleration": "regular",  # Баланс скорости и качества
                    "image_size": "landscape_4_3",
                    "num_inference_steps": 35,  # Увеличено для лучшего качества
                    "guidance_scale": 7,  # Увеличено для точного следования промпту
                    "num_images": "1",  # Строка (!)
                    "output_format": "png",
                    "negative_prompt": "blurry, distorted, unrealistic, ugly, bad quality, low quality, cartoon, painting, drawing, modified furniture, changed colors, altered design, different furniture, wrong color, recolored, repainted, modified texture",
                    "enable_safety_checker": True,
                    "sync_mode": False  # Асинхронный режим - используем Query Task
                }
            }
            
            # Отправляем запрос к Kie.ai API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30  # 30 секунд таймаут для получения taskId
            )
            
            print(f"📡 HTTP статус: {response.status_code}")
            
            # Полный ответ для отладки
            response_text = response.text
            print(f"📄 Ответ сервера (первые 500 символов): {response_text[:500]}")
            
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ Ответ от Kie.ai получен")
            print(f"   Код: {result.get('code')}, Сообщение: {result.get('msg')}")
            
            # Проверяем успешность запроса
            if result.get('code') != 200:
                raise ValueError(f"Kie.ai API ошибка: {result.get('msg')}")
            
            data = result.get('data', {})
            
            # Проверяем есть ли taskId (асинхронный режим)
            if 'taskId' in data:
                task_id = data['taskId']
                print(f"📋 Задача поставлена в очередь, taskId: {task_id}")
                print(f"⏳ Ожидание завершения обработки...")
                
                # Опрашиваем результат
                result_path = self._query_task_result(task_id, output_dir)
                return result_path
            else:
                # Синхронный результат
                result_path = self._process_result(data, output_dir)
                return result_path
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к Kie.ai API: {e}")
            if hasattr(e.response, 'text'):
                print(f"   Ответ сервера: {e.response.text}")
            raise
        except Exception as e:
            print(f"❌ Ошибка при редактировании: {e}")
            raise
    
    def _query_task_result(self, task_id: str, output_dir: Path, max_attempts: int = 60) -> str:
        """
        Опрашивает результат задачи через Query task API
        
        Args:
            task_id: ID задачи от Kie.ai
            output_dir: Директория для сохранения
            max_attempts: Максимальное количество попыток (60 = 2 минуты)
            
        Returns:
            Путь к результату
        """
        # Query task endpoint согласно документации
        query_url = "https://api.kie.ai/api/v1/jobs/recordInfo"
        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(
                    query_url,
                    headers=headers,
                    params={"taskId": task_id},
                    timeout=30
                )
                response.raise_for_status()
                result = response.json()
                
                if result.get('code') == 200:
                    data = result.get('data', {})
                    state = data.get('state')  # Используем 'state' вместо 'status'
                    
                    if state == 'success':
                        print(f"✅ Задача завершена успешно!")
                        # Результат в поле resultJson (это JSON строка)
                        result_json_str = data.get('resultJson')
                        if result_json_str:
                            result_json = json.loads(result_json_str)
                            result_urls = result_json.get('resultUrls', [])
                            if result_urls and len(result_urls) > 0:
                                print(f"📥 Скачивание результата по URL...")
                                return download_image(result_urls[0], output_dir)
                            else:
                                raise ValueError(f"В resultJson нет resultUrls: {result_json}")
                        else:
                            raise ValueError("Нет поля resultJson в ответе")
                    elif state == 'fail':
                        fail_msg = data.get('failMsg', 'Unknown error')
                        fail_code = data.get('failCode', '')
                        raise ValueError(f"Задача завершилась с ошибкой [{fail_code}]: {fail_msg}")
                    else:
                        # Еще обрабатывается (waiting, queuing, generating)
                        if attempt % 5 == 0:  # Логируем каждые 5 секунд
                            print(f"⏳ Статус: {state}, попытка {attempt + 1}/{max_attempts}")
                        time.sleep(2)  # Ждем 2 секунды перед следующей попыткой
                else:
                    raise ValueError(f"Ошибка опроса задачи: {result.get('message')}")
                    
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Превышено время ожидания результата: {e}")
                time.sleep(2)
        
        raise TimeoutError("Превышено время ожидания результата от Kie.ai")
    
    def _process_result(self, data: Dict[str, Any], output_dir: Path) -> str:
        """
        Обрабатывает результат от Kie.ai API
        
        Args:
            data: Поле 'data' из JSON ответа API
            output_dir: Директория для сохранения
            
        Returns:
            Путь к сохраненному изображению
        """
        # В sync_mode=true, результат содержит изображение напрямую
        # Возможные форматы ответа:
        
        # 1. Если есть output с URL или base64 или списком
        if 'output' in data:
            output = data['output']
            # Список URL
            if isinstance(output, list) and len(output) > 0:
                first_url = output[0]
                if isinstance(first_url, str) and first_url.startswith('http'):
                    print(f"📥 Скачивание результата по URL из списка...")
                    return download_image(first_url, output_dir)
            # URL изображения
            elif isinstance(output, str) and output.startswith('http'):
                print(f"📥 Скачивание результата по URL...")
                return download_image(output, output_dir)
            # Base64
            elif isinstance(output, str):
                print(f"💾 Сохранение результата из base64...")
                image_data = base64.b64decode(output)
                result_path = output_dir / f"result_{uuid.uuid4()}.png"
                with open(result_path, 'wb') as f:
                    f.write(image_data)
                return str(result_path)
        
        # 2. Если массив images
        elif 'images' in data and len(data['images']) > 0:
            first_image = data['images'][0]
            if isinstance(first_image, str) and first_image.startswith('http'):
                print(f"📥 Скачивание результата по URL...")
                return download_image(first_image, output_dir)
            elif isinstance(first_image, str):
                print(f"💾 Сохранение результата из base64...")
                image_data = base64.b64decode(first_image)
                result_path = output_dir / f"result_{uuid.uuid4()}.png"
                with open(result_path, 'wb') as f:
                    f.write(image_data)
                return str(result_path)
        
        # 3. Если результат в поле result
        elif 'result' in data:
            result = data['result']
            if isinstance(result, str) and result.startswith('http'):
                print(f"📥 Скачивание результата по URL...")
                return download_image(result, output_dir)
            elif isinstance(result, str):
                print(f"💾 Сохранение результата из base64...")
                image_data = base64.b64decode(result)
                result_path = output_dir / f"result_{uuid.uuid4()}.png"
                with open(result_path, 'wb') as f:
                    f.write(image_data)
                return str(result_path)
        
        # Если не нашли результат
        else:
            raise ValueError(f"Не удалось найти изображение в ответе. Data: {data}")
    
    def _create_semantic_prompt(
        self, 
        placement_params: Dict[str, Any],
        furniture_image_path: str
    ) -> str:
        """
        Создает семантический промпт для Qwen Image Edit
        Описывает ЧТО и ГДЕ нужно разместить
        
        Args:
            placement_params: Параметры от GPT-4V
            furniture_image_path: Путь к изображению мебели
            
        Returns:
            Детальный промпт для Qwen Image Edit
        """
        # Получаем анализ от GPT-4V
        furniture = placement_params.get('furniture_analysis', {})
        room = placement_params.get('room_analysis', {})
        placement = placement_params.get('placement', {})
        
        # Информация о мебели
        furniture_type = furniture.get('type', 'furniture item')
        furniture_style = furniture.get('style', 'modern')
        furniture_color = furniture.get('color', 'neutral toned')
        furniture_size = furniture.get('estimated_size', 'medium sized')
        
        # Информация о комнате
        room_style = room.get('style', 'modern')
        room_lighting = room.get('lighting', 'natural lighting')
        
        # Информация о размещении
        reasoning = placement.get('reasoning', '')
        
        # Формируем детальный промпт для семантического редактирования
        # ВАЖНО: Акцент на сохранении ОРИГИНАЛЬНОГО вида мебели!
        prompt = f"""Place this exact {furniture_color} {furniture_type} into the {room_style} room.

CRITICAL REQUIREMENTS:
- The furniture must look EXACTLY as in the original image
- Preserve the EXACT color: {furniture_color}
- Preserve the EXACT design and style: {furniture_style}
- Do NOT modify or alter the furniture appearance
- Do NOT change furniture color, texture or material
- Only adjust size and perspective to fit the room naturally

Placement: {reasoning if reasoning else 'Place it naturally in the room where it fits best'}

The result should be:
- Photorealistic integration with {room_lighting}
- Realistic shadows and reflections
- Proper perspective matching the room
- Seamless blending while keeping furniture IDENTICAL to original

Keep the room and furniture EXACTLY as they are in the original images."""
        
        return prompt.strip()
