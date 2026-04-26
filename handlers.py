import os
import logging
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery, 
    Message
)

# Импорты модулей проекта
from database import save_analysis_to_db, get_recent_analyses
from ai_parser import analyze_document
from qa_engine import ask_medical_ai 

logger = logging.getLogger(__name__)
router = Router()

class AnalysisStates(StatesGroup):
    confirming_save = State()

# --- БЛОК 1: КОМАНДЫ ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Здравствуйте! Я Stapler.</b>\n\n"
        "Я помогу вам вести медкарту и анализировать тренды.\n\n"
        "🔹 <b>Загрузка:</b> Пришлите фото или PDF результата анализа.\n"
        "🔹 <b>Чат:</b> Спрашивайте меня о своих данных (например: 'Как изменилось железо за год?').",
        parse_mode="HTML"
    )

@router.message(Command("history"))
async def cmd_history(message: Message):
    history = await get_recent_analyses(message.from_user.id, limit=10)
    if not history:
        await message.answer("У вас пока нет сохраненных анализов.")
        return
    
    text = "📅 <b>Ваша история:</b>\n\n"
    for item in history:
        text += f"• {item.get('date')} — <b>{item.get('title')}</b>\n"
    
    await message.answer(text, parse_mode="HTML")

# --- БЛОК 2: ОБРАБОТКА ФАЙЛОВ ---

@router.message(F.document | F.photo)
async def handle_medical_file(message: Message, state: FSMContext, bot: Bot):
    status_msg = await message.answer("🔍 <b>Анализирую документ...</b>\nЭто займет около 10-15 секунд.", parse_mode="HTML")
    
    file_path = None
    try:
        if message.document:
            file_id = message.document.file_id
            ext = message.document.file_name.split('.')[-1] if '.' in message.document.file_name else "pdf"
        else:
            file_id = message.photo[-1].file_id
            ext = "jpg"

        os.makedirs("temp", exist_ok=True)
        file_path = f"temp/{file_id}.{ext}"
        
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, destination=file_path)

        analysis_results = await analyze_document(file_path)
        
        if not analysis_results or "indicators" not in analysis_results:
            await status_msg.edit_text("❌ Не удалось распознать данные. Попробуйте другое фото.")
            return

        await state.update_data(temp_analysis=analysis_results)
        await state.set_state(AnalysisStates.confirming_save)

        preview = (
            f"✅ <b>Анализ распознан!</b>\n\n"
            f"📋 <b>Тип:</b> {analysis_results.get('title')}\n"
            f"🏢 <b>Лаборатория:</b> {analysis_results.get('laboratory', 'н/д')}\n\n"
            f"<b>Основные показатели:</b>\n"
        )
        
        indicators = analysis_results.get('indicators', [])
        for ind in indicators[:5]:
            status_emoji = "🟢" if ind.get('status') == 'normal' else "🔴"
            preview += f"{status_emoji} {ind['name']}: {ind['value']} {ind.get('unit', '')}\n"
        
        if len(indicators) > 5:
            preview += f"<i>...и еще {len(indicators) - 5} параметров.</i>\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 Сохранить в профиль", callback_data="save_to_db"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data="discard_analysis")
            ]
        ])

        await status_msg.delete()
        await message.answer(preview, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка при обработке файла: {e}")
        await status_msg.edit_text("💥 Произошла ошибка при обработке файла.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

@router.callback_query(F.data == "save_to_db", AnalysisStates.confirming_save)
async def process_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    analysis = data.get("temp_analysis")
    
    success = await save_analysis_to_db(callback.from_user.id, analysis)
    if success:
        await callback.message.edit_text("✅ <b>Данные сохранены в Stapler!</b> Теперь вы можете задавать вопросы по ним.", parse_mode="HTML")
    else:
        await callback.answer("Ошибка при сохранении в базу.", show_alert=True)
    await state.clear()

@router.callback_query(F.data == "discard_analysis", AnalysisStates.confirming_save)
async def process_discard(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🗑 Данные удалены.")

# --- БЛОК 3: ЧАТ С ИСТОРИЕЙ ---

@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_query(message: Message):
    user_id = message.from_user.id
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    history = await get_recent_analyses(user_id, limit=10)
    
    if not history:
        await message.answer("Чтобы я мог отвечать на вопросы, сначала загрузите свои анализы (фото или PDF).")
        return

    try:
        answer = await ask_medical_ai(message.text, history)
        await message.answer(answer, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Ошибка QA: {e}")
        await message.answer("Простите, я не смог проанализировать ваши данные сейчас. Попробуйте позже.")