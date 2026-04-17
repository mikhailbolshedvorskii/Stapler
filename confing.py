import os
from dotenv import load_dotenv

# Загружаем .env только если он есть (для локальной разработки)
# На VPS Google мы будем задавать эти переменные через окружение (Environment Variables)
load_dotenv()

class Config:
    """
    Класс для управления конфигурацией бота.
    При миграции на Google VPS все эти значения будут браться из системы.
    """
    
    # Telegram Bot Token от BotFather
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
    
    # Ключ API для Google Gemini (AI)
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    
    # Настройки базы данных (MongoDB или PostgreSQL)
    # На Google Cloud лучше использовать Cloud SQL или Atlas
    DATABASE_URL = os.getenv("DATABASE_URL", "mongodb://localhost:27017/stapler_db")
    
    # Уровень логирования
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

    @classmethod
    def validate(cls):
        """Проверка наличия критических настроек перед запуском"""
        missing = []
        if not cls.TELEGRAM_TOKEN: missing.append("TELEGRAM_TOKEN")
        if not cls.GEMINI_API_KEY: missing.append("GEMINI_API_KEY")
        
        if missing:
            raise EnvironmentError(f"Ошибка: Не найдены переменные окружения: {', '.join(missing)}")

# Инициализация объекта настроек
config = Config()