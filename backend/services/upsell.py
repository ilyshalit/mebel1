"""
Сервис для генерации рекомендаций доп товаров (upsell)
"""
from typing import List, Dict, Any
from openai import OpenAI
import json

from ..utils.load_env import get_env_variable


class UpsellService:
    """
    Сервис для умных рекомендаций дополнительных товаров
    """
    
    def __init__(self):
        """Инициализация клиента OpenAI"""
        api_key = get_env_variable('OPENAI_API_KEY')
        self.client = OpenAI(api_key=api_key)
        # Используем более дешевую модель для upsell
        self.model = "gpt-4-turbo-preview"
    
    def generate_recommendations(
        self,
        placed_furniture: Dict[str, Any],
        room_analysis: Dict[str, Any],
        catalog_items: List[Dict[str, Any]],
        max_recommendations: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Генерирует рекомендации дополнительных товаров
        
        Args:
            placed_furniture: Информация о размещенной мебели
            room_analysis: Анализ комнаты
            catalog_items: Список товаров из каталога
            max_recommendations: Максимальное количество рекомендаций
            
        Returns:
            Список рекомендованных товаров с объяснениями
        """
        try:
            # Формируем промпт
            prompt = self._create_upsell_prompt(
                placed_furniture,
                room_analysis,
                catalog_items,
                max_recommendations
            )
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """Ты эксперт по продажам мебели и интерьерному дизайну.
Твоя задача - рекомендовать дополнительные товары, которые:
1. Стилистически подходят к уже выбранной мебели
2. Функционально дополняют интерьер
3. Создают гармоничную композицию

Будь конкретным и убедительным, но не навязчивым."""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.7,
                max_tokens=1000
            )
            
            # Парсим ответ
            content = response.choices[0].message.content
            recommendations = self._parse_recommendations(content, catalog_items)
            
            return recommendations[:max_recommendations]
            
        except Exception as e:
            print(f"❌ Ошибка генерации рекомендаций: {e}")
            return []
    
    def _create_upsell_prompt(
        self,
        placed_furniture: Dict[str, Any],
        room_analysis: Dict[str, Any],
        catalog_items: List[Dict[str, Any]],
        max_recommendations: int
    ) -> str:
        """Создает промпт для генерации рекомендаций"""
        
        # Информация о размещенной мебели
        furniture_type = placed_furniture.get('type', 'мебель')
        furniture_style = placed_furniture.get('style', 'современный')
        furniture_color = placed_furniture.get('color', 'нейтральный')
        
        # Информация о комнате
        room_style = room_analysis.get('style', 'современный')
        room_lighting = room_analysis.get('lighting', 'естественное')
        
        # Формируем список товаров из каталога
        catalog_text = "\n".join([
            f"- {item['name']}: {item.get('description', '')} (стиль: {item.get('style', 'N/A')}, цена: {item.get('price', 'N/A')})"
            for item in catalog_items
        ])
        
        prompt = f"""Клиент только что разместил в своей комнате: {furniture_type}
Характеристики выбранной мебели:
- Стиль: {furniture_style}
- Цвет: {furniture_color}

Характеристики комнаты:
- Стиль интерьера: {room_style}
- Освещение: {room_lighting}

Доступные товары в каталоге:
{catalog_text}

Порекомендуй {max_recommendations} товара из каталога, которые:
1. Стилистически сочетаются с выбранной мебелью
2. Функционально дополняют интерьер
3. Помогут создать завершенную композицию

Для каждой рекомендации объясни ПОЧЕМУ это подходит (1-2 предложения).

Формат ответа (JSON):
{{
  "recommendations": [
    {{
      "item_name": "название товара из каталога",
      "reason": "почему этот товар подходит",
      "category": "функциональное дополнение / стилистическое сочетание / акцент"
    }}
  ]
}}"""
        
        return prompt
    
    def _parse_recommendations(
        self,
        content: str,
        catalog_items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Парсит рекомендации из ответа GPT
        
        Args:
            content: Текст ответа
            catalog_items: Список товаров из каталога
            
        Returns:
            Список рекомендаций с полной информацией
        """
        try:
            # Извлекаем JSON
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
            
            data = json.loads(json_str)
            recommendations = []
            
            # Создаем индекс товаров по имени
            catalog_index = {item['name'].lower(): item for item in catalog_items}
            
            for rec in data.get('recommendations', []):
                item_name = rec.get('item_name', '')
                
                # Ищем товар в каталоге
                catalog_item = None
                for key, value in catalog_index.items():
                    if key in item_name.lower() or item_name.lower() in key:
                        catalog_item = value
                        break
                
                if catalog_item:
                    recommendations.append({
                        **catalog_item,
                        'recommendation_reason': rec.get('reason', ''),
                        'recommendation_category': rec.get('category', 'дополнение')
                    })
            
            return recommendations
            
        except Exception as e:
            print(f"⚠️  Ошибка парсинга рекомендаций: {e}")
            # Возвращаем первые несколько товаров из каталога как fallback
            return catalog_items[:3]
    
    def get_simple_recommendations(
        self,
        furniture_type: str,
        catalog_items: List[Dict[str, Any]],
        count: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Простые рекомендации без AI (fallback)
        
        Args:
            furniture_type: Тип размещенной мебели
            catalog_items: Каталог товаров
            count: Количество рекомендаций
            
        Returns:
            Список рекомендаций
        """
        # Простая логика: рекомендуем комплементарные товары
        complements = {
            'диван': ['кресло', 'журнальный столик', 'торшер', 'подушки'],
            'кровать': ['тумбочка', 'комод', 'светильник', 'зеркало'],
            'стол': ['стулья', 'люстра', 'ваза'],
            'кресло': ['торшер', 'журнальный столик', 'подставка для ног'],
            'шкаф': ['зеркало', 'пуф', 'вешалка']
        }
        
        keywords = complements.get(furniture_type.lower(), [])
        
        # Фильтруем товары по ключевым словам
        recommendations = []
        for item in catalog_items:
            item_name_lower = item.get('name', '').lower()
            item_desc_lower = item.get('description', '').lower()
            
            for keyword in keywords:
                if keyword in item_name_lower or keyword in item_desc_lower:
                    recommendations.append(item)
                    break
            
            if len(recommendations) >= count:
                break
        
        # Если недостаточно, добавляем случайные
        if len(recommendations) < count:
            for item in catalog_items:
                if item not in recommendations:
                    recommendations.append(item)
                if len(recommendations) >= count:
                    break
        
        return recommendations[:count]
