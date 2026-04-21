import logging
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from config import config

# Настройка логирования
logger = logging.getLogger(__name__)

def initialize_firebase():
    """
    Инициализирует подключение к Firebase Firestore.
    Использует путь к ключу из config.py.
    """
    try:
        # Проверяем, не инициализировано ли уже приложение
        if not firebase_admin._apps:
            cred = credentials.Certificate(config.FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred, {
                'projectId': config.FIREBASE_PROJECT_ID,
            })
        return firestore.client()
    except Exception as e:
        logger.error(f"Ошибка инициализации Firebase: {e}")
        return None

def get_db():
    """Возвращает клиента Firestore."""
    return firestore.client()

async def save_analysis_to_db(user_id: int, analysis_data: dict):
    """
    Сохраняет результат анализа в Firestore.
    Путь: /artifacts/stapler-app/users/{userId}/analyses/{docId}
    """
    try:
        db = get_db()
        app_id = config.STAPLER_APP_ID
        user_id_str = str(user_id)
        
        # 1. Создаем ссылку на основной документ анализа
        analysis_ref = db.collection('artifacts').document(app_id) \
                         .collection('users').document(user_id_str) \
                         .collection('analyses').document()

        # Подготовка основных данных документа
        main_data = {
            "title": analysis_data.get('title', 'Медицинский анализ'),
            "date": analysis_data.get('date', datetime.now().strftime("%Y-%m-%d")),
            "laboratory": analysis_data.get('laboratory', 'Неизвестная лаборатория'),
            "summary": analysis_data.get('summary', ''),
            "created_at": firestore.SERVER_TIMESTAMP,
            "raw_text": analysis_data.get('raw_text', '') # Опционально: оригинал текста
        }

        # Сохраняем основной документ
        analysis_ref.set(main_data)
        logger.info(f"Основной документ анализа создан: {analysis_ref.id}")

        # 2. Сохраняем показатели (маркеры) в подколлекцию
        markers = analysis_data.get('indicators', []) or analysis_data.get('parameters', [])
        if markers:
            markers_batch = db.batch()
            for marker in markers:
                marker_doc_ref = analysis_ref.collection('markers').document()
                
                # Приводим данные маркера к стандарту
                marker_data = {
                    "name": marker.get('name', 'Неизвестно'),
                    "value": str(marker.get('value', '')),
                    "unit": marker.get('unit', ''),
                    "norm": marker.get('norm', ''),
                    "status": marker.get('status', 'normal'),
                    "date": main_data['date'] # Дублируем дату для легкой фильтрации в будущем
                }
                markers_batch.set(marker_doc_ref, marker_data)
            
            markers_batch.commit()
            logger.info(f"Успешно сохранено {len(markers)} маркеров для анализа {analysis_ref.id}")

        return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении в Firestore: {e}")
        return False

async def get_user_history(user_id: int, limit: int = 5):
    """
    Получает список последних анализов пользователя из Firestore.
    """
    try:
        db = get_db()
        app_id = config.STAPLER_APP_ID
        user_id_str = str(user_id)

        analyses_ref = db.collection('artifacts').document(app_id) \
                         .collection('users').document(user_id_str) \
                         .collection('analyses')

        # Сортируем по дате создания (требуется индекс в Firestore, либо простая выборка)
        query = analyses_ref.order_by("created_at", direction=firestore.Query.DESCENDING).limit(limit)
        docs = query.stream()

        history = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            history.append(data)
            
        return history
    except Exception as e:
        logger.error(f"Ошибка при получении истории из Firestore: {e}")
        return []

async def get_analysis_details(user_id: int, analysis_id: str):
    """
    Получает детальную информацию об анализе вместе с маркерами.
    """
    try:
        db = get_db()
        app_id = config.STAPLER_APP_ID
        user_id_str = str(user_id)

        doc_ref = db.collection('artifacts').document(app_id) \
                    .collection('users').document(user_id_str) \
                    .collection('analyses').document(analysis_id)

        doc = doc_ref.get()
        if not doc.exists:
            return None

        analysis_data = doc.to_dict()
        
        # Загружаем маркеры
        markers_docs = doc_ref.collection('markers').stream()
        analysis_data['markers'] = [m.to_dict() for m in markers_docs]
        
        return analysis_data
    except Exception as e:
        logger.error(f"Ошибка при получении деталей анализа: {e}")
        return None