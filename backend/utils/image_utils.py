"""
Утилиты для работы с изображениями
"""
import base64
import io
import uuid
from pathlib import Path
from typing import Tuple, Optional
from PIL import Image
import requests


def save_uploaded_image(image_data: bytes, upload_dir: Path) -> str:
    """
    Сохраняет загруженное изображение
    
    Args:
        image_data: Байты изображения
        upload_dir: Директория для сохранения
        
    Returns:
        Путь к сохраненному файлу
    """
    # Создаем уникальное имя файла
    filename = f"{uuid.uuid4()}.png"
    filepath = upload_dir / filename
    
    # Открываем и конвертируем в PNG
    image = Image.open(io.BytesIO(image_data))
    
    # Конвертируем RGBA в RGB если нужно
    if image.mode == 'RGBA':
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[3])
        image = background
    elif image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Сохраняем
    image.save(filepath, 'PNG')
    
    return str(filepath)


def image_to_base64(image_path: str) -> str:
    """
    Конвертирует изображение в base64 для API
    
    Args:
        image_path: Путь к изображению
        
    Returns:
        Base64 строка
    """
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def image_to_data_url(image_path: str) -> str:
    """
    Конвертирует изображение в data URL для OpenAI API
    
    Args:
        image_path: Путь к изображению
        
    Returns:
        Data URL строка
    """
    base64_image = image_to_base64(image_path)
    return f"data:image/png;base64,{base64_image}"


def resize_image(image_path: str, max_size: Tuple[int, int] = (1024, 1024)) -> str:
    """
    Изменяет размер изображения если оно слишком большое
    
    Args:
        image_path: Путь к изображению
        max_size: Максимальный размер (ширина, высота)
        
    Returns:
        Путь к измененному изображению (может быть тот же)
    """
    image = Image.open(image_path)
    
    # Проверяем нужно ли изменять размер
    if image.width <= max_size[0] and image.height <= max_size[1]:
        return image_path
    
    # Изменяем размер с сохранением пропорций
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Сохраняем поверх оригинала
    image.save(image_path, 'PNG')
    
    return image_path


def download_image(url: str, save_path: Path) -> str:
    """
    Скачивает изображение по URL
    
    Args:
        url: URL изображения
        save_path: Путь для сохранения
        
    Returns:
        Путь к сохраненному файлу
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # Создаем уникальное имя
    filename = f"{uuid.uuid4()}.png"
    filepath = save_path / filename
    
    # Открываем и сохраняем
    image = Image.open(io.BytesIO(response.content))
    image.save(filepath, 'PNG')
    
    return str(filepath)


def create_mask_from_bbox(
    image_size: Tuple[int, int],
    bbox: Tuple[int, int, int, int]
) -> Image.Image:
    """
    Создает маску для inpainting из bounding box
    
    Args:
        image_size: Размер изображения (width, height)
        bbox: Координаты (x, y, width, height)
        
    Returns:
        PIL Image маска (черно-белое изображение)
    """
    # Создаем черное изображение
    mask = Image.new('L', image_size, 0)
    
    # Рисуем белый прямоугольник в области маски
    from PIL import ImageDraw
    draw = ImageDraw.Draw(mask)
    
    x, y, width, height = bbox
    draw.rectangle(
        [(x, y), (x + width, y + height)],
        fill=255
    )
    
    return mask


def blend_images(
    background_path: str,
    foreground_path: str,
    position: Tuple[int, int],
    scale: float = 1.0
) -> Image.Image:
    """
    Накладывает одно изображение на другое
    
    Args:
        background_path: Путь к фоновому изображению
        foreground_path: Путь к накладываемому изображению
        position: Позиция (x, y)
        scale: Масштаб foreground изображения
        
    Returns:
        Результирующее изображение
    """
    background = Image.open(background_path)
    foreground = Image.open(foreground_path)
    
    # Масштабируем foreground
    if scale != 1.0:
        new_size = (
            int(foreground.width * scale),
            int(foreground.height * scale)
        )
        foreground = foreground.resize(new_size, Image.Resampling.LANCZOS)
    
    # Создаем копию фона
    result = background.copy()
    
    # Накладываем foreground
    if foreground.mode == 'RGBA':
        result.paste(foreground, position, foreground)
    else:
        result.paste(foreground, position)
    
    return result
