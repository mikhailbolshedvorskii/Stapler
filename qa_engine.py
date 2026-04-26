import logging
from google import genai
from google.genai import types
from config import config

logger = logging.getLogger(__name__)
client = genai.Client(api_key=config.GEMINI_API_KEY)

# Обновили имя на Stapler
QA_SYSTEM_PROMPT = (
    "Ты — Stapler, интеллектуальный медицинский ассистент. "
    "Тебе предоставлены медицинские данные пользователя из его базы данных. "
    "Твои правила:\n"
    "1. Если вопрос касается медицины и в данных ЕСТЬ ответ — ответь четко и профессионально.\n"
    "2. Если вопрос медицинский, но в предоставленных данных НЕТ этой информации — вежливо ответь: "
    "'Дорогой пользователь, в вашей базе Stapler пока нет данных для ответа на этот вопрос. Пожалуйста, уточните запрос или загрузите новый анализ'.\n"
    "3. Если вопрос НЕ касается медицины (просто беседа) — поддерживай диалог как дружелюбный ИИ, "
    "но отвечай кратко (строго не более 6 предложений).\n"
    "4. Всегда напоминай, что ты — ИИ, а не врач."
)

async def ask_medical_ai(user_question: str, medical_history: list):
    """
    Обрабатывает запрос пользователя с учетом его истории анализов.
    """
    try:
        # Формируем контекст из истории
        if medical_history:
            context = "Медицинские данные пользователя из базы Stapler:\n"
            for doc in medical_history:
                context += f"- Документ: {doc.get('title')} от {doc.get('date')}\n"
                # Проверка на наличие индикаторов (берем indicators или parameters)
                indicators = doc.get('indicators') or doc.get('parameters') or []
                for ind in indicators:
                    context += f"  * {ind.get('name')}: {ind.get('value')} {ind.get('unit')} (Статус: {ind.get('status')})\n"
        else:
            context = "В базе данных Stapler пока нет сохраненных анализов пользователя."

        prompt = f"{context}\n\nВопрос пользователя: {user_question}"

        # Используем gemini-2.0-flash-exp (как в твоем коде)
        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=QA_SYSTEM_PROMPT,
                temperature=0.3
            )
        )

        return response.text

    except Exception as e:
        logger.error(f"Ошибка в QA Engine: {e}")
        return "Извините, Stapler столкнулся с технической ошибкой при обработке вашего вопроса. Пожалуйста, попробуйте позже."