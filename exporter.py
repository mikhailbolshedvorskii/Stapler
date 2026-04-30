import os
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# 1. Регистрация шрифта (DejaVuSans поддерживает кириллицу)
FONT_PATH = "DejaVuSans.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_PATH))
    MAIN_FONT = 'DejaVuSans'
    BOLD_FONT = 'DejaVuSans' # Если есть DejaVuSans-Bold.ttf, лучше использовать его
else:
    # Если шрифта нет, PDF будет на английском (русский пропадет)
    MAIN_FONT = 'Helvetica'
    BOLD_FONT = 'Helvetica-Bold'

def create_medical_report(user_name, history, charts_data=None):
    """
    Создает профессиональный PDF-отчет со структурированными таблицами и графиками.
    """
    buffer = io.BytesIO()
    # Настройка документа с полями
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=40, 
        leftMargin=40, 
        topMargin=40, 
        bottomMargin=40
    )
    
    elements = []
    styles = getSampleStyleSheet()

    # Кастомные стили для русского языка и верстки
    rus_style = ParagraphStyle(
        'RusStyle',
        fontName=MAIN_FONT,
        fontSize=10,
        leading=12,
        spaceAfter=6
    )
    
    header_style = ParagraphStyle(
        'HeaderStyle',
        fontName=MAIN_FONT,
        fontSize=14,
        leading=18,
        spaceBefore=15,
        spaceAfter=10
    )

    title_style = ParagraphStyle(
        'TitleStyle',
        fontName=MAIN_FONT,
        fontSize=20,
        alignment=1, # По центру
        spaceAfter=30
    )

    # --- ТИТУЛЬНЫЙ БЛОК ---
    elements.append(Paragraph("<b>Медицинский отчет Stapler</b>", title_style))
    elements.append(Paragraph(f"<b>Пациент:</b> {user_name}", rus_style))
    elements.append(Paragraph(f"<b>Дата формирования:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}", rus_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width=1, color=colors.grey))
    elements.append(Spacer(1, 20))

    # --- ОСНОВНОЙ БЛОК: ТАБЛИЦЫ АНАЛИЗОВ ---
    # Сортируем историю по дате (от новых к старым)
    sorted_history = sorted(history, key=lambda x: x.get('date', ''), reverse=True)

    for record in sorted_history:
        # 1. Заголовок и лаборатория (уже есть в коде)
        elements.append(Paragraph(f"📅 {record.get('date')} — {record.get('title')}", header_style))
        elements.append(Paragraph(f"🏥 Лаборатория: {record.get('laboratory', 'н/д')}", rus_style))
        elements.append(Spacer(1, 10))

        # --- НОВАЯ ЛОГИКА ТУТ ---
        indicators = record.get('indicators', [])
        
        # Если это текстовый отчет (рентген) и список показателей пуст
        if not indicators:
            elements.append(Paragraph("<b>Описание / Заключение:</b>", rus_style))
            # Берем текст из поля summary
            summary_text = record.get('summary', 'Описание отсутствует в базе.')
            elements.append(Paragraph(summary_text, rus_style))
            elements.append(Spacer(1, 15))
        else:
            # Если показатели есть, рисуем таблицу (твой текущий код)
            data = [[
                Paragraph("<b>Показатель</b>", rus_style), 
                Paragraph("<b>Значение</b>", rus_style), 
                Paragraph("<b>Норма</b>", rus_style), 
                Paragraph("<b>Статус</b>", rus_style)
            ]]

            for ind in indicators:
                status_map = {"normal": "Норма", "high": "Выше", "low": "Ниже"}
                status_rus = status_map.get(ind.get('status', ''), ind.get('status', ''))
                name_p = Paragraph(ind.get('name', 'Неизвестно'), rus_style)
                
                data.append([
                    name_p,
                    f"{ind.get('value', '')} {ind.get('unit', '')}",
                    ind.get('norm', ''),
                    status_rus
                ])

            col_widths = [265, 80, 90, 80]
            t = Table(data, colWidths=col_widths, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), MAIN_FONT),
                ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 6),
                ('RIGHTPADDING', (0,0), (-1,-1), 6),
                ('BOTTOMPADDING', (0,0), (-1,-1), 6),
                ('TOPPADDING', (0,0), (-1,-1), 6),
            ]))
            elements.append(t)
            elements.append(Spacer(1, 20))
            
            # В конце табличного анализа тоже добавим краткое резюме, если оно есть
            if record.get('summary'):
                elements.append(Paragraph(f"<i>Комментарий: {record.get('summary')}</i>", rus_style))
                elements.append(Spacer(1, 15))

        # Линия-разделитель между разными анализами для "воздуха"
        elements.append(HrLine(width=0.5, color=colors.lightgrey))
        elements.append(Spacer(1, 20))

    # --- БЛОК ГРАФИКОВ ---
    if charts_data:
        # Переход на новую страницу для графиков
        from reportlab.platypus import PageBreak
        elements.append(PageBreak())
        elements.append(Paragraph("📊 Динамика ключевых показателей", title_style))
        elements.append(Spacer(1, 20))

        for chart_buf in charts_data:
            # Превращаем BufferedInputFile (байты) в изображение
            img_data = io.BytesIO(chart_buf.data)
            img = Image(img_data, width=460, height=260)
            elements.append(img)
            elements.append(Spacer(1, 30))

    # Генерация документа
    doc.build(elements)
    buffer.seek(0)
    return buffer