import logging
import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime, timedelta
from config import config

# Настройка логирования
logger = logging.getLogger(__name__)

_db_client = None

def initialize_firebase():
    """Инициализирует подключение к Firebase Firestore."""
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
    """Возвращает клиента Firestore."""
    global _db_client
    if _db_client is None:
        return initialize_firebase()
    return _db_client

async def save_analysis_to_db(user_id, analysis_data: dict, file_unique_id: str = None):
    """Асинхронная обертка для сохранения анализа с защитой от дубликатов."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_save_analysis, user_id, analysis_data, file_unique_id)

def _sync_save_analysis(user_id, analysis_data: dict, file_unique_id: str):
    """Синхронная логика сохранения с проверкой на дубликаты."""
    try:
        db = get_db()
        if not db: return None
            
        app_id = config.STAPLER_APP_ID
        user_id_str = str(user_id)
        
        user_analyses_ref = db.collection('artifacts').document(app_id) \
                              .collection('users').document(user_id_str) \
                              .collection('analyses')

        # 1. ЗАЩИТА ОТ ДУБЛИКАТОВ
        if file_unique_id:
            existing = user_analyses_ref.where(field_path="file_unique_id", op_string="==", value=file_unique_id).get()
            if len(existing) > 0:
                logger.info(f"⚠️ Дубликат файла {file_unique_id} для пользователя {user_id}")
                return "duplicate"

        # 2. СОЗДАНИЕ ЗАПИСИ
        analysis_ref = user_analyses_ref.document()

        main_data = {
            "title": analysis_data.get('title', 'Медицинский анализ'),
            "date": analysis_data.get('date', datetime.now().strftime("%Y-%m-%d")),
            "laboratory": analysis_data.get('laboratory', 'Неизвестная лаборатория'),
            "summary": analysis_data.get('summary', ''),
            "file_unique_id": file_unique_id, # Сохраняем для будущих проверок
            "created_at": firestore.SERVER_TIMESTAMP
        }

        analysis_ref.set(main_data)

        # 3. СОХРАНЕНИЕ ИНДИКАТОРОВ
        markers = analysis_data.get('indicators') or analysis_data.get('parameters') or []
        if markers:
            batch = db.batch()
            for marker in markers:
                marker_ref = analysis_ref.collection('markers').document()
                batch.set(marker_ref, {
                    "name": marker.get('name', 'Неизвестно'),
                    "value": str(marker.get('value', '')),
                    "unit": marker.get('unit', ''),
                    "norm": marker.get('norm', ''),
                    "status": marker.get('status', 'normal'),
                    "date": main_data['date']
                })
            batch.commit()
            
        logger.info(f"✅ Анализ {analysis_ref.id} успешно сохранен.")
        return analysis_ref.id
    except Exception as e:
        logger.error(f"❌ Ошибка Firestore при сохранении: {e}")
        return None

async def get_recent_analyses(user_id, limit: int = 5, days: int = None):
    """Получает историю анализов с подгрузкой показателей."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, _sync_get_analyses, user_id, limit, days)

def _sync_get_analyses(user_id, limit, days):
    """Синхронная логика выборки из БД."""
    try:
        db = get_db()
        if not db: return []
            
        user_ref = db.collection('artifacts').document(config.STAPLER_APP_ID) \
                     .collection('users').document(str(user_id)) \
                     .collection('analyses')
        
        # Сначала создаем базовый запрос
        query = user_ref.order_by(field_path="created_at", direction=firestore.Query.DESCENDING)

        # Затем, ЕСЛИ указаны дни, добавляем фильтр

        if days:
            start_date = datetime.now() - timedelta(days=days)
            query = query.where(field_path="created_at", op_string=">=", value=start_date)

        if limit:
            query = query.limit(limit)

        docs = query.stream()
        history = []
        for doc in docs:
            data = doc.to_dict()
            data['id'] = doc.id
            
            # Важно для графиков: подгружаем все маркеры для каждого анализа
            markers_docs = doc.reference.collection('markers').stream()
            data['indicators'] = [m.to_dict() for m in markers_docs]
            
            history.append(data)
            
        return history
    except Exception as e:
        logger.error(f"❌ Ошибка при получении данных: {e}")
        return []