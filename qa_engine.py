import logging
from google import genai
from google.genai import types
from config import config

logger = logging.getLogger(__name__)
client = genai.Client(api_key=config.GEMINI_API_KEY)

# Используем ту же модель, что и в парсере
MODEL_ID = "gemini-3.1-flash-lite-preview"

QA_SYSTEM_PROMPT = (
    "Ты — Stapler, интеллектуальный медицинский ассистент. "
    "Тебе предоставлены медицинские данные пользователя из его базы данных. "
    "Твои правила:\n"
    "1. Если вопрос касается медицины и в данных ЕСТЬ ответ — ответь четко и профессионально.\n"
    "2. Если вопрос медицинский, но в данных НЕТ информации — вежливо попроси уточнить запрос.\n"
    "3. Если вопрос не про медицину — будь дружелюбным, но кратким.\n"
    "4. Всегда напоминай, что ты — ИИ, а не врач."
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