"""
Сервис для генерации рекомендаций доп товаров (upsell) через Gemini.
Рекомендуем только то, что реально подходит по стилю и функции.
"""
from pathlib import Path
from typing import List, Dict, Any
import json
import requests

from ..utils.load_env import get_env_variable


class UpsellService:
    """
    Сервис для умных рекомендаций дополнительных товаров через Gemini
    """
    
    def __init__(self):
        """Инициализация клиента Kie.ai для Gemini"""
        self.api_key = get_env_variable('KIE_AI_API_KEY')
        self.api_url = "https://api.kie.ai/gemini-2.5-pro/v1/chat/completions"
    
    def generate_recommendations(
        self,
        placed_furniture: Dict[str, Any],
        room_analysis: Dict[str, Any],
        catalog_items: List[Dict[str, Any]],
        max_recommendations: int = 4,
        exclude_item_paths: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Генерирует рекомендации дополнительных товаров через Gemini.
        Рекомендует только то, что реально подходит по стилю и функции; не рекомендует уже размещённое.
        """
        exclude_item_paths = exclude_item_paths or []
        catalog_available = self._exclude_placed_from_catalog(catalog_items, exclude_item_paths)
        # Не подставляем весь каталог, если пользователь уже всё применил — рекомендуем только оставшееся
        if len(catalog_available) < max_recommendations:
            pass  # работаем с тем, что осталось; пустой список вернётся и бэкенд отдаст сообщение
        if not catalog_available:
            return []
        try:
            prompt = self._create_upsell_prompt(
                placed_furniture,
                room_analysis,
                catalog_available,
                max_recommendations
            )
            
            # Запрос к Gemini через Kie.ai
            payload = {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }
                ],
                "stream": False,
                "include_thoughts": False,
                "reasoning_effort": "high"
            }
            
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
            
            # Извлекаем ответ
            if 'choices' in result and len(result['choices']) > 0:
                content = result['choices'][0]['message']['content']
                recommendations = self._parse_recommendations(content, catalog_available)
                return recommendations[:max_recommendations]
            else:
                print(f"⚠️  Нет ответа от Gemini для upsell")
                return []
            
        except Exception as e:
            print(f"❌ Ошибка генерации рекомендаций: {e}")
            return []
    
    def _exclude_placed_from_catalog(
        self,
        catalog_items: List[Dict[str, Any]],
        exclude_paths: List[str]
    ) -> List[Dict[str, Any]]:
        """Исключает из каталога товары, которые пользователь уже разместил в этой визуализации."""
        if not exclude_paths:
            return list(catalog_items)
        exclude_names = {Path(p).name.lower() for p in exclude_paths}
        return [
            item for item in catalog_items
            if Path(item.get("image_path", "")).name.lower() not in exclude_names
        ]

    def _create_upsell_prompt(
        self,
        placed_furniture: Dict[str, Any],
        room_analysis: Dict[str, Any],
        catalog_items: List[Dict[str, Any]],
        max_recommendations: int
    ) -> str:
        """Промпт: рекомендуй только товары из списка, реально подходящие по стилю и функции."""
        furniture_type = placed_furniture.get('type', 'мебель')
        furniture_style = placed_furniture.get('style', 'современный')
        furniture_color = placed_furniture.get('color', 'нейтральный')
        room_style = room_analysis.get('style', 'современный')
        room_lighting = room_analysis.get('lighting', 'естественное')
        
        names_list = [item['name'] for item in catalog_items]
        catalog_text = "\n".join([
            f"- «{item['name']}»: {item.get('description', '')} (стиль: {item.get('style', '')}, тип: {item.get('type', '')})"
            for item in catalog_items
        ])
        
        return f"""Ты эксперт по интерьерному дизайну и подбору мебели.

Клиент только что разместил в комнате: {furniture_type}. Стиль мебели: {furniture_style}, цвет: {furniture_color}.
Комната: стиль {room_style}, освещение {room_lighting}.

Доступные товары в каталоге (рекомендовать можно ТОЛЬКО их, другими словами — нельзя):
{catalog_text}

Задача: порекомендуй ровно {max_recommendations} товара из этого списка, которые РЕАЛЬНО подойдут:
1. По стилю — сочетаются с уже размещённой мебелью и комнатой.
2. По функции — логично дополняют интерьер (например к кровати — тумбочка/светильник, к дивану — кресло/столик).
3. НЕ рекомендуй то, что клиент уже разместил (в списке выше только то, что ещё можно предложить).

Критично: в ответе в поле item_name указывай ТОЧНО название из каталога, без изменений. Допустимые названия: {names_list}.

Формат ответа — только JSON, без текста до и после:
{{
  "recommendations": [
    {{
      "item_name": "точное название из каталога",
      "reason": "кратко: почему именно этот товар подойдёт в этот интерьер",
      "category": "функциональное дополнение / стилистическое сочетание / акцент"
    }}
  ]
}}"""
    
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
            seen_ids = set()
            
            # Точное совпадение по имени, затем по вхождению
            catalog_by_name = {item['name'].strip(): item for item in catalog_items}
            catalog_by_name_lower = {k.lower(): v for k, v in catalog_by_name.items()}
            
            for rec in data.get('recommendations', []):
                item_name = (rec.get('item_name') or '').strip()
                if not item_name:
                    continue
                catalog_item = catalog_by_name.get(item_name) or catalog_by_name_lower.get(item_name.lower())
                if not catalog_item:
                    for cname, citem in catalog_by_name_lower.items():
                        if item_name.lower() in cname or cname in item_name.lower():
                            catalog_item = citem
                            break
                if catalog_item and catalog_item.get('id') not in seen_ids:
                    seen_ids.add(catalog_item.get('id'))
                    recommendations.append({
                        **catalog_item,
                        'recommendation_reason': rec.get('reason', 'Подойдёт к вашему интерьеру'),
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
        count: int = 3,
        exclude_item_paths: List[str] = None,
        room_style: str = ""
    ) -> List[Dict[str, Any]]:
        """
        Рекомендации без AI (fallback): по типу мебели и стилю комнаты.
        Исключаем уже размещённое; даём конкретную причину по каждому товару.
        """
        available = self._exclude_placed_from_catalog(catalog_items, exclude_item_paths or [])
        if not available:
            return []
        
        # Что логично дополняет уже размещённое
        complements = {
            'диван': ['кресло', 'столик', 'торшер', 'пуф'],
            'кровать': ['кресло', 'тумбочка', 'комод', 'светильник', 'зеркало'],
            'стол': ['стул', 'кресло', 'люстра'],
            'кресло': ['торшер', 'столик', 'кровать', 'диван'],
            'шкаф': ['зеркало', 'пуф', 'вешалка'],
            'мебель': ['кресло', 'кровать', 'стол'],
        }
        ft_lower = (furniture_type or "мебель").lower()
        keywords = complements.get(ft_lower, complements['мебель'])
        style_words = (room_style or "").lower().split()
        
        recommendations = []
        for item in available:
            name = item.get('name', '').lower()
            desc = (item.get('description') or '').lower()
            typ = (item.get('type') or '').lower()
            style = (item.get('style') or '').lower()
            for kw in keywords:
                if kw in name or kw in desc or kw in typ:
                    reason = f"Дополняет {furniture_type}: подойдёт по стилю и функции."
                    if style_words and any(s in style for s in style_words):
                        reason = f"Сочетается со стилем интерьера и дополняет {furniture_type}."
                    recommendations.append({
                        **item,
                        'recommendation_reason': reason,
                        'recommendation_category': 'дополнение'
                    })
                    break
            if len(recommendations) >= count:
                break
        
        if len(recommendations) < count:
            seen = {r.get('id') for r in recommendations}
            for item in available:
                if item.get('id') in seen:
                    continue
                seen.add(item.get('id'))
                recommendations.append({
                    **item,
                    'recommendation_reason': f"Подойдёт к вашему интерьеру и сочетается с {furniture_type}.",
                    'recommendation_category': 'дополнение'
                })
                if len(recommendations) >= count:
                    break
        
        return recommendations[:count]
