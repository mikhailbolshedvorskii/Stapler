import json
import logging
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message

# Твои существующие импорты
from database import save_analysis_to_db, get_recent_analyses
from ai_parser import analyze_document
# Импорт нового движка QA (который мы создадим в qa_engine.py)
from qa_engine import ask_medical_ai 

logger = logging.getLogger(__name__)
router = Router()

class AnalysisStates(StatesGroup):
    confirming_save = State()  # Ожидание нажатия кнопки "Сохранить"

# --- БЛОК 1: КОМАНДЫ ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Привет! Я Stapler Health AI.</b>\n\n"
        "Я помогаю оцифровывать анализы и отвечать на вопросы по ним.\n\n"
        "🔹 <b>Загрузка:</b> Пришлите фото или PDF анализа.\n"
        "🔹 <b>Вопросы:</b> Спрашивайте меня о ваших данных (например: 'Какой у меня гемоглобин?').",
        parse_mode="HTML"
    )

@router.message(Command("history"))
async def cmd_history(message: Message):
    analyses = await get_recent_analyses(message.from_user.id)
    if not analyses:
        await message.answer("Ваша база данных пока пуста.")
        return
    
    text = "📅 <b>Последние анализы:</b>\n\n"
    for a in analyses:
        text += f"• {a.get('date')} — {a.get('title')}\n"
    
    await message.answer(text, parse_mode="HTML")

# --- БЛОК 2: ОБРАБОТКА ФАЙЛОВ (ТВОЙ ТЕКУЩИЙ КОД) ---

@router.message(F.document | F.photo)
async def handle_medical_file(message: types.Message, state: FSMContext):
    """Шаг 1: Анализ файла через ИИ."""
    status_msg = await message.answer("🔍 <b>Анализирую документ...</b>\nЭто займет около 10-15 секунд.", parse_mode="HTML")
    
    try:
        # Здесь мы передаем путь к файлу (если ai_parser его скачивает)
        # В твоем случае ai_parser.py принимает объект message и сам качает файл
        analysis_results = await analyze_document(message)
        
        if not analysis_results or "indicators" not in analysis_results:
            await status_msg.edit_text("❌ Не удалось распознать данные. Убедитесь, что фото четкое.")
            return

        await state.update_data(temp_analysis=analysis_results)
        await state.set_state(AnalysisStates.confirming_save)

        preview_text = (
            f"✅ <b>Анализ готов!</b>\n\n"
            f"📋 <b>Тип:</b> {analysis_results.get('title', 'Не определен')}\n"
            f"🏢 <b>Лаборатория:</b> {analysis_results.get('laboratory', 'н/д')}\n\n"
            f"<b>Найденные показатели:</b>\n"
        )
        
        # Используем indicators (так как в ai_parser.py у тебя именно это имя поля)
        indicators = analysis_results.get('indicators', [])
        for p in indicators[:7]:
            icon = "🟢" if p.get('status') == 'normal' else "🔴"
            preview_text += f"{icon} {p['name']}: {p['value']} {p.get('unit', '')}\n"
        
        if len(indicators) > 7:
            preview_text += f"<i>...и еще {len(indicators) - 7} показателей</i>\n"

        preview_text += "\n<b>Сохранить результат в медкарту?</b>"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 Сохранить в профиль", callback_data="save_to_db"),
                InlineKeyboardButton(text="🗑 Отмена", callback_data="discard_analysis")
            ]
        ])

        await status_msg.delete()
        await message.answer(preview_text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Ошибка в handle_medical_file: {e}")
        await status_msg.edit_text("💥 Ошибка при обработке файла.")

@router.callback_query(F.data == "save_to_db", AnalysisStates.confirming_save)
async def process_confirm_save(callback: CallbackQuery, state: FSMContext):
    """Шаг 2: Подтверждение сохранения."""
    user_data = await state.get_data()
    analysis_data = user_data.get("temp_analysis")

    if not analysis_data:
        await callback.answer("⚠️ Данные не найдены.", show_alert=True)
        await state.clear()
        return

    success = await save_analysis_to_db(callback.from_user.id, analysis_data)

    if success:
        await callback.message.edit_text(
            "✅ <b>Успешно сохранено!</b>\n\nДанные добавлены в вашу историю.",
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Ошибка при записи в БД.", show_alert=True)

    await state.clear()

@router.callback_query(F.data == "discard_analysis", AnalysisStates.confirming_save)
async def process_discard_save(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🗑 Результат анализа удален.")
    await callback.answer("Удалено")

# --- БЛОК 3: НОВЫЙ ФУНКЦИОНАЛ (ВОПРОСЫ ПО БАЗЕ) ---

@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_query(message: Message):
    """
    Обработка текстовых вопросов пользователя.
    Вызывается, если сообщение не является командой.
    """
    user_id = message.from_user.id
    
    # 1. Показываем статус "печатает"
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")

    # 2. Достаем историю из Firestore для контекста ИИ
    # Загружаем последние 5-10 документов, чтобы ИИ знал последние данные
    history = await get_recent_analyses(user_id, limit=5)

    # 3. Отправляем в Gemini (через qa_engine)
    answer = await ask_medical_ai(message.text, history)

    # 4. Отправляем ответ
    await message.answer(answer)