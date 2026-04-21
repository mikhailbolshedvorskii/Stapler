import logging
from firebase_admin import firestore
from config import config

# Инициализация клиента (предполагаем, что initialize_firebase уже вызван в main.py)
db = firestore.client()

async def get_recent_analyses(user_id: str, limit: int = 5):
    """
    Получает последние анализы пользователя из Firestore.
    """
    try:
        # Используем путь из архитектуры: /artifacts/stapler-app/users/{userId}/analyses
        analyses_ref = db.collection("artifacts").document(config.STAPLER_APP_ID)\
                         .collection("users").document(user_id)\
                         .collection("analyses")
        
        # ВАЖНО: Согласно RULE 2, мы не используем orderBy в сложных запросах без индексов,
        # но для простого получения документов это допустимо, если индекс создан.
        # Если индекса нет, просто берем последние документы.
        docs = analyses_ref.limit(limit).stream()
        
        results = []
        for d in docs:
            data = d.to_dict()
            data['id'] = d.id
            
            # Загружаем маркеры для каждого анализа
            markers = d.reference.collection("markers").stream()
            data['parameters'] = [m.to_dict() for m in markers]
            
            results.append(data)
        
        return results
    except Exception as e:
        logging.error(f"Ошибка при получении истории: {e}")
        return []

async def save_analysis(user_id, analysis_data):
    """
    Сохраняет данные анализа, поддерживая и числа, и строки в поле value.
    """
    app_id = config.STAPLER_APP_ID
    doc_ref = db.collection("artifacts").document(app_id)\
                .collection("users").document(user_id)\
                .collection("analyses").document()
    
    doc_ref.set({
        "title": analysis_data.get("title"),
        "date": analysis_data.get("date"),
        "laboratory": analysis_data.get("laboratory"),
        "summary": analysis_data.get("summary"),
        "created_at": firestore.SERVER_TIMESTAMP
    })

    for marker in analysis_data.get("parameters", []):
        m_ref = doc_ref.collection("markers").document()
        # Сохраняем значение 'as is' (число или строка)
        m_ref.set({
            "name": marker.get("name"),
            "value": marker.get("value"), 
            "unit": marker.get("unit", ""),
            "norm": marker.get("norm", ""),
            "status": marker.get("status", "normal"),
            "date": analysis_data.get("date")
        })
    return doc_ref.id