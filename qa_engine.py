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
    "Твоя задача — анализировать данные из базы пользователя и отвечать строго по следующему шаблону:\n\n"
    
    "1. ПРИВЕТСТВИЕ И ДИСКЛЕЙМЕР:\n"
    "Начинай строго со слов: 'Здравствуйте! Я — Stapler, ваш интеллектуальный медицинский ассистент. "
    "Напоминаю, что я являюсь искусственным интеллектом, а не врачом. Мои ответы носят информационный характер "
    "и не заменяют очную консультацию специалиста.'\n\n"
    
    "2. ПЕРИОД:\n"
    "Укажи период анализа (с самой ранней до самой поздней даты в данных).\n\n"
    
    "3. БЛОК АНАЛИЗА:\n"
    "Используй заголовок: '📋 **Анализ данных:**'\n"
    "После заголовка сделай пустую строку (отступ).\n"
    "Перечисляй пункты (1, 2, 3...). Между пунктами ОБЯЗАТЕЛЬНО делай пустую строку-отступ для читаемости.\n\n"
    
    "4. БЛОК ТРЕНДОВ:\n"
    "Используй заголовок: '📈 **Тренды и выводы:**'\n"
    "После заголовка сделай пустую строку (отступ).\n"
    "Опиши тренды и повод для беспокойства. Между абзацами внутри блока делай пустые строки.\n\n"
    
    "5. ЗАКЛЮЧЕНИЕ:\n"
    "Добавь важные примечания и рекомендацию обратиться к врачу.\n\n"
    
    "ПРАВИЛА ОФОРМЛЕНИЯ:\n"
    "- НИКАКИХ решеток (#) в заголовках. Используй только жирный текст и эмодзи.\n"
    "- Всегда делай двойной перенос строки между логическими блоками.\n"
    "- Если данных нет — вежливо попроси загрузить их."
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