import httpx
import json
import logging
import hashlib
import asyncio
from config import config

logger = logging.getLogger(__name__)

# Актуальная модель по состоянию на апрель 2026 года
MODEL_NAME = "gemini-3.1-flash-lite-preview" 
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

API_KEY = config.GEMINI_API_KEY

# Системный промпт оптимизирован для работы с Flash-Lite версиями
SYSTEM_PROMPT = (
    "Ты — медицинский ИИ-ассистент Stapler. Твоя роль: извлечение данных из медицинских документов в JSON.\n\n"
    "ПРАВИЛО ДЛЯ ОПИСАТЕЛЬНЫХ ИССЛЕДОВАНИЙ (РЕНТГЕН, МРТ, УЗИ):\n"
    "Если в документе нет таблицы с числовыми показателями, поле 'parameters' ДОЛЖНО быть пустым списком [].\n"
    "Всю важную информацию (например, углы стоп 19° и 22°, наличие артроза) пиши ТОЛЬКО в поле 'summary'.\n\n"
    "ПРАВИЛО ДЛЯ ЛАБОРАТОРНЫХ АНАЛИЗОВ:\n"
    "Заполняй 'parameters', только если есть поля: Название, Результат, Ед. изм., Референс.\n"
    "Интерпретация: если результат в норме — 'normal', если выше/ниже — 'high'/'low'.\n\n"
    "ФОРМАТ JSON:\n"
    "{\n"
    "  'title': 'тип документа',\n"
    "  'date': 'DD.MM.YYYY',\n"
    "  'laboratory': 'название учреждения',\n"
    "  'parameters': [],\n"
    "  'summary': 'связный текст заключения на русском языке.'\n"
    "}"
)

async def make_request_with_retry(url, payload, proxy, max_retries=5):
    """Выполняет запрос к Gemini API с экспоненциальным бэк-оффом."""
    delays = [1, 2, 4, 8, 16]
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    
    async with httpx.AsyncClient(transport=transport, timeout=90.0) as client:
        for i in range(max_retries):
            try:
                response = await client.post(url, json=payload)
                
                if response.status_code == 400:
                    # Логируем детальную причину от Google (очень важно для Preview моделей)
                    error_data = response.json()
                    logger.error(f"API Error 400: {json.dumps(error_data, indent=2)}")
                    return {"error": f"Bad Request: {error_data.get('error', {}).get('message', 'Unknown')}"}
                
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"Attempt {i+1} failed: {e.response.status_code}")
                if i == max_retries - 1: raise
            except Exception as e:
                logger.warning(f"Connection error on attempt {i+1}: {e}")
                if i == max_retries - 1: raise
                
            await asyncio.sleep(delays[i])
    return None

async def analyze_document(base64_image: str, mime_type: str):
    """
    Основная функция анализа изображения или PDF.
    Использует мультимодальные возможности gemini-3.1-flash-lite-preview.
    """
    if not API_KEY:
        return {"error": "API_KEY_NOT_FOUND"}

    file_hash = hashlib.sha256(base64_image.encode()).hexdigest()
    url = f"{API_URL}?key={API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "Проанализируй этот документ. Верни строго JSON. Если это описание снимка, оставь parameters пустым."},
                {"inlineData": {"mimeType": mime_type, "data": base64_image}}
            ]
        }],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }

    proxy = config.PROXY_URL if config.PROXY_URL else None

    try:
        raw_result = await make_request_with_retry(url, payload, proxy)
        
        if "error" in raw_result:
            return raw_result

        text_content = raw_result['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(text_content)
        
        # Пост-обработка: если модель по привычке заполнила параметры мусором для рентгена
        if "parameters" in data and isinstance(data["parameters"], list):
            data["parameters"] = [p for p in data["parameters"] if p.get("name") and p.get("name") != "Не указано"]
            
        data["file_hash"] = file_hash
        return data
    except Exception as e:
        logger.error(f"AI Critical Error: {e}")
        return {"error": f"Internal system error: {str(e)}"}