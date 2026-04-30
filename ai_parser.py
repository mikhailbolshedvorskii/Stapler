import json
import logging
from google import genai
from google.genai import types
from config import config

logger = logging.getLogger(__name__)

# Инициализация клиента
client = genai.Client(api_key=config.GEMINI_API_KEY)

# Модель проекта
MODEL_ID = "gemini-3.1-flash-lite-preview"

async def analyze_document(file_path: str):
    """
    Извлечение данных из документа.
    """
    try:
        # Изменено имя на Stapler
        system_prompt = (
    "Ты — медицинский аналитик Stapler. Твоя задача: извлечь данные из анализа. "
    "ВАЖНО: Если документ — это текстовое заключение (Рентген, УЗИ, МРТ), "
    "создай в списке 'indicators' один объект, где 'name' будет 'Заключение', "
    "а в 'value' перенеси краткую суть исследования. "
    "Весь текст пиши СТРОГО на РУССКОМ языке."
)

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        mime_type = "application/pdf" if file_path.lower().endswith('.pdf') else "image/jpeg"
        
        generation_config = types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
            response_schema={
                "type": "OBJECT",
                "properties": {
                    "title": {"type": "STRING"},
                    "date": {"type": "STRING"},
                    "laboratory": {"type": "STRING"},
                    "indicators": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "name": {"type": "STRING"},
                                "value": {"type": "STRING"},
                                "unit": {"type": "STRING"},
                                "norm": {"type": "STRING"},
                                "status": {"type": "STRING", "enum": ["normal", "high", "low"]}
                            },
                            "required": ["name", "value", "status"]
                        }
                    },
                    "summary": {"type": "STRING"}
                },
                "required": ["title", "indicators", "summary"]
            }
        )

        response = await client.aio.models.generate_content(
            model=MODEL_ID,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                system_prompt
            ],
            config=generation_config
        )

        return json.loads(response.text)

    except Exception as e:
        logger.error(f"Ошибка Gemini 3.1 Lite при анализе {file_path}: {e}")
        return None

async def chat_with_data(user_query: str, history_context: str):
    """
    Ответы на вопросы на основе истории (RAG).
    """
    try:
        # Используем современный способ передачи роли через config
        response = await client.aio.models.generate_content(
            model=MODEL_ID,
            contents=f"Данные пациента:\n{history_context}\n\nВопрос: {user_query}",
            config=types.GenerateContentConfig(
                system_instruction="Ты — Stapler, профессиональный медицинский ассистент. Отвечай кратко и только по делу.",
                temperature=0.3
            )
        )

        return response.text
    except Exception as e:
        logger.error(f"Ошибка чата Gemini: {e}")
        return "Извините, не удалось проанализировать историю ваших анализов."