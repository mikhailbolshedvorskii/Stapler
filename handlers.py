import json
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# Импорты твоих модулей
from database import save_analysis_to_db  # Твоя функция записи в Firestore
from ai_parser import analyze_document      # Твоя функция вызова Gemini

router = Router()

# 1. Определяем состояния для процесса анализа
class AnalysisStates(StatesGroup):
    confirming_save = State()  # Ожидание нажатия кнопки "Сохранить"

@router.message(F.document | F.photo)
async def handle_medical_file(message: types.Message, state: FSMContext):
    """
    Шаг 1: Получаем файл, анализируем через ИИ, но НЕ сохраняем в БД.
    Вместо этого кладем данные в кэш состояния (FSM).
    """
    status_msg = await message.answer("🔍 <b>Анализирую документ...</b>\nЭто займет около 10-15 секунд.", parse_mode="HTML")
    
    try:
        # Здесь логика получения файла и вызова твоего ai_parser
        # Предположим, analyze_document возвращает готовый словарь (dict)
        analysis_results = await analyze_document(message)
        
        if not analysis_results or "parameters" not in analysis_results:
            await status_msg.edit_text("❌ Не удалось распознать данные. Пожалуйста, убедитесь, что фото четкое.")
            return

        # 2. СОХРАНЯЕМ ВО ВРЕМЕННЫЙ КЭШ
        # Данные будут жить, пока пользователь не нажмет кнопку или не сбросит состояние
        await state.update_data(temp_analysis=analysis_results)
        await state.set_state(AnalysisStates.confirming_save)

        # 3. ФОРМИРУЕМ КРАСИВОЕ ПРЕВЬЮ
        preview_text = (
            f"✅ <b>Анализ готов!</b>\n\n"
            f"📋 <b>Тип:</b> {analysis_results.get('title', 'Не определен')}\n"
            f"🏢 <b>Лаборатория:</b> {analysis_results.get('laboratory', 'н/д')}\n\n"
            f"<b>Найденные показатели:</b>\n"
        )
        
        # Берем первые 5 показателей для превью, чтобы сообщение не было слишком длинным
        for p in analysis_results.get('parameters', [])[:7]:
            icon = "🟢" if p.get('status') == 'normal' else "🔴"
            preview_text += f"{icon} {p['name']}: {p['value']} {p.get('unit', '')}\n"
        
        if len(analysis_results.get('parameters', [])) > 7:
            preview_text += f"<i>...и еще {len(analysis_results['parameters']) - 7} показателей</i>\n"

        preview_text += "\n<b>Сохранить этот результат в вашу медкарту?</b>"

        # 4. КНОПКИ
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 Сохранить в профиль", callback_data="save_to_db"),
                InlineKeyboardButton(text="🗑 Отмена", callback_data="discard_analysis")
            ]
        ])

        await status_msg.delete()
        await message.answer(preview_text, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logging.error(f"Ошибка в handle_medical_file: {e}")
        await status_msg.edit_text("💥 Произошла ошибка при обработке файла. Попробуйте позже.")

@router.callback_query(F.data == "save_to_db", AnalysisStates.confirming_save)
async def process_confirm_save(callback: CallbackQuery, state: FSMContext):
    """
    Шаг 2: Пользователь нажал "Сохранить". Переносим данные из кэша в Firestore.
    """
    # Достаем данные из FSM
    user_data = await state.get_data()
    analysis_data = user_data.get("temp_analysis")

    if not analysis_data:
        await callback.answer("⚠️ Ошибка: данные не найдены. Загрузите файл заново.", show_alert=True)
        await state.clear()
        return

    # Вызываем реальную функцию записи в БД
    success = await save_analysis_to_db(callback.from_user.id, analysis_data)

    if success:
        await callback.message.edit_text(
            f"✅ <b>Успешно сохранено!</b>\n\nДанные добавлены в вашу историю. "
            f"Теперь вы можете увидеть их в разделе /history.",
            parse_mode="HTML"
        )
    else:
        await callback.answer("❌ Ошибка при записи в базу данных.", show_alert=True)

    # Обязательно очищаем состояние
    await state.clear()

@router.callback_query(F.data == "discard_analysis", AnalysisStates.confirming_save)
async def process_discard_save(callback: CallbackQuery, state: FSMContext):
    """
    Шаг 2 (альтернатива): Пользователь нажал "Отмена".
    """
    await state.clear()
    await callback.message.edit_text("🗑 Результат анализа удален из временной памяти. В базу ничего не записано.")
    await callback.answer("Удалено")