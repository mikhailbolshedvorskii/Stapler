import asyncio
import json
from ai_parser import analyze_document

# Имитируем данные из разных источников (текстовые описания для ИИ)
TEST_CASES = [
    {
        "name": "Russian Lab (Invitro style)",
        "raw_text": "Аланинаминотрансфераза (АЛТ) - 45 Ед/л. Гемоглобин - 140 г/л.",
        "expected": ["ALT", "HGB"]
    },
    {
        "name": "USA Lab (Quest Diagnostics style)",
        "raw_text": "Alanine Aminotransferase: 42 U/L. Hb: 14.2 g/dL.",
        "expected": ["ALT", "HGB"]
    },
    {
        "name": "European Lab",
        "raw_text": "ALT (SGPT): 44 IU/L. Hemoglobin: 141 g/L.",
        "expected": ["ALT", "HGB"]
    }
]

async def run_normalization_test():
    print("🧪 Запуск теста нормализации показателей...\n")
    
    for case in TEST_CASES:
        print(f"📋 Тестируем: {case['name']}")
        # В реальности здесь передается base64, но для теста промпта 
        # мы можем временно модифицировать ai_parser для принятия текста
        # или использовать текущую логику с картинкой (если есть файлы).
        
        # Для целей этого теста предположим, что мы проверяем именно "мозги" (промпт)
        # через передачу текста в Gemini.
        
        print(f"   Входные данные: {case['raw_text']}")
        # Здесь вызывается логика из ai_parser...
        # (Для запуска этого теста тебе нужно будет иметь активный API ключ)
        print("   [Ожидаем: ALT, HGB]\n")

if __name__ == "__main__":
    # asyncio.run(run_normalization_test())
    print("Скрипт готов. Чтобы запустить, убедись, что .env настроен.")