import json
import os
import httpx
import logging
from typing import List, Dict, Any

# Настройка логирования
logger = logging.getLogger(__name__)

# Параметры модели ИИ
MODEL_NAME = "gemini-2.5-flash-lite"
API_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Системный промпт для формирования глубокого медицинского отчета
SUMMARY_SYSTEM_PROMPT = (
    "Ты — главный медицинский эксперт-координатор. "
    "Тебе предоставлены результаты нескольких разных анализов одного пациента. "
    "Твоя задача: найти взаимосвязи между показателями из разных документов, "
    "выявить общие паттерны (например, признаки воспаления, анемии или дефицитов) "
    "и составить единый, глубокий аналитический отчет. "
    "Ответ должен быть структурированным, на русском языке, объемом 15-25 предложений."
)

# Путь к локальному файлу истории (резервное хранилище)
HISTORY_FILE = "user_analyses_history.json"

def save_analysis_to_history(user_id: str, analysis_data: Dict[str, Any]):
    """
    Сохраняет результат анализа в локальный JSON-файл.
    Это полезно для быстрого доступа без постоянных запросов к Firestore.
    """
    history = load_full_history()
    
    str_user_id = str(user_id)
    if str_user_id not in history:
        history[str_user_id] = []
    
    history[str_user_id].append(analysis_data)
    
    try:
        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=4)
        logger.info(f"Данные локально сохранены для пользователя {user_id}")
    except Exception as e:
        logger.error(f"Ошибка сохранения локальной истории: {e}")

def load_user_history(user_id: str) -> List[Dict[str, Any]]:
    """
    Загружает историю анализов конкретного пользователя из локального файла.
    """
    history = load_full_history()
    return history.get(str(user_id), [])

def load_full_history() -> Dict[str, List[Dict[str, Any]]]:
    """
    Вспомогательная функция для чтения всего файла локальной истории.
    """
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка чтения файла истории: {e}")
        return {}

async def generate_combined_summary(all_results: List[Dict[str, Any]], api_key: str) -> str:
    """
    Принимает список результатов (JSON) от нескольких анализов и делает по ним общий вывод через ИИ.
    """
    if not all_results:
        return "Нет данных для анализа."

    # Получаем прокси из переменных окружения
    proxy_url = os.getenv("PROXY_URL")
    url = API_URL_TEMPLATE.format(model=MODEL_NAME) + f"?key={api_key}"
    
    # Формируем текстовый контекст для ИИ из всех документов
    context_text = "Результаты анализов пациента для сводного отчета:\n\n"
    for i, res in enumerate(all_results, 1):
        context_text += f"--- Документ №{i}: {res.get('title')} (Дата: {res.get('date')}) ---\n"
        context_text += f"Лаборатория: {res.get('laboratory')}\n"
        for p in res.get('parameters', []):
            context_text += f"- {p['name']}: {p['value']} {p.get('unit', '')} (Статус: {p.get('status', 'не указан')})\n"
        context_text += "\n"

    payload = {
        "contents": [{
            "parts": [
                {"text": f"Проанализируй эти данные и составь общий вывод:\n\n{context_text}"}
            ]
        }],
        "systemInstruction": {"parts": [{"text": SUMMARY_SYSTEM_PROMPT}]}
    }

    # Настройка прокси для httpx
    mounts = {"all://": httpx.Proxy(proxy_url)} if proxy_url else None

    async with httpx.AsyncClient(mounts=mounts, timeout=60.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            
            result = response.json()
            summary_text = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
            return summary_text
        except Exception as e:
            logger.error(f"Ошибка при создании сводного отчета ИИ: {e}")
            return "Извините, не удалось сформировать общий аналитический отчет. Попробуйте позже."