import os
import logging
import asyncio
from telebot.async_telebot import AsyncTeleBot

# Импортируем конфигурацию и модули системы
from config import config
from handlers import run_bot
import ai_parser 
import database

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def main():
    """
    Главная точка входа в приложение Stapler.
    """
    # 1. Валидация конфигурации
    try:
        config.validate()
    except EnvironmentError as e:
        logger.critical(f"Ошибка конфигурации: {e}")
        return

    # 2. Инициализация ИИ (API ключи и настройки)
    ai_parser.API_KEY = config.GEMINI_API_KEY
    
    # 3. Подключение к базе данных Firestore
    # Прокси для Firebase настраивается через системные переменные или Admin SDK,
    # поэтому здесь мы просто инициализируем клиент.
    db_client = database.initialize_firebase()
    if db_client:
        logger.info("✅ База данных Firestore подключена.")
    else:
        logger.warning("⚠️ Работа без базы данных (проверьте файл firebase_key.json)")

    # 4. Инициализация бота
    # ВАЖНО: Мы НЕ используем asyncio_helper.proxy здесь, так как Telegram 
    # должен работать напрямую без прокси, чтобы избежать ServerDisconnectedError.
    bot = AsyncTeleBot(config.TELEGRAM_TOKEN)

    # Установка команд бота в меню
    try:
        from telebot.types import BotCommand
        await bot.set_my_commands([
            BotCommand("start", "Запустить бота"),
            BotCommand("history", "Показать историю анализов"),
            BotCommand("help", "Инструкция по использованию")
        ])
        logger.info("✅ Команды меню установлены.")
    except Exception as e:
        logger.error(f"⚠️ Не удалось установить команды меню: {e}")

    logger.info("🚀 Запуск бота Stapler...")
    
    # Регистрация хендлеров (обработчиков сообщений) из handlers.py
    await run_bot(bot)
    
    try:
        # Запуск бесконечного цикла получения обновлений (polling)
        # timeout и request_timeout увеличены для стабильности на слабых каналах
        await bot.polling(non_stop=True, timeout=90, request_timeout=150)
    except Exception as e:
        logger.error(f"❌ Ошибка во время работы Polling: {e}")
        # Короткая пауза перед перезапуском при сбое сети
        await asyncio.sleep(5) 

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем (KeyboardInterrupt).")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка при запуске: {e}")