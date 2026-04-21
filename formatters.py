def format_analysis_card(data):
    """
    Превращает словарь с результатами анализа в красивый текст для Telegram.
    """
    if not data:
        return "❌ Ошибка при обработке данных."

    title = data.get('title', 'Медицинский анализ')
    date = data.get('date', 'дата не указана')
    lab = data.get('laboratory', 'Лаборатория не определена')
    
    # Заголовок карточки
    lines = [
        f"📋 **{title}**",
        f"📅 Дата: {date}",
        f"🏥 {lab}",
        "⎯" * 15
    ]

    # Список показателей
    indicators = data.get('indicators', [])
    if not indicators:
        lines.append("\n_Показатели не обнаружены или не распознаны._")
    else:
        for ind in indicators:
            name = ind.get('name', 'Неизвестно')
            value = ind.get('value', '-')
            unit = ind.get('unit', '')
            norm = ind.get('norm', '')
            status = ind.get('status', 'normal') # 'normal', 'high', 'low', 'warning'

            # Выбор эмодзи в зависимости от статуса
            emoji = "✅"
            if status == 'high':
                emoji = "🔼"
            elif status == 'low':
                emoji = "🔽"
            elif status == 'warning':
                emoji = "⚠️"

            # Формируем строку показателя
            line = f"{emoji} **{name}**: {value} {unit}"
            if norm:
                line += f" _(Норма: {norm})_"
            
            lines.append(line)

    # Резюме/Заключение от ИИ
    summary = data.get('summary')
    if summary:
        lines.append("\n🤖 **Заключение ИИ:**")
        lines.append(f"_{summary}_")

    # Футер
    lines.append("\n💾 _Данные сохранены в ваш личный профиль._")
    lines.append("❗ *Не является диагнозом. Обратитесь к врачу.*")

    return "\n".join(lines)