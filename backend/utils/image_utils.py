"""
Утилиты для работы с изображениями
"""
import base64
import io
import uuid
from pathlib import Path
from typing import Tuple, Optional, List
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


def create_furniture_collage(
    image_paths: List[str],
    output_path: str,
    max_height: int = 512,
    padding: int = 40
) -> str:
    """
    Склеивает несколько изображений мебели в одно (в ряд слева направо).
    Нужно для одного вызова Nano Banana: все предметы в одном изображении = одна генерация.
    
    Args:
        image_paths: Пути к изображениям мебели (порядок = слева направо в коллаже)
        output_path: Куда сохранить коллаж (PNG)
        max_height: Максимальная высота каждого элемента (пропорции сохраняются)
        padding: Отступ между элементами и по краям
        
    Returns:
        output_path
    """
    if not image_paths:
        raise ValueError("Нужен хотя бы один путь к изображению")
    
    images = []
    for path in image_paths:
        img = Image.open(path)
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        w, h = img.size
        if h > max_height:
            new_h = max_height
            new_w = int(w * max_height / h)
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        images.append(img)
    
    total_w = sum(im.size[0] for im in images) + padding * (len(images) + 1)
    max_h = max(im.size[1] for im in images) + padding * 2
    collage = Image.new("RGBA", (total_w, max_h), (255, 255, 255, 255))
    
    x = padding
    for im in images:
        y = (max_h - im.size[1]) // 2
        collage.paste(im, (x, y), im if im.mode == "RGBA" else None)
        x += im.size[0] + padding
    
    collage.convert("RGB").save(output_path, "PNG")
    return output_path


def limit_image_size(image_path: str, max_long_side: int = 1200) -> str:
    """
    Уменьшает изображение, если длинная сторона больше max_long_side.
    Сохраняет пропорции. Перезаписывает файл.
    """
    try:
        img = Image.open(image_path)
        w, h = img.size
        if w <= max_long_side and h <= max_long_side:
            return image_path
        if w >= h:
            new_w = max_long_side
            new_h = int(h * max_long_side / w)
        else:
            new_h = max_long_side
            new_w = int(w * max_long_side / h)
        img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
        img.save(image_path, 'PNG')
        print(f"📐 Результат уменьшен до {new_w}x{new_h}")
    except Exception as e:
        print(f"⚠️  Ошибка уменьшения: {e}")
    return image_path


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


def add_white_background_to_png(image_path: str) -> str:
    """
    Убирает прозрачность: подкладывает белый фон и сохраняет как RGB.
    Так в каталоге не будет «шахматки» ни в браузере, ни в IDE.
    """
    try:
        img = Image.open(image_path).convert('RGBA')
        alpha = img.split()[3]
        extrema = alpha.getextrema()
        if extrema[0] < 255:
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=alpha)
            img = background
        else:
            img = img.convert('RGB')
        # Всегда сохраняем как RGB (без альфа) — тогда ни IDE, ни браузер не покажут шахматку
        img.save(image_path, 'PNG')
        print(f"✅ Сохранён как RGB (без прозрачности): {Path(image_path).name}")
    except Exception as e:
        print(f"⚠️  Ошибка: {e}")
    return image_path


def ensure_rgb_png(image_path: str) -> bytes:
    """
    Открывает изображение и возвращает байты PNG с белым фоном (без прозрачности).
    Используется для отдачи картинок каталога через API — всегда без «шахматки».
    """
    img = Image.open(image_path).convert('RGBA')
    alpha = img.split()[3]
    extrema = alpha.getextrema()
    if extrema[0] < 255:
        background = Image.new('RGB', img.size, (255, 255, 255))
        background.paste(img, mask=alpha)
        img = background
    else:
        img = img.convert('RGB')
    buf = io.BytesIO()
    img.save(buf, 'PNG')
    return buf.getvalue()
