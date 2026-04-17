import httpx
import json
import logging
import hashlib
import asyncio
from config import config

logger = logging.getLogger(__name__)

# Настройки модели
MODEL_NAME = "gemini-2.5-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

API_KEY = config.GEMINI_API_KEY

# Улучшенный системный промпт с логикой интерпретации медицинских норм
SYSTEM_PROMPT = (
    "Ты — профессиональный медицинский лабораторный ассистент Stapler. "
    "Твоя задача: провести OCR документа и извлечь данные в строгий JSON.\n\n"
    "ПРАВИЛА ИНТЕРПРЕТАЦИИ НОРМ:\n"
    "1. Если в графе 'Норма' стоит '< X' (например, < 1.2), то любой результат меньше X является НОРМАЛЬНЫМ (status: 'normal').\n"
    "2. Если результат равен 1, а норма < 1.2 — это статус 'normal', а не 'low'.\n"
    "3. Если результат в титрах совпадает с порогом (например, <1:40 и норма <1:40) — это 'normal'.\n"
    "4. Статус 'high' или 'low' ставится только если результат ВЫХОДИТ за пределы указанного диапазона или порога.\n\n"
    "ВАЖНО: Твое текстовое заключение (summary) должно СТРОГО соответствовать статусам (status) в параметрах. "
    "Если параметр 'normal', в summary нельзя писать, что он выше или ниже нормы.\n\n"
    "ФОРМАТ ОТВЕТА (JSON):\n"
    "{\n"
    "  'title': 'тип анализа',\n"
    "  'date': 'DD.MM.YYYY',\n"
    "  'laboratory': 'название клиники',\n"
    "  'parameters': [\n"
    "    { 'name': 'название', 'value': 'число', 'unit': 'ед.изм', 'norm': 'референс', 'status': 'normal/high/low' }\n"
    "  ],\n"
    "  'summary': 'краткое мед. заключение на русском (1-2 предложения).'\n"
    "}\n"
    "Если поле не найдено, используй 'Не указано'. Не используй null."
)

HISTORY_SYSTEM_PROMPT = (
    "Ты — медицинский эксперт Stapler. Отвечай на вопросы на основе истории анализов. "
    "Будь краток и профессионален."
)

async def make_request_with_retry(url, payload, proxy, max_retries=5):
    """Выполняет запрос к API с экспоненциальной задержкой."""
    delays = [1, 2, 4, 8, 16]
    transport = httpx.AsyncHTTPTransport(proxy=proxy) if proxy else None
    
    async with httpx.AsyncClient(transport=transport, timeout=60.0) as client:
        for i in range(max_retries):
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if i == max_retries - 1:
                    logger.error(f"Gemini API request failed: {e}")
                    raise
                await asyncio.sleep(delays[i])
    return None

async def analyze_document(base64_image: str, mime_type: str):
    """Анализ документа через Gemini API."""
    if not API_KEY:
        return {"error": "API Key is missing"}

    file_hash = hashlib.sha256(base64_image.encode()).hexdigest()
    url = f"{API_URL}?key={API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "Извлеки данные и проведи мед. анализ. Убедись, что 'summary' не противоречит 'status'."},
                {"inlineData": {"mimeType": mime_type, "data": base64_image}}
            ]
        }],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    proxy = config.PROXY_URL if config.PROXY_URL else None

    try:
        raw_result = await make_request_with_retry(url, payload, proxy)
        if not raw_result:
            return {"error": "Empty response"}

        text_content = raw_result['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(text_content)
        data["file_hash"] = file_hash
        return data
    except Exception as e:
        logger.error(f"AI Analysis Error: {e}")
        return {"error": str(e)}

async def analyze_history(history: list, user_query: str):
    """Анализ истории запросов пациента."""
    url = f"{API_URL}?key={API_KEY}"
    context = "История анализов пациента:\n"
    for item in history:
        context += f"- {item.get('date')}: {item.get('title')}\n"
    
    payload = {
        "contents": [{"parts": [{"text": f"{context}\nВопрос: {user_query}"}]}],
        "systemInstruction": {"parts": [{"text": HISTORY_SYSTEM_PROMPT}]}
    }

    proxy = config.PROXY_URL if config.PROXY_URL else None
    
    try:
        result = await make_request_with_retry(url, payload, proxy)
        if result:
            return result['candidates'][0]['content']['parts'][0]['text']
        return "Не удалось получить ответ."
    except Exception:
        return "Ошибка связи с ИИ."