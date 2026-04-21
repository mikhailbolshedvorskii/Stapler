from google import genai
from google.genai import types
import json
import os
import logging
from config import config

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация клиента Gemini (требует pip install google-genai)
client = genai.Client(api_key=config.GEMINI_API_KEY)

async def analyze_document(file_path):
    """
    Анализ медицинского документа с использованием gemini-3.1-flash-lite-preview.
    Код оптимизирован: минимум строк за счет использования response_mime_type.
    """
    try:
        # Модель 3.1 Flash Lite идеально подходит для структурирования данных
        MODEL_ID = "gemini-3.1-flash-lite-preview"
        
        # Системные инструкции с экранированием фигурных скобок для Python f-строк
        system_prompt = (
            "Ты — медицинский аналитик Stapler Health. Извлеки данные из анализа. "
            "Верни ТОЛЬКО JSON объект с полями: "
            "{{ "
            "  'title': 'название анализа', "
            "  'date': 'дата ISO', "
            "  'laboratory': 'клиника', "
            "  'indicators': [ "
            "    {{'name': 'параметр', 'value': 'значение', 'unit': 'ед. изм.', 'norm': 'референс', 'status': 'normal/high/low'}} "
            "  ], "
            "  'summary': 'краткий медицинский вывод (1-2 предложения)' "
            "}}"
        )

        # Чтение файла в байтах
        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Определение типа контента
        mime_type = "application/pdf" if file_path.lower().endswith('.pdf') else "image/jpeg"
        
        # Асинхронный запрос к Gemini
        response = await client.models.generate_content_async(
            model=MODEL_ID,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type=mime_type),
                system_prompt
            ],
            config=types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json" # Ключевая настройка для чистого JSON
            )
        )

        # Парсим результат. Благодаря response_mime_type, в response.text нет лишнего текста.
        return json.loads(response.text)

    except Exception as e:
        logger.error(f"Ошибка при анализе документа {file_path}: {e}")
        return None