"""
Сервис для редактирования изображений с помощью Nano Banana Pro через Kie.ai
Google DeepMind's Nano Banana Pro - улучшенное качество 2K/4K
"""
import time
import requests
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image
import uuid
import os

from ..utils.load_env import get_env_variable
from ..utils.image_utils import download_image, create_furniture_collage
from .image_uploader import ImageUploader
from .base_inpainting import BaseInpaintingService


class NanoBananaService(BaseInpaintingService):
    """
    Сервис для композиции изображений с помощью Nano Banana Pro на Kie.ai
    Google DeepMind - 2K/4K качество, улучшенная консистентность
    """
    
    def __init__(self):
        """Инициализация клиента Kie.ai"""
        api_key = get_env_variable('KIE_AI_API_KEY')
        self.api_key = api_key
        
        # API endpoint для Kie.ai
        self.api_url = "https://api.kie.ai/api/v1/jobs/createTask"
        self.model_name = "nano-banana-pro"
        
        # Image uploader для создания публичных URL
        self.uploader = ImageUploader()
    
    def place_multi_furniture(
        self,
        room_image_path: str,
        furniture_image_paths: List[str],
        placement_params: Dict[str, Any],
        output_dir: Path
    ) -> str:
        """
        Размещает несколько предметов мебели в комнате.
        Один предмет — один вызов API. Несколько предметов — коллаж в одном изображении, один вызов API (дешевле и быстрее).
        """
        try:
            n = len(furniture_image_paths)
            furniture_items = placement_params.get("furniture_items", [])
            
            if n == 1:
                one_params = {
                    "room_analysis": placement_params.get("room_analysis", {}),
                    "furniture_analysis": placement_params.get("furniture_analysis", {}),
                    "placement": placement_params.get("placement", {})
                }
                if furniture_items:
                    first = furniture_items[0]
                    one_params["furniture_analysis"] = {
                        "type": first.get("type", "furniture"),
                        "style": first.get("style", "modern"),
                        "color": first.get("color", "neutral"),
                        "estimated_size": first.get("estimated_size", "medium")
                    }
                    one_params["placement"] = (first.get("placement") or one_params["placement"])
                return self.place_furniture(
                    room_image_path,
                    furniture_image_paths[0],
                    one_params,
                    output_dir
                )
            
            # Несколько предметов: один коллаж → один вызов Nano Banana
            print(f"🖼️  Собираем {n} предмет(ов) в одно изображение для одной генерации...")
            collage_path = str(output_dir / f"collage_{uuid.uuid4().hex}.png")
            create_furniture_collage(furniture_image_paths, collage_path, max_height=512, padding=40)
            
            print(f"🍌 Один вызов Nano Banana Pro: комната + все предметы...")
            return self._place_furniture_single_call(
                room_image_path,
                collage_path,
                furniture_image_paths,
                placement_params,
                output_dir
            )
            
        except Exception as e:
            print(f"❌ Ошибка при размещении множественной мебели: {e}")
            raise
    
    def _place_furniture_single_call(
        self,
        room_image_path: str,
        collage_path: str,
        furniture_image_paths: List[str],
        placement_params: Dict[str, Any],
        output_dir: Path
    ) -> str:
        """Один запрос к API: комната + коллаж мебели, промпт с позициями для каждого предмета."""
        rotated_path = None
        try:
            print(f"📤 Загрузка изображения комнаты на хостинг...")
            room_url = self.uploader.upload_image(room_image_path, expiration=600)
            if not room_url:
                room_url = self.uploader.image_to_data_url(room_image_path)
                if room_url:
                    print(f"✅ Комната в base64 (ImgBB недоступен)")
            if not room_url:
                raise ValueError("Не удалось загрузить изображение комнаты")
            
            print(f"📤 Загрузка коллажа мебели на хостинг...")
            collage_url = self.uploader.upload_image(collage_path, expiration=600)
            if not collage_url:
                collage_url = self.uploader.image_to_data_url(collage_path)
                if collage_url:
                    print(f"✅ Коллаж в base64")
            if not collage_url:
                raise ValueError("Не удалось загрузить коллаж мебели")
            
            prompt = self._create_multi_placement_prompt(
                placement_params,
                len(furniture_image_paths)
            )
            
            room_img = Image.open(room_image_path)
            aspect_ratio = self._get_aspect_ratio(room_img.size)
            
            payload = {
                "model": self.model_name,
                "input": {
                    "prompt": prompt,
                    "image_input": [room_url, collage_url],
                    "aspect_ratio": aspect_ratio,
                    "resolution": "1K",
                    "output_format": "png"
                }
            }
            
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            print(f"📡 HTTP статус: {response.status_code}")
            response.raise_for_status()
            result = response.json()
            
            if result.get("code") != 200:
                raise ValueError(f"Nano Banana Pro API: {result.get('message')}")
            
            data = result.get("data", {})
            task_id = data.get("taskId")
            if not task_id:
                raise ValueError("Нет taskId в ответе")
            
            print(f"📋 Задача в очереди, taskId: {task_id}")
            return self._query_task_result(task_id, output_dir)
            
        finally:
            try:
                if collage_path and os.path.exists(collage_path):
                    os.remove(collage_path)
            except Exception:
                pass
    
    def place_furniture_replace(
        self,
        room_image_path: str,
        furniture_image_path: str,
        output_dir: Path,
        replace_what: Optional[str] = None
    ) -> str:
        """
        Заменяет существующую мебель в комнате на новую (например старый диван на новый).
        Первое изображение — комната со старой мебелью, второе — новая мебель.
        replace_what: подсказка, что именно заменить (например "sofa on the left"), из анализа комнаты.
        """
        try:
            print(f"🔄 Режим замены: подставляем новую мебель вместо старой в комнате...")
            room_url = self.uploader.upload_image(room_image_path, expiration=600)
            if not room_url:
                room_url = self.uploader.image_to_data_url(room_image_path)
            if not room_url:
                raise ValueError("Не удалось загрузить изображение комнаты")
            
            furniture_url = self.uploader.upload_image(furniture_image_path, expiration=600)
            if not furniture_url:
                furniture_url = self.uploader.image_to_data_url(furniture_image_path)
            if not furniture_url:
                raise ValueError("Не удалось загрузить изображение новой мебели")
            
            prompt = self._create_replace_prompt(replace_what)
            room_img = Image.open(room_image_path)
            aspect_ratio = self._get_aspect_ratio(room_img.size)
            
            payload = {
                "model": self.model_name,
                "input": {
                    "prompt": prompt,
                    "image_input": [room_url, furniture_url],
                    "aspect_ratio": aspect_ratio,
                    "resolution": "1K",
                    "output_format": "png"
                }
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            response = requests.post(self.api_url, headers=headers, json=payload, timeout=30)
            response.raise_for_status()
            result = response.json()
            if result.get("code") != 200:
                raise ValueError(f"Nano Banana Pro API: {result.get('message')}")
            data = result.get("data", {})
            task_id = data.get("taskId")
            if not task_id:
                raise ValueError("Нет taskId в ответе")
            return self._query_task_result(task_id, output_dir)
        except Exception as e:
            print(f"❌ Ошибка замены мебели: {e}")
            raise
    
    def place_furniture_replace_multi(
        self,
        room_image_path: str,
        furniture_image_paths: List[str],
        output_dir: Path,
        replace_what: Optional[str] = None
    ) -> str:
        """Заменяет несколько предметов в комнате: коллаж новой мебели передаётся вторым изображением."""
        if len(furniture_image_paths) < 2:
            return self.place_furniture_replace(room_image_path, furniture_image_paths[0], output_dir, replace_what)
        collage_path = str(output_dir / f"replace_collage_{uuid.uuid4().hex}.png")
        try:
            create_furniture_collage(furniture_image_paths, collage_path, max_height=512, padding=40)
            return self.place_furniture_replace(room_image_path, collage_path, output_dir, replace_what)
        finally:
            try:
                if os.path.exists(collage_path):
                    os.remove(collage_path)
            except Exception:
                pass
    
    def _create_replace_prompt(self, replace_what: Optional[str] = None) -> str:
        """Промпт для замены старой мебели в комнате на новую. replace_what — что именно заменить (например 'sofa on the left')."""
        what_line = ""
        if replace_what and replace_what.strip():
            what_line = f" The furniture to replace in the room is: {replace_what.strip()}.\n\n"
        return f"""The first image is a room with existing furniture. The second image shows the NEW furniture (one or several items side by side) that should replace the corresponding old items.{what_line}
TASK: REPLACE the existing furniture in the room with the new furniture from the second image. If the second image contains multiple items, place each in the correct position (e.g. first item replaces first mentioned, second replaces second).
- Remove the old furniture completely.
- Place the new furniture in the SAME location and position where the old one was.
- Keep the rest of the room unchanged: walls, floor, other objects, lighting.
- Preserve the EXACT appearance of the new furniture (same color, texture, design).
- Match the room's lighting and add realistic shadows. The result must look photorealistic.
- The new furniture must stand ON THE FLOOR in a natural orientation, not on the wall."""

    def place_furniture(
        self,
        room_image_path: str,
        furniture_image_path: str,
        placement_params: Dict[str, Any],
        output_dir: Path
    ) -> str:
        """
        Размещает мебель в комнате используя Nano Banana Pro
        
        Args:
            room_image_path: Путь к изображению комнаты
            furniture_image_path: Путь к изображению мебели (без фона)
            placement_params: Параметры размещения от GPT-4V
            output_dir: Директория для сохранения результата
            
        Returns:
            Путь к результирующему изображению
        """
        try:
            # Загружаем изображение комнаты на хостинг (ImgBB). При недоступности — data URL
            print(f"📤 Загрузка изображения комнаты на хостинг...")
            room_url = self.uploader.upload_image(room_image_path, expiration=600)
            if not room_url:
                room_url = self.uploader.image_to_data_url(room_image_path)
                if room_url:
                    print(f"✅ Комната передана в base64 (ImgBB недоступен)")
            if not room_url:
                raise ValueError("Не удалось загрузить изображение комнаты на хостинг")
            
            # Поворот мебели если выбран (0/90)
            placement = placement_params.get("placement", {}) or {}
            rotation = placement.get("rotation", 0)
            rotated_path = None
            upload_path = furniture_image_path
            if rotation in (90, "90"):
                print("🔄 Поворот мебели на 90°...")
                img = Image.open(furniture_image_path).convert("RGBA")
                img = img.rotate(90, expand=True)
                rotated_path = str(output_dir / f"rotated_{uuid.uuid4()}.png")
                img.save(rotated_path)
                upload_path = rotated_path

            # Загружаем изображение мебели на хостинг (ImgBB). При недоступности — data URL
            print(f"📤 Загрузка изображения мебели на хостинг...")
            furniture_url = self.uploader.upload_image(upload_path, expiration=600)
            if not furniture_url:
                furniture_url = self.uploader.image_to_data_url(upload_path)
                if furniture_url:
                    print(f"✅ Мебель передана в base64 (ImgBB недоступен)")
            if not furniture_url:
                raise ValueError("Не удалось загрузить изображение мебели на хостинг")
            
            # Формируем промпт для Nano Banana Pro
            prompt = self._create_prompt(placement_params)
            
            print(f"🍌 Запуск Nano Banana Pro (Google DeepMind) на Kie.ai...")
            print(f"   Промпт: {prompt}")
            print(f"   Комната URL: {room_url}")
            print(f"   Мебель URL: {furniture_url}")
            
            # Определяем aspect ratio из размеров комнаты
            room_img = Image.open(room_image_path)
            aspect_ratio = self._get_aspect_ratio(room_img.size)
            
            # Подготавливаем payload согласно документации Nano Banana Pro
            payload = {
                "model": self.model_name,
                "input": {
                    "prompt": prompt,
                    "image_input": [room_url, furniture_url],  # До 8 изображений
                    "aspect_ratio": aspect_ratio,
                    "resolution": "1K",  # 1K быстрее; при необходимости можно вернуть 2K
                    "output_format": "png"
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
                timeout=30
            )
            
            print(f"📡 HTTP статус: {response.status_code}")
            
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ Ответ от Nano Banana Pro получен")
            print(f"   Код: {result.get('code')}, Сообщение: {result.get('message')}")
            
            # Проверяем успешность запроса
            if result.get('code') != 200:
                raise ValueError(f"Nano Banana Pro API ошибка: {result.get('message')}")
            
            data = result.get('data', {})
            
            # Получаем taskId для асинхронной обработки
            if 'taskId' in data:
                task_id = data['taskId']
                print(f"📋 Задача поставлена в очередь, taskId: {task_id}")
                print(f"⏳ Ожидание завершения обработки...")
                
                # Опрашиваем результат
                result_path = self._query_task_result(task_id, output_dir)
                return result_path
            else:
                raise ValueError("Не получен taskId от API")
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Ошибка запроса к Nano Banana Pro API: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                print(f"   Ответ сервера: {e.response.text}")
            raise
        except Exception as e:
            print(f"❌ Ошибка при генерации: {e}")
            raise
        finally:
            # Удаляем временный файл повёрнутой мебели
            try:
                if rotated_path and os.path.exists(rotated_path):
                    os.remove(rotated_path)
            except Exception:
                pass
    
    def _query_task_result(self, task_id: str, output_dir: Path, max_attempts: int = 240) -> str:
        """
        Опрашивает результат задачи через Query task API
        
        Args:
            task_id: ID задачи от Kie.ai
            output_dir: Директория для сохранения
            max_attempts: Максимальное количество попыток (по умолчанию 240 ≈ 8 мин при интервале 2 сек)
            
        Returns:
            Путь к результату
        """
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
                    state = data.get('state')
                    
                    if state == 'success':
                        print(f"✅ Задача завершена успешно!")
                        # Результат в поле resultJson
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
                        # Еще обрабатывается
                        if attempt % 5 == 0:
                            print(f"⏳ Статус: {state}, попытка {attempt + 1}/{max_attempts}")
                        time.sleep(2)
                else:
                    raise ValueError(f"Ошибка опроса задачи: {result.get('message')}")
                    
            except Exception as e:
                if attempt == max_attempts - 1:
                    raise Exception(f"Превышено время ожидания результата: {e}")
                time.sleep(2)
        
        raise TimeoutError("Превышено время ожидания результата от Nano Banana Pro")
    
    def _create_multi_placement_prompt(self, placement_params: Dict[str, Any], num_items: int) -> str:
        """
        Промпт для одного вызова: второе изображение — коллаж из N предметов (слева направо).
        Описываем позиции для каждого предмета в комнате.
        """
        room = placement_params.get("room_analysis", {})
        room_style = room.get("style", "modern")
        room_lighting = room.get("lighting", "natural lighting")
        furniture_items = placement_params.get("furniture_items", [])
        base_placement = placement_params.get("placement", {})
        
        parts = []
        for idx in range(num_items):
            item = next((x for x in furniture_items if x.get("index") == idx), None)
            if item and item.get("placement"):
                pl = item["placement"]
                xp = pl.get("x_percent", 50)
                yp = pl.get("y_percent", 60)
                wp = pl.get("width_percent", 30)
                hp = pl.get("height_percent", 25)
            else:
                xp = 25 + (idx * 50 / max(1, num_items - 1))
                yp = 55 + (idx % 2) * 10
                wp = 30 / num_items
                hp = 25 / num_items
            typ = (item or {}).get("type", "furniture item")
            color = (item or {}).get("color", "neutral")
            pos = f"center at {xp:.0f}% from left, {yp:.0f}% from top, area about {wp:.0f}% width and {hp:.0f}% height"
            parts.append(f"Item {idx + 1} (position {idx + 1} in the row, from left): {color} {typ} — place in the room {pos}.")
        
        placement_text = "\n".join(parts)
        
        return f"""The first image is the room. The second image is a reference sheet with {num_items} furniture items arranged in a row from LEFT to RIGHT (item 1 = leftmost, item {num_items} = rightmost).

Place each item from the second image into the {room_style} room at these positions:
{placement_text}

CRITICAL: Preserve the EXACT appearance of every furniture item - same colors, textures, and design. Integrate ALL items into the room in one coherent scene.
CRITICAL: Place ALL furniture ON THE FLOOR, standing normally. Do NOT put furniture on walls or vertically against the wall. Beds must be horizontal on the floor, chairs and sofas upright on the floor with legs on the ground.
Match the room's {room_lighting}. Add realistic shadows and reflections. Maintain photorealistic quality. Output in high resolution with sharp details."""

    def _create_prompt(self, placement_params: Dict[str, Any]) -> str:
        """
        Создает промпт для Nano Banana Pro (один предмет).
        
        Args:
            placement_params: Параметры от GPT-4V
            
        Returns:
            Детальный промпт
        """
        furniture = placement_params.get('furniture_analysis', {})
        room = placement_params.get('room_analysis', {})
        placement = placement_params.get('placement', {})
        
        furniture_type = furniture.get('type', 'furniture item')
        furniture_style = furniture.get('style', 'modern')
        furniture_color = furniture.get('color', 'neutral toned')
        room_style = room.get('style', 'modern')
        room_lighting = room.get('lighting', 'natural lighting')
        reasoning = placement.get('reasoning', '')
        # bbox placement hints (если есть)
        x_percent = placement.get("x_percent")
        y_percent = placement.get("y_percent")
        width_percent = placement.get("width_percent")
        height_percent = placement.get("height_percent")
        rotation = placement.get("rotation", 0)
        wall_alignment = placement.get("wall_alignment", "auto")
        
        # Промпт с акцентом на сохранение оригинала
        placement_hint = ""
        if None not in (x_percent, y_percent, width_percent, height_percent):
            placement_hint = (
                f"Place the furniture centered at approximately {x_percent:.1f}% from the left and "
                f"{y_percent:.1f}% from the top. Fit it inside a rectangle of about "
                f"{width_percent:.1f}% width and {height_percent:.1f}% height of the room image."
            )

        rotation_hint = ""
        if rotation == 90:
            rotation_hint = "The furniture is rotated 90 degrees to match the user's requested orientation (vertical vs horizontal)."

        wall_hint = ""
        if wall_alignment in ("right", "left", "back"):
            wall_name = {"right": "right wall", "left": "left wall", "back": "back wall"}[wall_alignment]
            wall_hint = (
                f"IMPORTANT: Place the sofa ALONG the {wall_name}, parallel to it, and flush against it. "
                f"Do NOT place it perpendicular across the room."
            )

        prompt = f"""Seamlessly integrate the exact {furniture_color} {furniture_type} from the second image into the {room_style} room from the first image.

CRITICAL: Preserve the EXACT appearance of the furniture - same color, texture, and design.

Placement: {placement_hint if placement_hint else (reasoning if reasoning else 'Place it naturally in the room where it fits best')}
{rotation_hint}
{wall_hint}

Requirements:
- Match the room's {room_lighting}
- Add realistic shadows and reflections
- Adjust perspective to fit naturally
- Maintain photorealistic quality
- Keep furniture IDENTICAL to the original image
- Blend seamlessly with the interior
- CRITICAL: Place furniture ON THE FLOOR, standing normally. Do NOT put it on the wall or vertically. Beds horizontal on the floor, chairs/sofas upright with legs on the ground.

Output in high resolution with sharp details."""
        
        return prompt.strip()
    
    def _get_aspect_ratio(self, image_size: tuple) -> str:
        """
        Определяет aspect ratio из размеров изображения
        
        Args:
            image_size: (width, height)
            
        Returns:
            Строка aspect ratio для API
        """
        width, height = image_size
        ratio = width / height
        
        # Определяем ближайший стандартный aspect ratio
        if 0.95 < ratio < 1.05:
            return "1:1"
        elif 1.3 < ratio < 1.4:
            return "4:3"
        elif 1.5 < ratio < 1.6:
            return "3:2"
        elif 1.7 < ratio < 1.9:
            return "16:9"
        elif 2.2 < ratio < 2.4:
            return "21:9"
        elif 0.6 < ratio < 0.7:
            return "2:3"
        elif 0.7 < ratio < 0.8:
            return "3:4"
        elif 0.5 < ratio < 0.6:
            return "9:16"
        else:
            return "auto"
    
    def get_model_name(self) -> str:
        """Возвращает название модели"""
        return "Nano Banana Pro (Google DeepMind)"
    
    def get_estimated_time(self) -> int:
        """Возвращает примерное время генерации"""
        return 60  # ~60 секунд для 2K
    
    def preserves_original(self) -> bool:
        """Сохраняет оригинальный вид мебели"""
        return False  # AI генерация, может немного изменить
