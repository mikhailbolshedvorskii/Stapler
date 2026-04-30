import os
import logging
from datetime import datetime
from exporter import create_medical_report
from aiogram import Router, F, types, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    CallbackQuery, 
    Message,
    BufferedInputFile
)

# Импорты модулей проекта
from database import save_analysis_to_db, get_recent_analyses
from ai_parser import analyze_document
from qa_engine import ask_medical_ai 
from charts import generate_trend_chart 

logger = logging.getLogger(__name__)
router = Router()

class AnalysisStates(StatesGroup):
    confirming_save = State()

# --- БЛОК 1: КОМАНДЫ ---

@router.message(Command("start")) # команда бота - start
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Привет! Я Stapler.</b>\n\n"
        "Я твой медицинский ассистент. Вот что я умею:\n\n"
        "📥 <b>Загрузка:</b> Пришли фото или PDF результата анализа.\n"
        "📊 <b>Аналитика:</b> Используй команду /analysis для вывода трендов.\n"
        "💬 <b>Чат:</b> Просто задай вопрос по своим данным.",
        parse_mode="HTML"
    )

@router.message(Command("history")) # команда бота - history
async def cmd_history(message: Message):
    history = await get_recent_analyses(message.from_user.id, limit=10)
    if not history:
        await message.answer("Ваша база данных пока пуста.")
        return
    
    text = "📅 <b>Последние анализы:</b>\n\n"
    for a in history:
        text += f"• {a.get('date')} — {a.get('title')}\n"
    
    await message.answer(text, parse_mode="HTML")

@router.message(Command("analysis")) # команда бота - analysis
async def cmd_analysis(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗓 Месяц", callback_data="period_30"),
            InlineKeyboardButton(text="🗓 3 Месяца", callback_data="period_90")
        ],
        [
            InlineKeyboardButton(text="🗓 Полгода", callback_data="period_180"),
            InlineKeyboardButton(text="🗓 Год", callback_data="period_365")
        ],
        [
            InlineKeyboardButton(text="📈 Вся история", callback_data="period_3650")
        ]
    ])
    await message.answer("📊 <b>Анализ динамики</b>\n\nЗа какой период проанализировать показатели?", reply_markup=keyboard, parse_mode="HTML")

@router.message(Command("export")) # команда бота - export
async def cmd_export(message: Message):
    status_msg = await message.answer("📋 <b>Stapler формирует ваш медицинский отчет...</b>", parse_mode="HTML")
    
    user_id = message.from_user.id
    # 1. Получаем историю (до 100 последних записей для полноты картины)
    history = await get_recent_analyses(user_id, limit=100)
    
    if not history:
        await status_msg.edit_text("❌ В вашей базе пока нет данных для экспорта.")
        return

    try:
        # 2. Собираем графики для отчета по ключевым маркерам
        charts_for_pdf = []
        target_markers = ["Гемоглобин", "Глюкоза", "Холестерин", "Железо", "C3", "C4"]
        
        for marker in target_markers:
            chart = generate_trend_chart(history, marker)
            if chart:
                charts_for_pdf.append(chart)

        # 3. Генерируем PDF через наш новый модуль
        user_name = message.from_user.full_name or "Пациент Stapler"
        pdf_buffer = create_medical_report(user_name, history, charts_for_pdf)
        
        # 4. Отправляем готовый файл
        file_name = f"Stapler_Report_{datetime.now().strftime('%Y%m%d')}.pdf"
        document = BufferedInputFile(pdf_buffer.read(), filename=file_name)
        
        await message.answer_document(
            document=document,
            caption="✅ <b>Ваш медицинский отчет готов!</b>\n\nВ нем собраны все ваши анализы и графики динамики показателей.",
            parse_mode="HTML"
        )
        await status_msg.delete()

    except Exception as e:
        logger.error(f"Ошибка при экспорте PDF: {e}")
        await status_msg.edit_text("💥 Произошла ошибка при генерации PDF-отчета.")

# --- БЛОК 2: ОБРАБОТКА КНОПОК ПЕРИОДА (АНАЛИТИКА + ГРАФИКИ) ---

@router.callback_query(F.data.startswith("period_"))
async def process_period_analysis(callback: CallbackQuery):
    days = int(callback.data.split("_")[1]) # Исправлен сплит
    user_id = callback.from_user.id
    
    await callback.message.edit_text(f"⌛ <b>Собираю данные за {days} дн. и анализирую...</b>", parse_mode="HTML")
    history = await get_recent_analyses(user_id, limit=50, days=days)
    
    if not history:
        await callback.message.edit_text("❌ Данные за этот период не найдены.")
        return

    query = f"Проведи глубокий анализ моих данных за последние {days} дней. Какие тренды ты видишь?"
    try:
        answer = await ask_medical_ai(query, history)
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="back_to_analysis")]
        ])
        await callback.message.edit_text(answer, parse_mode="Markdown", reply_markup=keyboard)

        # Популярные маркеры для отрисовки графиков
        target_markers = ["Гемоглобин", "Глюкоза", "Холестерин", "C3", "C4", "Железо", "Ферритин", "АКТГ", "Кортизол"]
        for marker in target_markers:
            chart_file = generate_trend_chart(history, marker)
            if chart_file:
                await callback.message.answer_photo(
                    photo=chart_file,
                    caption=f"📈 Динамика показателя: <b>{marker}</b>",
                    parse_mode="HTML"
                )
    except Exception as e:
        logger.error(f"Ошибка аналитики: {e}")
        await callback.message.edit_text("💥 Ошибка при формировании отчета.")

@router.callback_query(F.data == "back_to_analysis")
async def back_to_analysis(callback: CallbackQuery):
    await cmd_analysis(callback.message)

# --- БЛОК 3: ЗАГРУЗКА И КАРТОЧКА АНАЛИЗА ---

@router.message(F.document | F.photo)
async def handle_medical_file(message: Message, state: FSMContext, bot: Bot):
    # Добавляем reply_to_message_id прямо здесь
    status_msg = await message.answer(
        "🔍 <b>Stapler изучает документ...</b>", 
        parse_mode="HTML",
        reply_to_message_id=message.message_id # Это сделает статус "ответом" на файл
    )
    
    file_path = None
    try:
        # 1. Извлекаем ID и уникальный ID файла
        if message.document:
            file_id = message.document.file_id
            file_unique_id = message.document.file_unique_id
            ext = message.document.file_name.split('.')[-1] if '.' in message.document.file_name else "pdf"
        else:
            file_id = message.photo[-1].file_id
            file_unique_id = message.photo[-1].file_unique_id
            ext = "jpg"

        # 2. Скачивание файла
        os.makedirs("temp", exist_ok=True)
        file_path = f"temp/{file_id}.{ext}"
        
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, destination=file_path)

        # 3. Анализ через ИИ
        analysis_results = await analyze_document(file_path)
        
        if not analysis_results or "indicators" not in analysis_results:
            await status_msg.edit_text("❌ Не удалось распознать данные. Проверьте четкость фото.")
            return

        # 4. Сохраняем данные в состояние FSM
        await state.update_data(temp_analysis=analysis_results, file_unique_id=file_unique_id)
        await state.set_state(AnalysisStates.confirming_save)

        # 6. Формируем "богатую" карточку
        preview = (
            f"📋 <b>{analysis_results.get('title', 'Анализ')}</b>\n"
            f"📅 <b>Дата:</b> {analysis_results.get('date', 'не указана')}\n"
            f"🏥 <b>{analysis_results.get('laboratory', 'Лаборатория н/д')}</b>\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        )
        
        for ind in analysis_results.get('indicators', []):
            status_ico = "✅" if ind.get('status') == 'normal' else "⚠️"
            norm_text = f" (<i>Норма: {ind.get('norm')}</i>)" if ind.get('norm') else ""
            preview += f"{status_ico} {ind['name']}: {ind['value']} {ind.get('unit', '')}{norm_text}\n"

        preview += (
            f"\n🤖 <b>Комментарий Google Gemini:</b>\n"
            f"<i>{analysis_results.get('summary', 'Описание отсутствует')}</i>\n\n"
            f"💾 <b>Данные готовы к сохранению в ваш личный профиль.</b>\n"
            f"❗ <b>Не является диагнозом. Обратитесь к врачу.</b>"
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 Сохранить в Stapler", callback_data="save_to_db"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data="discard_analysis")
            ]
        ])

        # 7. Заменяем текст ожидания на результат (edit_text вместо delete)
        await status_msg.edit_text(preview, reply_markup=keyboard, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Ошибка в handle_medical_file: {e}")
        try:
            await status_msg.edit_text("💥 Ошибка при чтении файла. Попробуйте еще раз.")
        except:
            await message.answer("💥 Ошибка при чтении файла.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

@router.callback_query(F.data == "save_to_db", AnalysisStates.confirming_save)
async def process_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    success = await save_analysis_to_db(callback.from_user.id, data.get("temp_analysis"), data.get("file_unique_id"))
    
    if success == "duplicate":
        await callback.answer("⚠️ Этот анализ уже сохранен!", show_alert=True)
    elif success:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.answer("✅ Сохранено")
        text = (
            "💾 <b>Данные сохранены в ваш личный профиль.</b>\n"
            "❗ <b>Не является диагнозом. Обратитесь к врачу.</b>"
        )
        await callback.message.answer(text, parse_mode="HTML")
    else:
        await callback.answer("❌ Ошибка при сохранении", show_alert=True)
    await state.clear()

@router.callback_query(F.data == "discard_analysis", AnalysisStates.confirming_save)
async def process_discard(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🗑 Результат анализа удален из чата.")

# --- БЛОК 4: СВОБОДНЫЙ ЧАТ ---

@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_query(message: Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    history = await get_recent_analyses(message.from_user.id, limit=10)
    
    if not history:
        await message.answer("Сначала загрузи анализ, чтобы мне было на что опираться.")
        return

    answer = await ask_medical_ai(message.text, history)
    await message.answer(answer, parse_mode="Markdown")