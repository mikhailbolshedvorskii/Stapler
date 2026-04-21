import logging
import firebase_admin
from firebase_admin import credentials, firestore
from config import config

# Настройка логирования
logger = logging.getLogger(__name__)

def initialize_firebase():
    """
    Инициализирует соединение с Firebase.
    Использует путь к ключу из config.py.
    """
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(config.FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
        return firestore.client()
    except Exception as e:
        logger.error(f"Критическая ошибка при инициализации Firebase: {e}")
        return None

# Глобальный клиент базы данных
db = initialize_firebase()

async def save_analysis(user_id: str, analysis_data: dict):
    """
    Сохраняет оцифрованный анализ в Firestore.
    
    Путь: /artifacts/stapler-app/users/{userId}/analyses/{docId}
    """
    if not db:
        logger.error("База данных не инициализирована.")
        return None

    try:
        app_id = config.STAPLER_APP_ID
        # Создаем ссылку на новый документ в основной коллекции анализов пользователя
        doc_ref = db.collection("artifacts").document(app_id)\
                    .collection("users").document(str(user_id))\
                    .collection("analyses").document()
        
        # Сохраняем метаданные анализа
        doc_ref.set({
            "title": analysis_data.get("title", "Анализ"),
            "date": analysis_data.get("date"),
            "laboratory": analysis_data.get("laboratory", "Не указана"),
            "summary": analysis_data.get("summary", ""),
            "created_at": firestore.SERVER_TIMESTAMP,
            "raw_results_count": len(analysis_data.get("parameters", []))
        })

        # Сохраняем каждый параметр (маркер) в отдельную подколлекцию
        # Это позволяет в будущем строить графики по конкретному названию маркера
        for marker in analysis_data.get("parameters", []):
            marker_ref = doc_ref.collection("markers").document()
            marker_ref.set({
                "name": marker.get("name"),
                "value": marker.get("value"), # Может быть числом или строкой ("отрицательно")
                "unit": marker.get("unit", ""),
                "norm": marker.get("norm", ""),
                "status": marker.get("status", "normal"),
                "date": analysis_data.get("date") # Дублируем дату для легкого поиска в подколлекциях
            })
            
        logger.info(f"✅ Анализ успешно сохранен. ID: {doc_ref.id}")
        return doc_ref.id
    except Exception as e:
        logger.error(f"Ошибка при сохранении анализа в БД: {e}")
        return None

async def get_recent_analyses(user_id: str, limit: int = 5):
    """
    Загружает последние анализы пользователя.
    Для каждого анализа также подгружаются все маркеры из подколлекции.
    """
    if not db:
        return []

    try:
        app_id = config.STAPLER_APP_ID
        analyses_ref = db.collection("artifacts").document(app_id)\
                         .collection("users").document(str(user_id))\
                         .collection("analyses")
        
        # Получаем документы. Согласно правилам, сложные фильтры без индексов не используем.
        # Просто берем последние добавленные (по умолчанию Firestore возвращает по ID или времени создания)
        docs = analyses_ref.limit(limit).stream()
        
        results = []
        for d in docs:
            analysis = d.to_dict()
            analysis['id'] = d.id
            
            # Подгружаем маркеры для текущего анализа
            markers_docs = d.reference.collection("markers").stream()
            analysis['parameters'] = [m.to_dict() for m in markers_docs]
            
            results.append(analysis)
            
        # Сортируем в памяти по дате (если даты в формате YYYY-MM-DD)
        results.sort(key=lambda x: x.get('date', ''), reverse=True)
        
        return results
    except Exception as e:
        logger.error(f"Ошибка при получении истории из БД: {e}")
        return []

async def delete_analysis(user_id: str, doc_id: str):
    """
    Удаляет конкретный анализ пользователя.
    """
    try:
        app_id = config.STAPLER_APP_ID
        doc_ref = db.collection("artifacts").document(app_id)\
                    .collection("users").document(str(user_id))\
                    .collection("analyses").document(doc_id)
        
        # В Firestore подколлекции нужно удалять вручную или через консоль, 
        # здесь мы удаляем основной документ.
        doc_ref.delete()
        return True
    except Exception as e:
        logger.error(f"Ошибка при удалении документа: {e}")
        return False