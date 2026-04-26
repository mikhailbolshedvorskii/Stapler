import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperty
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from handlers import router as main_router
import database

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)

async def main():
    """
    Основная функция запуска бота Stapler Health на aiogram 3.
    """
    logger.info("--- Запуск Stapler Health AI (aiogram) ---")

    # 1. Проверка конфигурации
    try:
        config.validate()
    except Exception as e:
        logger.critical(f"Ошибка конфигурации: {e}")
        return

    # 2. Инициализация БД Firestore
    db = database.initialize_firebase()
    if not db:
        logger.error("Не удалось подключить Firebase. Бот может работать некорректно.")

    # 3. Инициализация бота и диспетчера
    # Используем DefaultBotProperty для указания ParseMode по умолчанию
    bot = Bot(
        token=config.TELEGRAM_TOKEN,
        default=DefaultBotProperty(parse_mode=ParseMode.HTML)
    )
    
    # Хранилище состояний в оперативной памяти (для FSM)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # 4. Регистрация роутеров (хендлеров)
    dp.include_router(main_router)

    # Полезная функция: удаление вебхуков перед запуском поллинга
    await bot.delete_webhook(drop_pending_updates=True)

    # 5. Запуск бота
    try:
        logger.info("🚀 Бот запущен и готов принимать документы!")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка при работе бота: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")