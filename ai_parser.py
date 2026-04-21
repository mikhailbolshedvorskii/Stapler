import httpx
import json
import logging
import hashlib
import asyncio
from config import config

logger = logging.getLogger(__name__)

# Актуальная модель
MODEL_NAME = "gemini-3.1-flash-lite-preview" 
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

API_KEY = config.GEMINI_API_KEY

SYSTEM_PROMPT = (
    "Ты — медицинский ИИ-ассистент Stapler. Твоя роль: извлечение данных из медицинских документов в JSON.\n\n"
    "ПРАВИЛО ДЛЯ ОПИСАТЕЛЬНЫХ ИССЛЕДОВАНИЙ (РЕНТГЕН, МРТ, УЗИ):\n"
    "Если в документе нет таблицы с числовыми показателями, поле 'parameters' ДОЛЖНО быть пустым списком [].\n"
    "Всю важную информацию пиши ТОЛЬКО в поле 'summary'.\n\n"
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
                    error_data = response.json()
                    logger.error(f"API Error 400: {json.dumps(error_data, indent=2)}")
                    return {"error": f"Bad Request: {error_data.get('error', {}).get('message', 'Unknown')}"}
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if i == max_retries - 1: raise
                await asyncio.sleep(delays[i])
    return None

async def analyze_document(base64_image: str, mime_type: str):
    """Анализ первичного документа (изображение или PDF)."""
    if not API_KEY:
        return {"error": "API_KEY_NOT_FOUND"}

    file_hash = hashlib.sha256(base64_image.encode()).hexdigest()
    url = f"{API_URL}?key={API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "Проанализируй документ. Верни строго JSON."},
                {"inlineData": {"mimeType": mime_type, "data": base64_image}}
            ]
        }],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}
    }

    try:
        raw_result = await make_request_with_retry(url, payload, config.PROXY_URL)
        if "error" in raw_result: return raw_result
        text_content = raw_result['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(text_content)
        data["file_hash"] = file_hash
        return data
    except Exception as e:
        logger.error(f"AI Error: {e}")
        return {"error": str(e)}

async def analyze_history(history_text: str):
    """
    Анализ накопленной истории анализов (то, что не хватало).
    Принимает текстовое представление всех прошлых документов.
    """
    if not API_KEY:
        return "Ошибка: API ключ не настроен."

    url = f"{API_URL}?key={API_KEY}"
    
    prompt = (
        f"Ниже приведена история медицинских анализов пациента:\n\n{history_text}\n\n"
        "Проанализируй динамику. Выдели значимые изменения, тренды (улучшения или ухудшения) "
        "и дай общие рекомендации на что обратить внимание. Отвечай на русском языке, кратко и по делу."
    )

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.7}
    }

    try:
        raw_result = await make_request_with_retry(url, payload, config.PROXY_URL)
        if "error" in raw_result: return f"Ошибка API: {raw_result['error']}"
        return raw_result['candidates'][0]['content']['parts'][0]['text']
    except Exception as e:
        logger.error(f"History Analysis Error: {e}")
        return "Не удалось проанализировать историю анализов."