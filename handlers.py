import os
import logging
import asyncio
from telebot import types
from ai_parser import analyze_document
from database import save_analysis_to_db, get_recent_analyses
from formatters import format_analysis_card
from config import config

# Настройка логирования
logger = logging.getLogger(__name__)

async def run_bot(bot):
    """
    Регистрация всех обработчиков сообщений.
    """

    @bot.message_handler(commands=['start'])
    async def send_welcome(message):
        welcome_text = (
            "👋 Привет! Я **Stapler** — твой интеллектуальный архив анализов.\n\n"
            "📸 Просто пришли мне фото или PDF с результатами исследований, "
            "и я расшифрую их, сохраню в базу и покажу динамику.\n\n"
            "Используй /history, чтобы увидеть свои прошлые записи."
        )
        await bot.reply_to(message, welcome_text, parse_mode='Markdown')

    @bot.message_handler(commands=['history'])
    async def show_history(message):
        user_id = str(message.from_user.id)
        await bot.send_chat_action(message.chat.id, 'typing')
        
        try:
            history = await get_recent_analyses(user_id, limit=5)
            if not history:
                await bot.reply_to(message, "Ваш архив пока пуст. Загрузите первый анализ!")
                return

            response = "📂 **Последние анализы из вашего архива:**\n\n"
            for item in history:
                response += f"🔹 {item.get('date', '??')} — {item.get('title', 'Анализ')}\n"
            
            response += "\n_Чтобы получить подробности, просто загрузите новый файл._"
            await bot.reply_to(message, response, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Ошибка при получении истории: {e}")
            await bot.reply_to(message, "❌ Не удалось загрузить историю.")

    @bot.message_handler(content_types=['photo', 'document'])
    async def handle_docs(message):
        """
        Обработка входящих файлов (фотографий или PDF).
        """
        user_id = str(message.from_user.id)
        file_id = None
        file_ext = ""

        # Определяем тип файла
        if message.content_type == 'photo':
            file_id = message.photo[-1].file_id
            file_ext = ".jpg"
        elif message.content_type == 'document':
            if message.document.mime_type in ['image/jpeg', 'image/png', 'application/pdf']:
                file_id = message.document.file_id
                file_ext = os.path.splitext(message.document.file_name)[1]
            else:
                await bot.reply_to(message, "❌ Я принимаю только фото (JPG/PNG) или PDF документы.")
                return

        # Индикация работы
        processing_msg = await bot.reply_to(message, "🔍 **Начинаю анализ...** Это может занять до 30 секунд.", parse_mode='Markdown')
        await bot.send_chat_action(message.chat.id, 'upload_document')

        temp_path = f"temp_{user_id}{file_ext}"

        try:
            # 1. Скачивание файла
            file_info = await bot.get_file(file_id)
            downloaded_file = await bot.download_file(file_info.file_path)
            
            with open(temp_path, 'wb') as new_file:
                new_file.write(downloaded_file)

            # 2. Анализ через Gemini AI
            # Передаем путь к файлу в наш парсер
            analysis_result = await analyze_document(temp_path)

            if not analysis_result:
                await bot.edit_message_text(
                    "❌ Не удалось распознать данные. Убедитесь, что фото четкое.",
                    chat_id=message.chat.id,
                    message_id=processing_msg.message_id
                )
                return

            # 3. Сохранение в Firebase
            # Добавляем user_id в данные перед сохранением
            doc_id = await save_analysis_to_db(user_id, analysis_result)
            
            # 4. Форматирование ответа
            final_text = format_analysis_card(analysis_result)

            # 5. Отправка результата
            await bot.edit_message_text(
                final_text,
                chat_id=message.chat.id,
                message_id=processing_msg.message_id,
                parse_mode='Markdown'
            )

        except Exception as e:
            logger.error(f"Критическая ошибка при обработке: {e}")
            await bot.edit_message_text(
                "⚠️ Произошла техническая ошибка. Попробуйте позже.",
                chat_id=message.chat.id,
                message_id=processing_msg.message_id
            )
        finally:
            # Удаление временного файла
            if os.path.exists(temp_path):
                os.remove(temp_path)

    @bot.message_handler(commands=['help'])
    async def send_help(message):
        help_text = (
            "❓ **Как пользоваться Stapler?**\n\n"
            "1. Отправьте фото бумажного анализа или PDF файл.\n"
            "2. Подождите около 20 секунд, пока ИИ изучит данные.\n"
            "3. Получите структурированный отчет и сохранение в архив.\n\n"
            "💡 **Совет:** Для лучшего распознавания делайте фото при хорошем освещении и без теней."
        )
        await bot.reply_to(message, help_text, parse_mode='Markdown')

    logger.info("✅ Обработчики успешно зарегистрированы.")