import logging
import base64
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from ai_parser import analyze_document, analyze_history
from database import save_medical_analysis, get_recent_analyses

logger = logging.getLogger(__name__)
pending_analyses = {}

async def run_bot(bot: AsyncTeleBot):
    
    await bot.set_my_commands([
        types.BotCommand("start", "🏠 Главное меню"),
        types.BotCommand("history", "📜 Мой архив"),
        types.BotCommand("help", "❓ Справка")
    ])

    @bot.message_handler(commands=['start'])
    async def send_welcome(message):
        welcome_text = "👋 *Я Stapler — твой ИИ-архив здоровья.*\n\nПришли фото или PDF-файл анализов!"
        await bot.reply_to(message, welcome_text, parse_mode='Markdown')

    @bot.message_handler(content_types=['document', 'photo'])
    async def handle_medical_file(message):
        user_id = message.from_user.id
        status_msg = await bot.reply_to(message, "⏳ *ИИ расшифровывает документ...*", parse_mode='Markdown')

        try:
            if message.content_type == 'photo':
                file_id = message.photo[-1].file_id
                mime = "image/jpeg"
            else:
                file_id = message.document.file_id
                mime = message.document.mime_type or "application/pdf"

            file_info = await bot.get_file(file_id)
            downloaded = await bot.download_file(file_info.file_path)
            base64_data = base64.b64encode(downloaded).decode('utf-8')

            # Анализ через Gemini
            result = await analyze_document(base64_data, mime)
            
            if "error" in result:
                await bot.edit_message_text(f"❌ Ошибка ИИ: {result['error']}", message.chat.id, status_msg.message_id)
                return

            # Сохраняем во временное хранилище
            pending_analyses[user_id] = result

            # Формируем красивый текст (с защитой от None)
            title = result.get('title') or "Анализ"
            date = result.get('date') or "Дата не определена"
            summary = result.get('summary') or "Описание отсутствует."
            
            params_text = ""
            for p in result.get('parameters', [])[:5]:
                name = p.get('name', 'Показатель')
                val = p.get('value', '?')
                status_emoji = "🟢" if p.get('status') == 'normal' else "🔴"
                params_text += f"{status_emoji} {name}: `{val}`\n"

            response_text = (
                f"✅ *{title}*\n"
                f"📅 Дата: `{date}`\n\n"
                f"{params_text}\n"
                f"💬 *Разбор:* {summary[:200]}..."
            )

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 Сохранить в архив", callback_data="save_analysis"))

            await bot.edit_message_text(response_text, message.chat.id, status_msg.message_id, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"Processing error: {e}")
            await bot.edit_message_text("❌ Не удалось прочитать файл.", message.chat.id, status_msg.message_id)

    @bot.callback_query_handler(func=lambda call: True)
    async def callback_listener(call):
        user_id = call.from_user.id
        if call.data == "save_analysis":
            data = pending_analyses.get(user_id)
            if not data:
                await bot.answer_callback_query(call.id, "Данные не найдены")
                return

            await bot.answer_callback_query(call.id, "💾 Сохранение...")
            res = await save_medical_analysis(str(user_id), data)
            
            if res == "duplicate":
                await bot.send_message(call.message.chat.id, "⚠️ Этот анализ уже есть в вашей базе.")
            elif res:
                await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                await bot.send_message(call.message.chat.id, "✅ Успешно сохранено!")
            
            pending_analyses.pop(user_id, None)

    @bot.message_handler(func=lambda message: True)
    async def handle_text(message):
        # Логика ответов на вопросы по истории (как в вашем коде)
        user_id = message.from_user.id
        history = await get_recent_analyses(str(user_id), limit=10)
        if history:
            ans = await analyze_history(history, message.text)
            await bot.reply_to(message, ans, parse_mode='Markdown')
        else:
            await bot.reply_to(message, "Загрузите сначала анализы.")