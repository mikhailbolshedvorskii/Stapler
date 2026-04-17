import logging
import base64
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from ai_parser import analyze_document, analyze_history
from database import save_medical_analysis, get_recent_analyses

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Временное хранилище для результатов анализа перед сохранением
pending_analyses = {}

async def run_bot(bot: AsyncTeleBot):
    
    # 1. Установка меню команд (синяя кнопка в углу)
    await bot.set_my_commands([
        types.BotCommand("start", "🏠 Главное меню"),
        types.BotCommand("history", "📜 Мой архив анализов"),
        types.BotCommand("help", "❓ Как пользоваться")
    ])

    @bot.message_handler(commands=['start'])
    async def send_welcome(message):
        welcome_text = (
            "👋 *Привет! Я Stapler — твой личный ИИ-архив здоровья.*\n\n"
            "Пришли мне файл с анализами (фото или PDF), чтобы я его расшифровал, "
            "или задай любой вопрос по своим прошлым записям.\n\n"
            "📸 *Просто отправь фото документа, чтобы начать!*"
        )
        
        # Инлайновые кнопки для приветственного сообщения
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("📜 Посмотреть историю", callback_data="back_to_history"),
            types.InlineKeyboardButton("💬 Задать вопрос ИИ", callback_data="view_help")
        )
        
        await bot.reply_to(message, welcome_text, parse_mode='Markdown', reply_markup=markup)

    @bot.message_handler(commands=['history'])
    async def show_history(message):
        user_id = message.from_user.id
        status_msg = await bot.reply_to(message, "📂 *Загружаю ваш архив...*", parse_mode='Markdown')
        
        try:
            history = await get_recent_analyses(str(user_id), limit=6)
            
            if not history:
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("🏠 В меню", callback_data="back_to_menu"))
                await bot.edit_message_text(
                    "📭 *Ваш архив пока пуст.*\n\nЗагрузите свой первый документ, и я его запомню!", 
                    message.chat.id, status_msg.message_id, parse_mode='Markdown', reply_markup=markup
                )
                return

            markup = types.InlineKeyboardMarkup()
            response_text = "📜 *Ваши последние анализы:*\n\nВыберите один для деталей или просто задайте вопрос в чате."
            
            for item in history: 
                date = item.get('date', '??.??.????')
                title = item.get('title', 'Анализ')
                btn_text = f"📅 {date} | {title}"
                markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"view_{item['id']}"))

            markup.add(types.InlineKeyboardButton("📊 Анализировать тренды", callback_data="analyze_all_history"))

            await bot.edit_message_text(response_text, message.chat.id, status_msg.message_id, parse_mode='Markdown', reply_markup=markup)
            
        except Exception as e:
            logger.error(f"Error in history: {e}")
            await bot.edit_message_text("❌ Ошибка доступа к базе данных.", message.chat.id, status_msg.message_id)

    @bot.callback_query_handler(func=lambda call: True)
    async def callback_listener(call):
        user_id = call.from_user.id
        
        if call.data == "view_help":
            help_text = (
                "💬 *Я понимаю вопросы на обычном языке:*\n\n"
                "Попробуйте написать:\n"
                "• _'Какой у меня был ферритин в прошлом году?'_\n"
                "• _'Покажи самый высокий результат сахара'_\n"
                "• _'Есть ли показатели выше нормы?'_\n\n"
                "Я проанализирую все ваши сохраненные документы, чтобы найти ответ."
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("⬅️ Назад", callback_data="back_to_history"))
            await bot.edit_message_text(help_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

        elif call.data == "save_analysis":
            data = pending_analyses.get(user_id)
            if not data:
                await bot.answer_callback_query(call.id, "❌ Данные устарели")
                return

            await bot.answer_callback_query(call.id, "💾 Сохраняю...")
            result = await save_medical_analysis(str(user_id), data)
            
            if result == "duplicate":
                await bot.answer_callback_query(call.id, "⚠️ Уже есть в базе", show_alert=True)
            elif result:
                await bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
                await bot.send_message(call.message.chat.id, "✅ *Сохранено! Теперь вы можете задавать вопросы по этому анализу.*", parse_mode='Markdown')
            else:
                await bot.answer_callback_query(call.id, "❌ Ошибка базы данных")
            
            pending_analyses.pop(user_id, None)

        elif call.data.startswith("view_"):
            analysis_id = call.data.replace("view_", "")
            history = await get_recent_analyses(str(user_id), limit=15)
            target = next((item for item in history if str(item['id']) == analysis_id), None)
            
            if target:
                params_text = ""
                # Ограничиваем список параметров для читаемости
                for p in target.get('parameters', [])[:10]: 
                    status_emoji = "🟢" if p.get('status') == 'normal' else ("🔴" if p.get('status') == 'high' else "🔵")
                    params_text += f"{status_emoji} *{p['name']}*: {p['value']} {p.get('unit','')} \n"
                
                detail_text = (
                    f"📋 *{target.get('title')}*\n"
                    f"📅 Дата: `{target.get('date')}`\n\n"
                    f"{params_text}\n"
                    f"💡 *Заключение:* {target.get('summary')}\n\n"
                    f"👇 *Задайте любой вопрос по этой записи в чате!*"
                )
                
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton("⬅️ Назад к истории", callback_data="back_to_history"))
                await bot.edit_message_text(detail_text, call.message.chat.id, call.message.message_id, parse_mode='Markdown', reply_markup=markup)

        elif call.data == "back_to_history":
            await show_history(call.message)
            
        elif call.data == "back_to_menu":
            await send_welcome(call.message)

    @bot.message_handler(content_types=['document', 'photo'])
    async def handle_medical_file(message):
        user_id = message.from_user.id
        status_msg = await bot.reply_to(message, "⏳ *Читаю документ...*", parse_mode='Markdown')

        try:
            if message.content_type == 'photo':
                file_id = message.photo[-1].file_id
                mime = "image/jpeg"
            else:
                file_id = message.document.file_id
                mime = message.document.mime_type

            file_info = await bot.get_file(file_id)
            downloaded = await bot.download_file(file_info.file_path)
            base64_data = base64.b64encode(downloaded).decode('utf-8')

            result = await analyze_document(base64_data, mime)
            if "error" in result:
                await bot.edit_message_text(f"❌ {result['error']}", message.chat.id, status_msg.message_id)
                return

            pending_analyses[user_id] = result

            params_text = ""
            for p in result.get('parameters', [])[:5]:
                status_emoji = "🟢" if p.get('status') == 'normal' else ("🔴" if p.get('status') == 'high' else "🔵")
                params_text += f"{status_emoji} {p['name']}: `{p['value']}`\n"

            response_text = (
                f"✅ *{result.get('title')} обработан*\n"
                f"📅 Дата: `{result.get('date')}`\n\n"
                f"{params_text}\n"
                f"💬 *ИИ-разбор:* {result.get('summary', '')[:150]}..."
            )

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("📥 Сохранить и запомнить", callback_data="save_analysis"))

            await bot.edit_message_text(response_text, message.chat.id, status_msg.message_id, parse_mode='Markdown', reply_markup=markup)

        except Exception as e:
            logger.error(f"File processing error: {e}")
            await bot.edit_message_text("❌ Ошибка при чтении. Попробуйте другой файл.", message.chat.id, status_msg.message_id)

    @bot.message_handler(func=lambda message: True)
    async def handle_text(message):
        user_id = message.from_user.id
        history = await get_recent_analyses(str(user_id), limit=15)
        
        if not history:
            await bot.reply_to(message, "💬 Я еще не видел ваших анализов! Пожалуйста, загрузите фото документа.")
            return

        status_msg = await bot.reply_to(message, "🧠 *Анализирую историю...*", parse_mode='Markdown')
        ai_response = await analyze_history(history, user_query=message.text)
        await bot.edit_message_text(ai_response, message.chat.id, status_msg.message_id, parse_mode='Markdown')