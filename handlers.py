import logging
from telebot.async_telebot import AsyncTeleBot
from telebot import types
from database import get_recent_analyses

logger = logging.getLogger(__name__)

async def run_bot(bot: AsyncTeleBot):
    
    @bot.message_handler(commands=['start'])
    async def welcome(message):
        welcome_text = (
            "🚀 *Stapler Health AI приветствует тебя!*\n\n"
            "Я помогу оцифровать твои анализы и сохранить их в облако.\n"
            "Просто пришли мне фото или PDF документа."
        )
        await bot.reply_to(message, welcome_text, parse_mode='Markdown')

    @bot.message_handler(commands=['history'])
    async def show_history(message):
        user_id = str(message.from_user.id)
        await bot.send_chat_action(message.chat.id, 'typing')
        
        history = await get_recent_analyses(user_id, limit=5)
        
        if not history:
            await bot.reply_to(message, "📜 Твоя история пока пуста. Загрузи первый анализ!")
            return

        response = "📋 *Твои последние анализы:*\n\n"
        for i, item in enumerate(history, 1):
            date = item.get('date', '??.??.????')
            title = item.get('title', 'Анализ')
            
            response += f"{i}. 🗓 *{date}* — {title}\n"
            
            params = item.get('parameters', [])
            if params:
                # Теперь корректно отображаем и числа, и строки (отрицательно/положительно)
                rows = []
                for p in params[:3]:
                    val = p.get('value', 'н/д')
                    name = p.get('name', '')
                    status_icon = "🟢" if p.get('status') == "normal" else "🔴"
                    rows.append(f"   {status_icon} {name}: {val}")
                
                response += "\n".join(rows) + "\n"
            response += "\n"

        await bot.reply_to(message, response, parse_mode='Markdown')