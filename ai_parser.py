import google.generativeai as genai
import json
import os
import logging
from config import config

# Настройка логирования
logger = logging.getLogger(__name__)

# Инициализация Gemini
genai.configure(api_key=config.GEMINI_API_KEY)

async def analyze_document(file_path):
    """
    Отправляет файл в Gemini AI для извлечения медицинских данных.
    """
    try:
        # Настройка модели
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')
        
        # Системный промпт для структурирования данных
        system_prompt = (
            "Ты — профессиональный медицинский ассистент. Твоя задача: извлечь данные из лабораторного анализа. "
            "Верни ответ ТОЛЬКО в формате JSON со следующей структурой: "
            "{"
            "  'title': 'название анализа',"
            "  'date': 'дата',"
            "  'laboratory': 'название клиники',"
            "  'indicators': ["
            "    {'name': 'название параметра', 'value': 'значение', 'unit': 'ед. изм.', 'norm': 'референс', 'status': 'normal/high/low/warning'}"
            "  ],"
            "  'summary': 'краткое пояснение человеческим языком (макс 2 предложения)'"
            "}"
            "Если параметр выше нормы, ставь status: high, если ниже — low. Если в норме — normal."
        )

        # Загрузка файла (фото или PDF)
        # Примечание: Gemini поддерживает прямую передачу байтов или файлов
        with open(file_path, 'rb') as f:
            image_data = f.read()

        # Формируем запрос
        # Для простоты используем формат контента с данными
        mime_type = "application/pdf" if file_path.endswith('.pdf') else "image/jpeg"
        
        response = await model.generate_content_async([
            system_prompt,
            {'mime_type': mime_type, 'data': image_data}
        ])

        # Очистка текста от возможных markdown-оберток ```json ... ```
        text_response = response.text
        if "```json" in text_response:
            text_response = text_response.split("```json")[1].split("```")[0].strip()
        elif "```" in text_response:
            text_response = text_response.split("```")[1].split("```")[0].strip()

        # Парсим JSON
        result = json.loads(text_response)
        return result

    except Exception as e:
        logger.error(f"Ошибка при работе с Gemini API: {e}")
        return None