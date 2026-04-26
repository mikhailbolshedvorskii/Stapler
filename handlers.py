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

# Project imports
from database import save_analysis_to_db, get_recent_analyses
from ai_parser import analyze_document
from qa_engine import ask_medical_ai 
from charts import generate_trend_chart  # NEW IMPORT

logger = logging.getLogger(__name__)
router = Router()

class AnalysisStates(StatesGroup):
    confirming_save = State()

# --- BLOCK 1: COMMANDS ---

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 <b>Hello! I am Stapler.</b>\n\n"
        "I am your medical assistant. Here is what I can do:\n\n"
        "📥 <b>Upload:</b> Send a photo or PDF of your lab results.\n"
        "📊 <b>Analytics:</b> Use /analysis to see trends over time.\n"
        "💬 <b>Chat:</b> Ask me questions about your health data.",
        parse_mode="HTML"
    )

@router.message(Command("history"))
async def cmd_history(message: Message):
    history = await get_recent_analyses(message.from_user.id, limit=10)
    if not history:
        await message.answer("Your history is currently empty.")
        return
    
    text = "📅 <b>Your upload history:</b>\n\n"
    for item in history:
        text += f"• {item.get('date')} — <b>{item.get('title')}</b>\n"
    
    await message.answer(text, parse_mode="HTML")

@router.message(Command("analysis"))
async def cmd_analysis(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🗓 Month", callback_data="period_30"),
            InlineKeyboardButton(text="🗓 3 Months", callback_data="period_90")
        ],
        [
            InlineKeyboardButton(text="🗓 6 Months", callback_data="period_180"),
            InlineKeyboardButton(text="🗓 Year", callback_data="period_365")
        ],
        [
            InlineKeyboardButton(text="📈 All Time", callback_data="period_3650")
        ]
    ])
    
    await message.answer(
        "📊 <b>Trend Analysis</b>\n\nFor which period should Stapler analyze your health markers?",
        reply_markup=keyboard,
        parse_mode="HTML"
    )

# --- BLOCK 2: CALLBACK HANDLERS ---

@router.callback_query(F.data.startswith("period_"))
async def process_period_analysis(callback: CallbackQuery):
    days = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    
    await callback.message.edit_text(f"⌛ <b>Gathering data for {days} days and analyzing...</b>", parse_mode="HTML")
    
    # 1. Fetch data from DB
    history = await get_recent_analyses(user_id, limit=50, days=days)
    
    if not history:
        await callback.message.edit_text("❌ No data found for this period.")
        return

    # 2. Get AI Analysis
    query = f"Analyze my medical trends for the last {days} days."
    try:
        answer = await ask_medical_ai(query, history)
        
        # Navigation keyboard
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Back to menu", callback_data="back_to_analysis")]
        ])
        
        # Edit current message with text analysis
        await callback.message.edit_text(answer, parse_mode="Markdown", reply_markup=keyboard)

        # 3. GENERATE CHARTS (PRO LOGIC)
        # We check common markers. If data exists, we send a photo
        target_markers = ["Гемоглобин", "Глюкоза", "Холестерин", "C3", "C4"]
        
        for marker in target_markers:
            chart_file = generate_trend_chart(history, marker)
            if chart_file:
                await callback.message.answer_photo(
                    photo=chart_file,
                    caption=f"📈 Visual trend for: <b>{marker}</b>",
                    parse_mode="HTML"
                )

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        await callback.message.edit_text("💥 An error occurred during analysis.")

@router.callback_query(F.data == "back_to_analysis")
async def back_to_analysis(callback: CallbackQuery):
    await cmd_analysis(callback.message)

# --- BLOCK 3: FILE HANDLING ---

@router.message(F.document | F.photo)
async def handle_medical_file(message: Message, state: FSMContext, bot: Bot):
    status_msg = await message.answer("🔍 <b>Stapler is studying the document...</b>", parse_mode="HTML")
    
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
            await status_msg.edit_text("❌ Could not recognize data. Please ensure the photo is clear.")
            return

        await state.update_data(temp_analysis=analysis_results)
        await state.set_state(AnalysisStates.confirming_save)

        preview = (
            f"✅ <b>Document processed!</b>\n\n"
            f"📋 <b>Type:</b> {analysis_results.get('title')}\n\n"
            f"<b>Top Markers:</b>\n"
        )
        
        for ind in analysis_results.get('indicators', [])[:5]:
            status_ico = "🟢" if ind.get('status') == 'normal' else "🔴"
            preview += f"{status_ico} {ind['name']}: {ind['value']} {ind.get('unit', '')}\n"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 Save to Stapler", callback_data="save_to_db"),
                InlineKeyboardButton(text="🗑 Delete", callback_data="discard_analysis")
            ]
        ])

        await status_msg.delete()
        await message.answer(preview, reply_markup=keyboard, parse_mode="HTML")

    except Exception as e:
        logger.error(f"File error: {e}")
        await status_msg.edit_text("💥 Error reading file.")
    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)

@router.callback_query(F.data == "save_to_db", AnalysisStates.confirming_save)
async def process_save(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    success = await save_analysis_to_db(callback.from_user.id, data.get("temp_analysis"))
    if success:
        await callback.message.edit_text("✅ <b>Data saved to your Stapler health record!</b>")
    await state.clear()

@router.callback_query(F.data == "discard_analysis", AnalysisStates.confirming_save)
async def process_discard(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🗑 Analysis deleted.")

# --- BLOCK 4: CHAT ---

@router.message(F.text & ~F.text.startswith("/"))
async def handle_user_query(message: Message):
    await message.bot.send_chat_action(chat_id=message.chat.id, action="typing")
    history = await get_recent_analyses(message.from_user.id, limit=10)
    
    if not history:
        await message.answer("Please upload an analysis first so I have data to discuss.")
        return

    answer = await ask_medical_ai(message.text, history)
    await message.answer(answer, parse_mode="Markdown")