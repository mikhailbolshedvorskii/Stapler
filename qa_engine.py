import logging
from google import genai
from google.genai import types
from config import config

logger = logging.getLogger(__name__)
client = genai.Client(api_key=config.GEMINI_API_KEY)

# Используем ту же модель, что и в парсере
MODEL_ID = "gemini-3.1-flash-lite-preview"

QA_SYSTEM_PROMPT = (
    "Ты — Stapler, профессиональный медицинский ассистент. "
    "Твоя задача — анализировать данные и отвечать СТРОГО по шаблону.\n\n"
    
    "ЦВЕТОВАЯ ИНДИКАЦИЯ (ОБЯЗАТЕЛЬНО):\n"
    "Перед каждым пунктом в разделе 'Анализ данных' ставь соответствующий эмодзи-кружок:\n"
    "🟢 — если ВСЕ показатели в этой группе в норме.\n"
    "🟡 — если есть хотя бы одно незначительное отклонение от нормы.\n"
    "🔴 — если есть серьезные отклонения или критические маркеры.\n\n"
    
    "СТРУКТУРА ОТВЕТА:\n"
    "1. ПРИВЕТСТВИЕ И ДИСКЛЕЙМЕР (как раньше).\n\n"
    "2. ПЕРИОД (как раньше).\n\n"
    "3. БЛОК АНАЛИЗА:\n"
    "📋 **Анализ данных:**\n\n"
    "🟢 1. [Название категории]: [Текст анализа].\n\n"
    "🟡 2. [Название категории]: [Текст анализа].\n\n"
    "(Важно: двойной отступ между пунктами).\n\n"
    "4. БЛОК ТРЕНДОВ:\n"
    "📈 **Тренды и выводы:** (как раньше).\n\n"
    "5. ЗАКЛЮЧЕНИЕ (как раньше).\n\n"
    
    "ПРАВИЛА:\n"
    "- Никогда не используй #.\n"
    "- Сохраняй цветовую логику: зеленый — норма, желтый — внимание, красный — тревога."
)

async def ask_medical_ai(user_question: str, medical_history: list):
    try:
        if medical_history:
            context = "Медицинские данные пользователя из базы Stapler:\n"
            for doc in medical_history:
                context += f"- Документ: {doc.get('title')} от {doc.get('date')}\n"
                indicators = doc.get('indicators') or doc.get('parameters') or []
                for ind in indicators:
                    context += f"  * {ind.get('name')}: {ind.get('value')} {ind.get('unit')} (Статус: {ind.get('status')})\n"
        else:
            context = "В базе данных Stapler пока нет сохраненных анализов."

        prompt = f"{context}\n\nВопрос пользователя: {user_question}"

        # Теперь вызываем 3.1 Flash Lite
        response = await client.aio.models.generate_content(
            model=MODEL_ID,
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=QA_SYSTEM_PROMPT,
                temperature=0.3
            )
        )

        return response.text

    except Exception as e:
        logger.error(f"Ошибка в QA Engine (3.1 Lite): {e}")
        return "Извините, Stapler столкнулся с технической ошибкой при обращении к модели."