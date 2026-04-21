import httpx
import json
import logging
import hashlib
import asyncio
from config import config

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash-Lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

API_KEY = config.GEMINI_API_KEY

# Обновленный системный промпт с защитой от "лишних" строк
SYSTEM_PROMPT = (
    "Ты — профессиональный медицинский ассистент Stapler. Твоя задача: оцифровать документ в JSON.\n\n"
    "ПРАВИЛА ИЗВЛЕЧЕНИЯ:\n"
    "1. ОПРЕДЕЛЕНИЕ ТИПА: Если это текстовое описание (рентген, УЗИ, МРТ), поле 'parameters' ОБЯЗАТЕЛЬНО должно быть пустым списком [].\n"
    "2. КОЛИЧЕСТВЕННЫЕ ДАННЫЕ: Только если в документе есть таблица с анализами (кровь, моча и т.д.), заполняй 'parameters'.\n"
    "3. ЗАЩИТА ОТ МУСОРА: Не выдумывай параметры из предложений в описании. Если сомневаешься — не добавляй в 'parameters'.\n\n"
    "ПРАВИЛА ИНТЕРПРЕТАЦИИ НОРМ:\n"
    "1. Если результат внутри диапазона или совпадает с порогом (напр. результат 1, норма < 1.2) — status: 'normal'.\n"
    "2. 'high' или 'low' только при явном выходе за границы.\n\n"
    "ФОРМАТ ОТВЕТА (JSON):\n"
    "{\n"
    "  'title': 'тип анализа (напр. Рентгенография стоп)',\n"
    "  'date': 'DD.MM.YYYY',\n"
    "  'laboratory': 'название клиники',\n"
    "  'parameters': [\n"
    "    { 'name': 'название', 'value': 'число', 'unit': 'ед.изм', 'norm': 'референс', 'status': 'normal/high/low' }\n"
    "  ],\n"
    "  'summary': 'краткое и понятное заключение на русском (2-3 предложения). Для рентгена опиши суть здесь.'\n"
    "}\n"
    "Используй 'Не указано' вместо пустых полей, но для 'parameters' используй пустой массив [], если это не табличный анализ."
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
                {"text": "Извлеки данные строго по инструкции. Если это рентген или описание — оставь parameters пустым, всё пиши в summary."},
                {"inlineData": {"mimeType": mime_type, "data": base64_image}}
            ]
        }],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1  # Низкая температура для уменьшения галлюцинаций
        }
    }

    proxy = config.PROXY_URL if config.PROXY_URL else None

    try:
        raw_result = await make_request_with_retry(url, payload, proxy)
        if not raw_result:
            return {"error": "Empty response"}

        text_content = raw_result['candidates'][0]['content']['parts'][0]['text']
        data = json.loads(text_content)
        
        # Финальная чистка: если ИИ всё же засунул мусор в параметры (напр. 'Не указано')
        if "parameters" in data and isinstance(data["parameters"], list):
            data["parameters"] = [
                p for p in data["parameters"] 
                if p.get("name") != "Не указано" and p.get("value") != "Не указано"
            ]
            
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