"""
Сервис для анализа изображений с помощью Gemini 2.5 Pro через Kie.ai
"""
import json
import requests
from typing import Dict, Any, Optional, Tuple
from ..utils.load_env import get_env_variable
from .image_uploader import ImageUploader


class GPT4Analyzer:
    """
    Класс для анализа комнаты и мебели с помощью GPT-4 Vision
    """
    
    def __init__(self):
        """Инициализация клиента Kie.ai для Gemini"""
        self.api_key = get_env_variable('KIE_AI_API_KEY')
        self.api_url = "https://api.kie.ai/gemini-2.5-pro/v1/chat/completions"
        self.uploader = ImageUploader()
    
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
            # Загружаем изображения на imgbb для получения публичных URL
            print(f"📤 Загрузка изображений на хостинг...")
            room_url = self.uploader.upload_image(room_image_path, expiration=600)
            furniture_url = self.uploader.upload_image(furniture_image_path, expiration=600)
            
            if not room_url or not furniture_url:
                raise ValueError("Не удалось загрузить изображения на хостинг")
            
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
            
            # Отправляем запрос к Kie.ai Gemini API
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            
            response.raise_for_status()
            result = response.json()
            
            print(f"✅ Ответ от Gemini получен")
            print(f"📋 Полный ответ: {json.dumps(result, ensure_ascii=False)[:500]}")
            
            # Извлекаем текст ответа из формата Chat Completions
            if 'choices' in result and len(result['choices']) > 0:
                message = result['choices'][0].get('message', {})
                content = message.get('content', '')
                if not content:
                    print(f"⚠️  Пустой content в message: {message}")
                    raise ValueError("Gemini вернул пустой content")
                print(f"📝 Content от Gemini: {content[:200]}...")
                analysis = self._parse_analysis(content)
                return analysis
            else:
                print(f"⚠️  Нет choices в ответе или choices пустой. Ключи ответа: {list(result.keys())}")
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
