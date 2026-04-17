import httpx
import json
import logging
from config import config

logger = logging.getLogger(__name__)

# Настройки модели
MODEL_NAME = "gemini-2.5-flash-lite"
API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent"

# Ключ теперь берется из конфига, если не задан явно
API_KEY = config.GEMINI_API_KEY

SYSTEM_PROMPT = (
    "Ты — медицинский ИИ-ассистент Stapler. Твоя задача: провести OCR документа, "
    "извлечь показатели и вернуть их в строгом JSON формате на русском языке."
)

async def analyze_document(base64_image: str, mime_type: str):
    """
    Асинхронный анализ документа через Gemini API с поддержкой прокси.
    """
    if not API_KEY:
        return {"error": "API Key is missing"}

    url = f"{API_URL}?key={API_KEY}"
    
    payload = {
        "contents": [{
            "parts": [
                {"text": "Извлеки все медицинские показатели, дату и название лаборатории из этого документа."},
                {"inlineData": {"mimeType": mime_type, "data": base64_image}}
            ]
        }],
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "generationConfig": {
            "responseMimeType": "application/json"
        }
    }

    # Настройка прокси для запросов к Google
    mounts = {"all://": httpx.HTTPProxy(config.PROXY_URL)} if config.PROXY_URL else None

    async with httpx.AsyncClient(mounts=mounts, timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            raw_result = response.json()
            text_content = raw_result['candidates'][0]['content']['parts'][0]['text']
            
            return json.loads(text_content)
        except Exception as e:
            logger.error(f"AI Analysis Error: {e}")
            return {"error": str(e)}