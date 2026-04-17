import firebase_admin
from firebase_admin import credentials, firestore
import logging
import os
from datetime import datetime

# Настройка локального логгера
logger = logging.getLogger(__name__)

# Путь к ключу
CONF_PATH = os.path.join(os.getcwd(), 'firebase_key.json')

def initialize_firebase():
    """Явная функция инициализации, которую мы вызовем при старте"""
    try:
        if not firebase_admin._apps:
            if os.path.exists(CONF_PATH):
                cred = credentials.Certificate(CONF_PATH)
                firebase_admin.initialize_app(cred)
                print(f"✅ [FIREBASE] Успешный вход с файлом: {CONF_PATH}")
                return firestore.client()
            else:
                print(f"❌ [FIREBASE] Файл не найден: {CONF_PATH}")
                return None
        return firestore.client()
    except Exception as e:
        print(f"❌ [FIREBASE] Ошибка: {e}")
        return None

# Инициализируем при загрузке модуля
db = initialize_firebase()

APP_ID = "second-opinion-app"

async def is_duplicate_analysis(user_id: str, file_hash: str) -> bool:
    """Проверяет, существует ли уже анализ с таким хешем у пользователя."""
    if not db or not file_hash:
        return False
    try:
        # Ищем документы в коллекции анализов пользователя по полю file_hash
        user_analyses_ref = db.collection('artifacts', APP_ID, 'users', str(user_id), 'analyses')
        # RULE 2: Используем простой фильтр, так как file_hash — уникальное поле для поиска
        query = user_analyses_ref.where("file_hash", "==", file_hash).limit(1)
        docs = query.get()
        return len(docs) > 0
    except Exception as e:
        logger.error(f"Ошибка при проверке дубликатов: {e}")
        return False

async def save_medical_analysis(user_id: str, data: dict):
    """Сохранение анализа с проверкой на дубликаты."""
    global db
    if db is None:
        db = initialize_firebase()
        if db is None:
            logger.error("База данных всё еще недоступна.")
            return False

    file_hash = data.get("file_hash")
    
    # Проверка на дубликат перед сохранением
    if await is_duplicate_analysis(user_id, file_hash):
        print(f"⚠️ [DB] Обнаружен дубликат файла для пользователя {user_id}. Пропускаю.")
        return "duplicate"

    print(f"⏳ [DB] Начинаю сохранение для пользователя {user_id}...")

    try:
        user_analyses_ref = db.collection('artifacts', APP_ID, 'users', str(user_id), 'analyses')
        
        analysis_doc = {
            "title": data.get("title", "Общий анализ"),
            "date": data.get("date", datetime.now().strftime("%d.%m.%Y")),
            "laboratory": data.get("laboratory", "Не указана"),
            "summary": data.get("summary", ""),
            "file_hash": file_hash, # Сохраняем хеш для будущих проверок
            "created_at": firestore.SERVER_TIMESTAMP
        }
        
        new_doc_ref = user_analyses_ref.document()
        new_doc_ref.set(analysis_doc)
        
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
            
        print(f"✅ [DB] Анализ успешно сохранен! (ID: {new_doc_ref.id})")
        return True

    except Exception as e:
        print(f"❌ [DB] Ошибка при записи в Firestore: {e}")
        logger.error(f"Ошибка сохранения: {e}")
        return False

async def get_recent_analyses(user_id: str, limit: int = 5):
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
            markers = doc.reference.collection('markers').stream()
            analysis['parameters'] = [m.to_dict() for m in markers]
            results.append(analysis)
        return results
    except Exception as e:
        logger.error(f"Ошибка получения истории: {e}")
        return []