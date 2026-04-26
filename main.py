import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
# Исправлено: DefaultBotProperties (во множественном числе)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from handlers import router as main_router
import database

# Настройка логирования на уровне всего приложения
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
        logger.info("✅ Конфигурация валидна.")
    except Exception as e:
        logger.critical(f"Ошибка конфигурации: {e}")
        return

    # 2. Инициализация БД Firestore
    try:
        db = database.initialize_firebase()
        if db:
            logger.info("✅ Firebase успешно инициализирован.")
        else:
            logger.warning("⚠️ Firebase инициализирован с пустым результатом. Проверьте подключение.")
    except Exception as e:
        logger.error(f"Критическая ошибка при подключении Firebase: {e}")

    # 3. Инициализация бота и диспетчера
    # Исправлено имя класса: DefaultBotProperties
    bot = Bot(
        token=config.TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    # Хранилище состояний в оперативной памяти (для FSM)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    # 4. Регистрация роутеров (хендлеров)
    dp.include_router(main_router)

    # Удаление обновлений, пришедших пока бот был выключен
    await bot.delete_webhook(drop_pending_updates=True)

    # 5. Запуск бота
    try:
        logger.info("🚀 Бот запущен и готов к работе!")
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Критическая ошибка во время работы: {e}")
    finally:
        # Корректное закрытие сессии
        await bot.session.close()
        logger.info("Сессия бота закрыта.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен пользователем.")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при запуске: {e}")