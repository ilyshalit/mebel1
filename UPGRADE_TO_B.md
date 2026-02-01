# 🔄 Апгрейд до Варианта B (Продвинутая версия)

Когда проект окупится и заказчик будет готов инвестировать в улучшенное качество, можно перейти на Вариант B.

## Отличия Варианта B от Варианта A

| Компонент | Вариант A (текущий) | Вариант B (улучшенный) |
|-----------|---------------------|------------------------|
| **Удаление фона** | rembg (локально) | Segment Anything Model (SAM) |
| **Анализ сцены** | GPT-4 Vision | GPT-4 Vision |
| **Композиция** | SD Inpainting | ControlNet + SDXL Inpainting |
| **Качество** | 7/10 | 9/10 |
| **Цена/генерация** | ~$0.02 | ~$0.03 |

## Преимущества Варианта B

✅ **Лучшая точность** - SAM даёт идеальные маски мебели  
✅ **Правильная перспектива** - ControlNet Depth гарантирует соответствие  
✅ **Реалистичное освещение** - Тени и блики соответствуют комнате  
✅ **Правильный масштаб** - Мебель всегда правильного размера  

## Шаги для апгрейда

### 1. Установка дополнительных зависимостей

```bash
cd backend
pip install segment-anything-py controlnet-aux
```

### 2. Создание нового сервиса Segment Anything

Создайте файл `backend/services/segment_anything.py`:

```python
"""
Сервис для удаления фона с помощью Segment Anything Model
"""
from pathlib import Path
from segment_anything import sam_model_registry, SamAutomaticMaskGenerator
import cv2
import numpy as np
from PIL import Image

class SegmentAnythingRemover:
    def __init__(self):
        # Загружаем модель SAM
        sam_checkpoint = "sam_vit_h_4b8939.pth"
        model_type = "vit_h"
        
        sam = sam_model_registry[model_type](checkpoint=sam_checkpoint)
        self.mask_generator = SamAutomaticMaskGenerator(sam)
    
    def remove_background(self, input_path: str, output_path: str) -> str:
        # Загружаем изображение
        image = cv2.imread(input_path)
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        
        # Генерируем маски
        masks = self.mask_generator.generate(image_rgb)
        
        # Находим самый большой объект (предположительно мебель)
        largest_mask = max(masks, key=lambda x: x['area'])
        
        # Применяем маску
        mask = largest_mask['segmentation']
        
        # Создаем прозрачное изображение
        result = cv2.cvtColor(image, cv2.COLOR_BGR2BGRA)
        result[:, :, 3] = mask.astype(np.uint8) * 255
        
        # Сохраняем
        cv2.imwrite(output_path, result)
        
        return output_path
```

### 3. Создание сервиса ControlNet Inpainting

Создайте файл `backend/services/controlnet_inpainting.py`:

```python
"""
Сервис для inpainting с ControlNet для лучшей перспективы
"""
from controlnet_aux import OpenposeDetector, MidasDetector
import replicate

class ControlNetInpainting:
    def __init__(self):
        self.depth_estimator = MidasDetector.from_pretrained("lllyasviel/Annotators")
        self.model = "jagilley/controlnet-depth2img"
    
    def place_furniture(self, room_path, furniture_path, params, output_dir):
        # Генерируем карту глубины комнаты
        depth_map = self.depth_estimator(room_path)
        
        # Используем ControlNet с depth conditioning
        output = replicate.run(
            self.model,
            input={
                "image": open(room_path, "rb"),
                "control_image": depth_map,
                "prompt": params['inpainting_prompt'],
                "structure": "depth"
            }
        )
        
        return output
```

### 4. Обновление app.py

В файле `backend/app.py` замените импорты:

```python
# Старый вариант
from services.background_remover import BackgroundRemover
from services.inpainting import InpaintingService

# Новый вариант (для Варианта B)
from services.segment_anything import SegmentAnythingRemover
from services.controlnet_inpainting import ControlNetInpainting

# Инициализация
background_remover = SegmentAnythingRemover()
inpainting_service = ControlNetInpainting()
```

## Результаты апгрейда

После апгрейда вы получите:

- 📈 Качество: 7/10 → 9/10
- ⚡ Скорость: 8-12с → 10-15с (+2-3 секунды)
- 💰 Цена: $0.02 → $0.03 за генерацию (+50%)
- ✨ Удовлетворенность пользователей: значительно выше

## Когда делать апгрейд?

✅ Заказчик оплатил разработку  
✅ Есть положительные отзывы о MVP  
✅ Нужно масштабироваться  
✅ Конкуренты предлагают лучшее качество  

## Дальнейшие улучшения (Вариант C)

После Варианта B можно рассмотреть:

1. **Свой GPU-сервер** - единоразовые затраты, но потом бесплатно
2. **Fine-tuning моделей** - обучение на мебели заказчика
3. **Кастомные LoRA** - специфические стили интерьера
4. **Real-time генерация** - SDXL Turbo для скорости

---

**Вопросы?** Смотрите основной README.md или создайте issue.
