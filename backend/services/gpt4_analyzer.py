"""
Сервис для анализа изображений с помощью Gemini 2.5 Pro через Kie.ai
"""
import json
import time
import requests
from typing import Dict, Any, Optional, Tuple, List
from ..utils.load_env import get_env_variable
from .image_uploader import ImageUploader

KIE_RETRY_COUNT = 3
KIE_RETRY_DELAY = 15


class GPT4Analyzer:
    """
    Класс для анализа комнаты и мебели с помощью GPT-4 Vision
    """
    
    def __init__(self):
        """Инициализация клиента Kie.ai для Gemini"""
        self.api_key = get_env_variable('KIE_AI_API_KEY')
        self.api_url = "https://api.kie.ai/gemini-2.5-pro/v1/chat/completions"
        self.uploader = ImageUploader()
    
    def analyze_multi_furniture_placement(
        self,
        room_image_path: str,
        furniture_image_paths: List[str],
        manual_position: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        """
        Анализирует где и как разместить несколько предметов мебели в комнате
        
        Args:
            room_image_path: Путь к изображению комнаты
            furniture_image_paths: Массив путей к изображениям мебели (до 5)
            manual_position: Опциональная ручная позиция (x, y) в пикселях
            
        Returns:
            Словарь с анализом и параметрами размещения всех предметов
        """
        
        try:
            # Kie.ai возвращает 422 "Failed to get the file information" при ссылках на ImgBB — не может загрузить по URL.
            # Поэтому для Gemini всегда передаём изображения в base64 (data URL).
            print(f"📤 Подготовка изображений для Gemini (base64)...")
            room_url = self.uploader.image_to_data_url(room_image_path)
            if not room_url:
                raise ValueError("Не удалось прочитать изображение комнаты")
            
            furniture_urls = []
            for fpath in furniture_image_paths:
                furl = self.uploader.image_to_data_url(fpath)
                if not furl:
                    raise ValueError(f"Не удалось прочитать изображение мебели: {fpath}")
                furniture_urls.append(furl)
            
            # Формируем промпт
            if manual_position:
                prompt_data = self._create_multi_manual_placement_prompt(manual_position, len(furniture_urls))
            else:
                prompt_data = self._create_multi_auto_placement_prompt(len(furniture_urls))
            
            # Объединяем system и user промпты
            full_prompt = f"{prompt_data['system']}\n\n{prompt_data['user']}"
            
            print(f"🤖 Запуск Gemini 2.5 Pro для анализа {len(furniture_urls)} предметов...")
            
            # Формируем content с комнатой + всеми предметами мебели
            content = [
                {
                    "type": "text",
                    "text": full_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": room_url
                    }
                }
            ]
            
            # Добавляем все изображения мебели
            for furl in furniture_urls:
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": furl
                    }
                })
            
            # Подготавливаем payload
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": content
                    }
                ],
                "stream": False,
                "include_thoughts": False,
                "reasoning_effort": "high"
            }
            
            # Отправляем запрос к Kie.ai (с повтором при maintenance)
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            result = None
            for attempt in range(KIE_RETRY_COUNT):
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=90
                )
                result = response.json()
                # 422 = Kie.ai не смог получить файл (при ссылках). Мы шлём base64 — 422 не должно быть.
                if response.status_code == 422 or (result.get("code") == 422 and "file" in (result.get("msg") or "").lower()):
                    raise ValueError(f"Gemini отклонил изображения: {result.get('msg', '')}")
                response.raise_for_status()
                
                if result.get("code") == 500 and "maintained" in (result.get("msg") or "").lower():
                    if attempt < KIE_RETRY_COUNT - 1:
                        print(f"⏳ Kie.ai на обслуживании, повтор через {KIE_RETRY_DELAY} сек... ({attempt + 1}/{KIE_RETRY_COUNT})")
                        time.sleep(KIE_RETRY_DELAY)
                        continue
                    raise ValueError("Kie.ai временно недоступен (maintenance). Попробуйте позже.")
                
                break
            
            print(f"✅ Ответ от Gemini получен")
            
            # Извлекаем текст ответа
            if result and 'choices' in result and len(result['choices']) > 0:
                message = result['choices'][0].get('message', {})
                content_text = message.get('content', '')
                if not content_text:
                    print(f"⚠️  Пустой content в message: {message}")
                    raise ValueError("Gemini вернул пустой content")
                print(f"📝 Content от Gemini: {content_text[:200]}...")
                analysis = self._parse_analysis(content_text)
                return analysis
            else:
                print(f"⚠️  Нет choices в ответе. Ключи: {list(result.keys()) if result else []}")
                raise ValueError("Не получен корректный ответ от Gemini API")
            
        except Exception as e:
            print(f"❌ Ошибка при анализе с Gemini: {e}")
            raise
    
    def analyze_room_for_replace(self, room_image_path: str) -> Dict[str, Any]:
        """
        Анализирует фото комнаты и возвращает список мебели, которую можно заменить.
        Используется в режиме «Заменить мебель»: ИИ предлагает, что заменить (диван, стол, кресло и т.д.).
        
        Returns:
            {"items": [{"type": "sofa", "position": "left"}, {"type": "table", "position": "center"}, ...]}
        """
        try:
            print(f"📤 Подготовка изображения комнаты для анализа (base64)...")
            room_url = self.uploader.image_to_data_url(room_image_path)
            if not room_url:
                raise ValueError("Не удалось прочитать изображение комнаты")
            
            prompt = """Look at this room interior photo. List ONLY the furniture that you CLEARLY SEE in the image. Do NOT invent or assume anything that is not visible (e.g. if there is no bed, do not list a bed).
For each item that is actually visible provide: "type" (one word in English: sofa, table, bed, chair, desk, cabinet, armchair, etc.) and "position" (left / center / right).
CRITICAL: Include only items that are unambiguously present in the photo. If in doubt, omit the item.
Return ONLY a valid JSON object, no markdown, no code block. Example:
{"items": [{"type": "table", "position": "center"}, {"type": "chair", "position": "right"}]}
If you see no clear furniture, return {"items": []}."""
            
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": room_url}}
                        ]
                    }
                ],
                "stream": False,
                "include_thoughts": False,
                "reasoning_effort": "medium"
            }
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            for attempt in range(KIE_RETRY_COUNT):
                response = requests.post(self.api_url, headers=headers, json=payload, timeout=60)
                result = response.json()
                if response.status_code == 422:
                    raise ValueError("Не удалось отправить изображение в Gemini")
                response.raise_for_status()
                if result.get("code") == 500 and "maintained" in (result.get("msg") or "").lower():
                    if attempt < KIE_RETRY_COUNT - 1:
                        time.sleep(KIE_RETRY_DELAY)
                        continue
                    raise ValueError("Kie.ai временно недоступен")
                break
            
            if not result or 'choices' not in result or len(result['choices']) == 0:
                return {"items": []}
            content = result['choices'][0].get('message', {}).get('content', '')
            if not content:
                return {"items": []}
            # Убираем возможную обёртку в markdown
            text = content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
            data = json.loads(text)
            items = data.get("items", [])
            if not isinstance(items, list):
                return {"items": []}
            # Нормализуем: только type и position
            out = []
            for it in items:
                if isinstance(it, dict) and it.get("type"):
                    out.append({
                        "type": str(it.get("type", "")).strip().lower() or "furniture",
                        "position": str(it.get("position", "center")).strip().lower() or "center"
                    })
            return {"items": out}
        except json.JSONDecodeError as e:
            print(f"⚠️  Не удалось распарсить JSON анализа комнаты: {e}")
            return {"items": []}
        except Exception as e:
            print(f"❌ Ошибка анализа комнаты для замены: {e}")
            raise
    
    def analyze_placement(
        self,
        room_image_path: str,
        furniture_image_path: str,
        manual_position: Optional[Tuple[int, int]] = None
    ) -> Dict[str, Any]:
        """
        Анализирует где и как разместить мебель в комнате
        
        Args:
            room_image_path: Путь к изображению комнаты
            furniture_image_path: Путь к изображению мебели
            manual_position: Опциональная ручная позиция (x, y) в пикселях
            
        Returns:
            Словарь с анализом и параметрами размещения
        """
        
        try:
            # Для Gemini передаём base64 (Kie.ai даёт 422 на внешние URL ImgBB)
            print(f"📤 Подготовка изображений для Gemini (base64)...")
            room_url = self.uploader.image_to_data_url(room_image_path)
            furniture_url = self.uploader.image_to_data_url(furniture_image_path)
            if not room_url or not furniture_url:
                raise ValueError("Не удалось прочитать изображения")
            
            # Формируем промпт в зависимости от режима
            if manual_position:
                prompt_data = self._create_manual_placement_prompt(manual_position)
            else:
                prompt_data = self._create_auto_placement_prompt()
            
            # Объединяем system и user промпты
            full_prompt = f"{prompt_data['system']}\n\n{prompt_data['user']}"
            
            print(f"🤖 Запуск Gemini 2.5 Pro на Kie.ai...")
            
            # Подготавливаем payload в формате Chat Completions API
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": full_prompt
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": room_url
                                }
                            },
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": furniture_url
                                }
                            }
                        ]
                    }
                ],
                "stream": False,
                "include_thoughts": False,
                "reasoning_effort": "high"
            }
            
            # Отправляем запрос к Kie.ai (с повтором при maintenance)
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            result = None
            for attempt in range(KIE_RETRY_COUNT):
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    json=payload,
                    timeout=60
                )
                result = response.json()
                if response.status_code == 422 or (result.get("code") == 422 and "file" in (result.get("msg") or "").lower()):
                    raise ValueError(f"Gemini отклонил изображения: {result.get('msg', '')}")
                response.raise_for_status()
                
                if result.get("code") == 500 and "maintained" in (result.get("msg") or "").lower():
                    if attempt < KIE_RETRY_COUNT - 1:
                        print(f"⏳ Kie.ai на обслуживании, повтор через {KIE_RETRY_DELAY} сек... ({attempt + 1}/{KIE_RETRY_COUNT})")
                        time.sleep(KIE_RETRY_DELAY)
                        continue
                    raise ValueError("Kie.ai временно недоступен (maintenance). Попробуйте позже.")
                
                break
            
            print(f"✅ Ответ от Gemini получен")
            
            # Извлекаем текст ответа из формата Chat Completions
            if result and 'choices' in result and len(result['choices']) > 0:
                message = result['choices'][0].get('message', {})
                content = message.get('content', '')
                if not content:
                    print(f"⚠️  Пустой content в message: {message}")
                    raise ValueError("Gemini вернул пустой content")
                print(f"📝 Content от Gemini: {content[:200]}...")
                analysis = self._parse_analysis(content)
                return analysis
            else:
                print(f"⚠️  Нет choices в ответе. Ключи: {list(result.keys()) if result else []}")
                raise ValueError("Не получен корректный ответ от Gemini API")
            
        except Exception as e:
            print(f"❌ Ошибка при анализе с Gemini: {e}")
            raise
    
    def _create_auto_placement_prompt(self) -> Dict[str, str]:
        """Создает промпт для автоматического размещения"""
        return {
            "system": """Ты эксперт по интерьерному дизайну и 3D-композиции.
Твоя задача - проанализировать фото комнаты и мебели, определить ЛУЧШЕЕ место для размещения мебели.

КРИТИЧЕСКИ ВАЖНО: 
- Комната и мебель должны остаться ПОЛНОСТЬЮ неизменными!
- Описывай мебель МАКСИМАЛЬНО точно и детально
- Укажи ТОЧНЫЙ цвет, ТОЧНУЮ форму, ТОЧНЫЕ детали
- Ты определяешь только область куда вставить мебель БЕЗ изменения её внешнего вида
- Учитывай перспективу, освещение, пропорции

Верни ответ СТРОГО в JSON формате.""",
            
            "user": """Проанализируй эти изображения:
1. Первое изображение - комната
2. Второе изображение - мебель

Определи:
1. Характеристики комнаты (размер, освещение, стиль, перспектива)
2. Характеристики мебели - БУДЬ МАКСИМАЛЬНО ТОЧНЫМ В ОПИСАНИИ!
3. ЛУЧШЕЕ место для размещения мебели

Верни JSON:
{
  "room_analysis": {
    "size_estimate": "примерный размер в метрах",
    "lighting": "описание освещения",
    "style": "стиль интерьера",
    "perspective": "описание перспективы камеры",
    "free_spaces": ["список свободных мест"]
  },
  "furniture_analysis": {
    "type": "тип мебели (диван, кресло, стол...)",
    "estimated_size": "примерный размер в метрах",
    "style": "детальное описание стиля",
    "color": "ТОЧНЫЙ цвет с оттенком (например: 'deep purple', 'burgundy', 'dark violet')",
    "features": ["детальные особенности: форма подлокотников, тип обивки, наличие подушек, форма ножек и т.д."]
  },
  "placement": {
    "x_percent": 50,
    "y_percent": 60,
    "width_percent": 35,
    "height_percent": 25,
    "scale": 0.85,
    "rotation": 15,
    "reasoning": "почему это лучшее место"
  },
  "inpainting_prompt": "НЕ используется - оставь пустым"
}

ВАЖНО: 
- Опиши цвет мебели МАКСИМАЛЬНО точно
- Опиши все визуальные детали мебели
- Укажи материал и текстуру если видно

Координаты в процентах от размера изображения."""
        }
    
    def _create_manual_placement_prompt(self, position: Tuple[int, int]) -> Dict[str, str]:
        """Создает промпт для ручного размещения"""
        x, y = position
        return {
            "system": """Ты эксперт по интерьерному дизайну.
Пользователь указал конкретное место где хочет разместить мебель.
Твоя задача - определить правильный размер и параметры для этого места.

ВАЖНО: НЕ меняй детали комнаты!""",
            
            "user": f"""Пользователь хочет разместить мебель в позиции ({x}, {y}).

Проанализируй:
1. Подходит ли это место для данной мебели
2. Какой размер должна иметь мебель в этом месте
3. Под каким углом её разместить

Изображения:
1. Первое - комната
2. Второе - мебель

Верни JSON как в предыдущем примере, но используй указанную позицию."""
        }
    
    def _create_multi_auto_placement_prompt(self, furniture_count: int) -> Dict[str, str]:
        """Создает промпт для автоматического размещения нескольких предметов"""
        return {
            "system": f"""Ты эксперт по интерьерному дизайну и 3D-композиции.
Твоя задача - проанализировать фото комнаты и {furniture_count} предметов мебели, определить ЛУЧШЕЕ размещение для КАЖДОГО предмета так, чтобы они гармонично сочетались.

КРИТИЧЕСКИ ВАЖНО:
- Все предметы должны остаться ПОЛНОСТЬЮ неизменными!
- Опис

ывай каждый предмет МАКСИМАЛЬНО точно и детально
- Укажи ТОЧНЫЙ цвет, ТОЧНУЮ форму, ТОЧНЫЕ детали каждого
- Размещай предметы так, чтобы они не перекрывали друг друга
- Учитывай перспективу, освещение, пропорции

Верни ответ СТРОГО в JSON формате.""",
            
            "user": f"""Проанализируй эти изображения:
1. Первое изображение - комната
2. Следующие {furniture_count} изображений - предметы мебели

Определи для КАЖДОГО предмета:
1. Характеристики (тип, размер, цвет, стиль)
2. ЛУЧШЕЕ место для размещения
3. Как предметы сочетаются между собой

Верни JSON:
{{
  "room_analysis": {{
    "size_estimate": "примерный размер в метрах",
    "lighting": "описание освещения",
    "style": "стиль интерьера",
    "perspective": "описание перспективы камеры",
    "free_spaces": ["список свободных мест"]
  }},
  "furniture_items": [
    {{
      "index": 0,
      "type": "тип мебели",
      "estimated_size": "размер",
      "style": "стиль",
      "color": "ТОЧНЫЙ цвет",
      "features": ["особенности"],
      "placement": {{
        "x_percent": 50,
        "y_percent": 60,
        "width_percent": 35,
        "height_percent": 25,
        "scale": 0.85,
        "rotation": 15,
        "reasoning": "почему это место"
      }}
    }}
  ],
  "overall_composition": "как предметы сочетаются между собой"
}}

Координаты в процентах от размера изображения."""
        }
    
    def _create_multi_manual_placement_prompt(self, position: Tuple[int, int], furniture_count: int) -> Dict[str, str]:
        """Создает промпт для ручного размещения нескольких предметов"""
        x, y = position
        return {
            "system": f"""Ты эксперт по интерьерному дизайну.
Пользователь указал место где хочет разместить {furniture_count} предметов мебели.
Определи размеры и параметры для каждого предмета.""",
            
            "user": f"""Пользователь выбрал позицию ({x}, {y}) для размещения {furniture_count} предметов.

Проанализируй все предметы и определи их оптимальное размещение в этой области.

Изображения:
1. Первое - комната
2. Следующие {furniture_count} - предметы мебели

Верни JSON в том же формате что и для автоматического размещения."""
        }
    
    def _parse_analysis(self, content: str) -> Dict[str, Any]:
        """
        Парсит ответ GPT-4V и извлекает JSON
        
        Args:
            content: Текст ответа от GPT-4V
            
        Returns:
            Распарсенный JSON
        """
        try:
            # Ищем JSON в ответе (может быть обернут в markdown)
            if "```json" in content:
                json_start = content.find("```json") + 7
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            elif "```" in content:
                json_start = content.find("```") + 3
                json_end = content.find("```", json_start)
                json_str = content[json_start:json_end].strip()
            else:
                json_str = content.strip()
            
            # Парсим JSON
            analysis = json.loads(json_str)
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"⚠️  Ошибка парсинга JSON от GPT-4V: {e}")
            print(f"Ответ: {content}")
            
            # Возвращаем дефолтные значения
            return {
                "room_analysis": {
                    "size_estimate": "unknown",
                    "lighting": "natural",
                    "style": "modern",
                    "perspective": "eye-level"
                },
                "furniture_analysis": {
                    "type": "furniture",
                    "estimated_size": "medium",
                    "style": "modern",
                    "color": "neutral"
                },
                "placement": {
                    "x_percent": 50,
                    "y_percent": 50,
                    "width_percent": 30,
                    "height_percent": 30,
                    "scale": 1.0,
                    "rotation": 0,
                    "reasoning": "Default placement"
                },
                "inpainting_prompt": f"Place furniture in the room, photorealistic, natural lighting"
            }
