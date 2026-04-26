import logging
from google import genai
from google.genai import types
from config import config
import json

logger = logging.getLogger(__name__)
client = genai.Client(api_key=config.GEMINI_API_KEY)

QA_SYSTEM_PROMPT = (
    "Ты — Stapler Health AI, интеллектуальный медицинский ассистент. "
    "Тебе предоставлены медицинские данные пользователя из его базы данных. "
    "Твои правила:\n"
    "1. Если вопрос касается медицины и в данных ЕСТЬ ответ — ответь четко и профессионально.\n"
    "2. Если вопрос медицинский, но в предоставленных данных НЕТ этой информации — вежливо ответь: "
    "'Дорогой пользователь, ваш вопрос не имеет отношения к тем данным, которые мы сохранили в базе, уточни, пожалуйста, вопрос'.\n"
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
            context = "Медицинские данные пользователя:\n"
            for doc in medical_history:
                context += f"- Документ: {doc.get('title')} от {doc.get('date')}\n"
                for ind in doc.get('indicators', []):
                    context += f"  * {ind.get('name')}: {ind.get('value')} {ind.get('unit')} (Статус: {ind.get('status')})\n"
        else:
            context = "В базе данных пока нет сохраненных анализов пользователя."

        prompt = f"{context}\n\nВопрос пользователя: {user_question}"

        response = await client.aio.models.generate_content(
            model="gemini-2.0-flash-exp", # Используем последнюю стабильную модель
            contents=[prompt],
            config=types.GenerateContentConfig(
                system_instruction=QA_SYSTEM_PROMPT,
                temperature=0.3 # Низкая температура для точности
            )
        )

        return response.text

    except Exception as e:
        logger.error(f"Ошибка в QA Engine: {e}")
        return "Извините, произошла техническая ошибка при обработке вопроса."