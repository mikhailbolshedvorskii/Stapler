import firebase_admin
from firebase_admin import credentials, firestore
import logging
import os
from datetime import datetime

# Настройка локального логгера
logger = logging.getLogger(__name__)

# Путь к ключу (файл должен быть в корне проекта)
CONF_PATH = os.path.join(os.getcwd(), 'firebase_key.json')

# Единый идентификатор приложения для всей экосистемы Stapler
APP_ID = "stapler-app"

def initialize_firebase():
    """Явная функция инициализации Firebase Admin SDK"""
    try:
        if not firebase_admin._apps:
            if os.path.exists(CONF_PATH):
                cred = credentials.Certificate(CONF_PATH)
                firebase_admin.initialize_app(cred)
                print(f"✅ [STAPLER DB] Успешный вход. Используем APP_ID: {APP_ID}")
                return firestore.client()
            else:
                print(f"❌ [STAPLER DB] Файл ключа не найден: {CONF_PATH}")
                return None
        return firestore.client()
    except Exception as e:
        print(f"❌ [STAPLER DB] Ошибка инициализации: {e}")
        return None

# Инициализируем БД при импорте модуля
db = initialize_firebase()

async def is_duplicate_analysis(user_id: str, file_hash: str) -> bool:
    """Проверяет наличие анализа с таким же хешем в базе Stapler."""
    if not db or not file_hash:
        return False
    try:
        # Путь: /artifacts/stapler-app/users/{user_id}/analyses
        user_analyses_ref = db.collection('artifacts', APP_ID, 'users', str(user_id), 'analyses')
        
        # RULE 2: Простой запрос по полю file_hash
        query = user_analyses_ref.where("file_hash", "==", file_hash).limit(1)
        docs = query.get()
        return len(docs) > 0
    except Exception as e:
        logger.error(f"Ошибка при проверке дубликатов: {e}")
        return False

async def save_medical_analysis(user_id: str, data: dict):
    """
    Сохранение оцифрованных данных в Firestore.
    Возвращает True, False или "duplicate".
    """
    global db
    if db is None:
        db = initialize_firebase()
        if db is None:
            logger.error("Критическая ошибка: База данных недоступна.")
            return False

    file_hash = data.get("file_hash")
    
    # Защита от повторной загрузки того же файла
    if await is_duplicate_analysis(user_id, file_hash):
        print(f"⚠️ [STAPLER DB] Файл уже существует для пользователя {user_id}. Пропуск.")
        return "duplicate"

    print(f"⏳ [STAPLER DB] Запись данных в облако для пользователя {user_id}...")

    try:
        # Основная коллекция анализов
        user_analyses_ref = db.collection('artifacts', APP_ID, 'users', str(user_id), 'analyses')
        
        analysis_doc = {
            "title": data.get("title", "Документ Stapler"),
            "date": data.get("date", datetime.now().strftime("%d.%m.%Y")),
            "laboratory": data.get("laboratory", "Не указана"),
            "summary": data.get("summary", ""),
            "file_hash": file_hash,
            "created_at": firestore.SERVER_TIMESTAMP
        }
        
        # Создаем документ анализа
        new_doc_ref = user_analyses_ref.document()
        new_doc_ref.set(analysis_doc)
        
        # Сохраняем конкретные параметры в подколлекцию 'markers' для графиков
        markers_ref = new_doc_ref.collection('markers')
        parameters = data.get("parameters", [])
        
        for param in parameters:
            marker_data = {
                "name": param.get("name"),
                "value": param.get("value"),
                "unit": param.get("unit"),
                "norm": param.get("norm"),
                "status": param.get("status"),
                "date": analysis_doc["date"]
            }
            markers_ref.add(marker_data)
            
        print(f"✅ [STAPLER DB] Данные успешно сохранены (ID: {new_doc_ref.id})")
        return True

    except Exception as e:
        print(f"❌ [STAPLER DB] Ошибка записи: {e}")
        return False

async def get_recent_analyses(user_id: str, limit: int = 5):
    """Загрузка истории из облака Stapler для команды /history"""
    if db is None: return []
    try:
        query = db.collection('artifacts', APP_ID, 'users', str(user_id), 'analyses')\
                  .order_by("created_at", direction=firestore.Query.DESCENDING)\
                  .limit(limit)
        
        docs = query.stream()
        results = []
        for doc in docs:
            analysis = doc.to_dict()
            analysis['id'] = doc.id
            # Достаем маркеры для отображения деталей в истории
            markers = doc.reference.collection('markers').stream()
            analysis['parameters'] = [m.to_dict() for m in markers]
            results.append(analysis)
        return results
    except Exception as e:
        logger.error(f"Ошибка получения истории Stapler: {e}")
        return []