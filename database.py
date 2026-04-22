import logging
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from config import config

# Настройка логирования
logger = logging.getLogger(__name__)

# Глобальная переменная для клиента, чтобы не инициализировать каждый раз
_db_client = None

def initialize_firebase():
    """
    Инициализирует подключение к Firebase Firestore.
    """
    global _db_client
    try:
        if not firebase_admin._apps:
            cred = credentials.Certificate(config.FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred, {
                'projectId': config.FIREBASE_PROJECT_ID,
            })
        _db_client = firestore.client()
        return _db_client
    except Exception as e:
        logger.error(f"Ошибка инициализации Firebase: {e}")
        return None

def get_db():
    """Возвращает клиента Firestore, инициализируя его при необходимости."""
    global _db_client
    if _db_client is None:
        return initialize_firebase()
    return _db_client

async def save_analysis_to_db(user_id, analysis_data: dict):
    """
    Сохраняет результат анализа в Firestore.
    Стыкуется с handlers.py (имя функции и параметры).
    """
    try:
        db = get_db()
        if not db:
            return False
            
        app_id = config.STAPLER_APP_ID
        user_id_str = str(user_id)
        
        # Ссылка на основной документ анализа
        analysis_ref = db.collection('artifacts').document(app_id) \
                         .collection('users').document(user_id_str) \
                         .collection('analyses').document()

        # Подготовка данных
        main_data = {
            "title": analysis_data.get('title', 'Медицинский анализ'),
            "date": analysis_data.get('date', datetime.now().strftime("%Y-%m-%d")),
            "laboratory": analysis_data.get('laboratory', 'Неизвестная лаборатория'),
            "summary": analysis_data.get('summary', ''),
            "created_at": firestore.SERVER_TIMESTAMP
        }

        # Сохраняем основной документ
        analysis_ref.set(main_data)

        # Сохраняем показатели (маркеры) в подколлекцию
        markers = analysis_data.get('indicators', [])
        if markers:
            batch = db.batch()
            for marker in markers:
                marker_ref = analysis_ref.collection('markers').document()
                marker_data = {
                    "name": marker.get('name', 'Неизвестно'),
                    "value": str(marker.get('value', '')),
                    "unit": marker.get('unit', ''),
                    "norm": marker.get('norm', ''),
                    "status": marker.get('status', 'normal'),
                    "date": main_data['date']
                }
                batch.set(marker_ref, marker_data)
            batch.commit()
            
        logger.info(f"✅ Анализ {analysis_ref.id} сохранен для пользователя {user_id}")
        return analysis_ref.id
    except Exception as e:
        logger.error(f"❌ Ошибка при сохранении в Firestore: {e}")
        return None

async def get_recent_analyses(user_id, limit: int = 5):
    """
    Получает историю анализов. 
    Имя функции изменено для совместимости с handlers.py
    """
    try:
        db = get_db()
        if not db:
            return []
            
        app_id = config.STAPLER_APP_ID
        user_id_str = str(user_id)

        analyses_ref = db.collection('artifacts').document(app_id) \
                         .collection('users').document(user_id_str) \
                         .collection('analyses')

        # ВАЖНО: Требует создания индекса в консоли Firebase, 
        # если используется order_by вместе с фильтрацией.
        query = analyses_ref.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()

        history = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            history.append(data)
            
        return history
    except Exception as e:
        logger.error(f"❌ Ошибка при получении истории: {e}")
        return []