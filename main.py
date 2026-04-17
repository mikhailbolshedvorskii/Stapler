import os
import logging
import asyncio
import dotenv
from telebot.async_telebot import AsyncTeleBot
from telebot import asyncio_helper

# Импортируем конфиг и компоненты
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
    Главная точка входа.
    """
    # 1. Валидация конфига
    try:
        config.validate()
    except EnvironmentError as e:
        logger.critical(e)
        return

    # 2. Настройка прокси для Telegram (если указан в .env)
    if config.PROXY_URL:
        logger.info(f"🌐 Использование прокси для Telegram: {config.PROXY_URL}")
        asyncio_helper.proxy = config.PROXY_URL

    # 3. Инициализация ИИ и БД
    ai_parser.API_KEY = config.GEMINI_API_KEY
    
    db_client = database.initialize_firebase()
    if db_client:
        logger.info("✅ База данных Firestore подключена.")
    else:
        logger.warning("⚠️ Работа без базы данных (проверьте firebase_key.json)")

    # 4. Запуск бота
    logger.info(f"🚀 Запуск бота @{os.getenv('TELEGRAM_BOT_USERNAME', 'bot')}...")
    bot = AsyncTeleBot(config.TELEGRAM_TOKEN)
    
    # Регистрация хендлеров
    await run_bot(bot)
    
    try:
        await bot.polling(non_stop=True, timeout=60)
    except Exception as e:
        logger.error(f"❌ Ошибка Polling: {e}")
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен.")