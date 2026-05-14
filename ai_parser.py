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
        system_prompt = """
Ты — профессиональный медицинский эксперт-аналитик Stapler. Твоя задача: детально извлечь данные из медицинского документа и дать понятное, развернутое объяснение пациенту.

ВАЖНО ДЛЯ ТЕКСТОВЫХ ЗАКЛЮЧЕНИЙ (УЗИ, МРТ, Рентген, КТ):
1. Создай в списке 'indicators' ОДИН объект. Поле 'name' должно быть 'Заключение'.
2. В поле 'value' перенеси суть исследования и все обнаруженные находки. 
3. Весь текст пиши СТРОГО на РУССКОМ языке.

ПРАВИЛА ОПРЕДЕЛЕНИЯ СТАТУСА (ПОЛЕ 'status') — СЛЕДУЙ ИМ НЕУКОСНИТЕЛЬНО:
- 'attention': Используй для начальных, хронических, умеренных или минимальных изменений (например: остеоартроз 1-2 стадии, плоскостопие, умеренная лимфоаденопатия, кисты, диффузные изменения). Это НЕ норма, но и НЕ катастрофа. Это пограничное состояние, требующее внимания и контроля.
- 'normal': Только если прямо написано 'патологий не обнаружено', 'без особенностей' или числовые показатели строго в референсе.
- 'low' / 'high': Только для числовых выходов за границы лабораторных референсов.
- 'pathology': Для тяжелых, острых, деструктивных или критических состояний (например, переломы, разрывы органов, подозрение на онкологию).

СТРУКТУРА ПОЛЯ 'summary' (КОММЕНТАРИЙ GEMINI) — ЗАПОЛНЯЙ СТРОГО ПО ТРЕМ ПУНКТАМ:
1) Что обнаружено: Краткий пересказ выявленных изменений простыми и понятными словами (без перегрузки сложными терминами).
2) Что это означает: Доступное объяснение сути процесса (например: 'Остеоартроз 1 степени — это начальные, чаще всего обратимые изменения в хрящевой ткани суставов, которые могут возникать из-за нагрузок или возрастных факторов...').
3) Рекомендации: Четкий совет, к какому именно узкому специалисту обратиться для очной консультации (например: ортопед, травматолог, невролог, ревматолог) и какие общие меры предосторожности стоит соблюдать.
"""


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