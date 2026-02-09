"""
Утилита для загрузки переменных окружения из .env файла
"""
import os
from pathlib import Path
from dotenv import load_dotenv


def load_environment():
    """
    Загружает переменные окружения из .env файла
    Ищет .env в корне проекта
    """
    # Определяем корень проекта (на уровень выше backend/)
    current_dir = Path(__file__).resolve().parent
    backend_dir = current_dir.parent
    project_root = backend_dir.parent
    env_path = project_root / '.env'
    
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Переменные окружения загружены из: {env_path}")
        return True
    else:
        print(f"⚠️  Файл .env не найден по пути: {env_path}")
        print(f"📝 Создайте файл .env на основе .env.example")
        return False


def get_env_variable(key: str, default: str = None) -> str:
    """
    Получает переменную окружения с проверкой
    
    Args:
        key: Название переменной
        default: Значение по умолчанию
        
    Returns:
        Значение переменной окружения
    """
    value = os.getenv(key, default)
    
    if value is None:
        raise ValueError(f"❌ Переменная окружения {key} не установлена!")
    
    return value


def get_env_optional(key: str) -> str:
    """Возвращает переменную окружения или пустую строку."""
    return os.getenv(key, "") or ""


# Загружаем при импорте модуля
load_environment()
