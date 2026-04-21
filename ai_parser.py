import json
import logging
from google import genai
from google.genai import types
from config import config

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация клиента Gemini через новый SDK google-genai
client = genai.Client(api_key=config.GEMINI_API_KEY)

async def analyze_document(file_path: str):
    """
    Анализ медицинского документа с использованием Gemini 3.1 Flash-Lite.
    Используется формат JSON через response_mime_type для исключения ошибок парсинга.
    """
    try:
        # Прямое указание новейшей модели согласно правилам проекта
        MODEL_ID = "gemini-3.1-flash-lite-preview"
        
        system_prompt = (
            "Ты — медицинский аналитик Stapler Health. Твоя задача: извлечь данные из предоставленного анализа. "
            "Если параметр качественный (например, ВИЧ), используй 'Negative'/'Positive' для value и norm. "
            "Всегда возвращай данные строго в формате JSON."
        )

        # Чтение файла
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        mime_type = "application/pdf" if file_path.lower().endswith('.pdf') else "image/jpeg"
        
        # Настройка конфигурации генерации с принудительным JSON
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

        # Вызов API
        response = await client.models.generate_content_async(
            model=MODEL_ID,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                system_prompt
            ],
            config=generation_config
        )

        # Благодаря response_mime_type, ответ приходит в виде чистого JSON
        result_json = json.loads(response.text)
        
        logger.info(f"Документ успешно проанализирован: {result_json.get('title')}")
        return result_json

    except Exception as e:
        logger.error(f"Критическая ошибка Gemini SDK (3.1 Lite) при анализе {file_path}: {e}")
        return None