import os
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
import io

# Регистрируем шрифт для поддержки русского языка
# Убедись, что файл DejaVuSans.ttf лежит в той же папке!
FONT_PATH = "DejaVuSans.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_PATH))
    MAIN_FONT = 'DejaVuSans'
else:
    MAIN_FONT = 'Helvetica' # Резервный, если шрифт не найден (русский не будет виден)

def create_medical_report(user_name, history, charts_data=None):
    """
    Создает PDF-отчет со списком анализов и графиками.
    charts_data: список объектов BufferedInputFile с графиками
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
    elements = []
    
    styles = getSampleStyleSheet()
    # Создаем кастомный стиль для русского текста
    rus_style = ParagraphStyle(
        'RusStyle',
        parent=styles['Normal'],
        fontName=MAIN_FONT,
        fontSize=10,
        leading=12
    )
    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName=MAIN_FONT,
        fontSize=18,
        alignment=1, # По центру
        spaceAfter=20
    )

    # 1. Заголовок
    elements.append(Paragraph(f"Медицинский отчет Stapler", title_style))
    elements.append(Paragraph(f"Пациент: {user_name}", rus_style))
    elements.append(Paragraph(f"Дата формирования: {datetime.now().strftime('%d.%m.%Y %H:%M')}", rus_style))
    elements.append(Spacer(1, 20))

    # 2. Основной блок с анализами
    for record in history:
        elements.append(Paragraph(f"<b>{record.get('date')} — {record.get('title')}</b>", rus_style))
        elements.append(Paragraph(f"Лаборатория: {record.get('laboratory', 'н/д')}", rus_style))
        elements.append(Spacer(1, 10))

        # Таблица показателей
        data = [["Показатель", "Значение", "Норма", "Статус"]]
        indicators = record.get('indicators', [])
        for ind in indicators:
            status_map = {"normal": "Норма", "high": "Выше", "low": "Ниже"}
            data.append([
                ind.get('name', ''),
                f"{ind.get('value', '')} {ind.get('unit', '')}",
                ind.get('norm', ''),
                status_map.get(ind.get('status', ''), ind.get('status', ''))
            ])

        t = Table(data, colWidths=[180, 100, 100, 80])
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), MAIN_FONT),
            ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('ALIGN', (0,0), (-1,-1), 'LEFT'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 20))

    # 3. Блок графиков (если они есть)
    if charts_data:
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("📊 Динамика ключевых показателей:", title_style))
        for chart_buf in charts_data:
            # Превращаем байты графика в объект Image для PDF
            img_data = io.BytesIO(chart_buf.data)
            img = Image(img_data, width=450, height=250)
            elements.append(img)
            elements.append(Spacer(1, 10))

    # Сохраняем
    doc.build(elements)
    buffer.seek(0)
    return buffer