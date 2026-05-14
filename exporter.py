import os
import io
from datetime import datetime

from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

FONT_PATH = "DejaVuSans.ttf"
if os.path.exists(FONT_PATH):
    pdfmetrics.registerFont(TTFont('DejaVuSans', FONT_PATH))
    MAIN_FONT = 'DejaVuSans'
else:
    MAIN_FONT = 'Helvetica'

def create_medical_report(user_name, history, charts_data=None, ai_summary=None):
    buffer = io.BytesIO()
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

    rus_style = ParagraphStyle(
        'RusStyle',
        fontName=MAIN_FONT,
        fontSize=10,
        leading=12,
        spaceAfter=6
    )
    
    title_style = ParagraphStyle(
        'TitleStyle',
        fontName=MAIN_FONT,
        fontSize=20,
        alignment=1,
        spaceAfter=20
    )

    # --- ТИТУЛЬНЫЙ БЛОК ---
    elements.append(Paragraph("<b>Медицинский отчет Stapler</b>", title_style))
    elements.append(Paragraph(f"<b>Пациент:</b> {user_name}", rus_style))
    elements.append(Paragraph(f"<b>Дата формирования:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}", rus_style))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    elements.append(Spacer(1, 15))

    # --- ОБЩЕЕ РЕЗЮМЕ ОТ ИИ ---
    if ai_summary:
        elements.append(Paragraph("<b>🤖 Общее заключение ассистента Gemini:</b>", rus_style))
        elements.append(Paragraph(f"<i>{ai_summary}</i>", rus_style))
        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        elements.append(Spacer(1, 15))

    # --- ИСТОРИЯ АНАЛИЗОВ ---
    sorted_history = sorted(history, key=lambda x: x.get('date', ''), reverse=True)

    for record in sorted_history:
        elements.append(Paragraph(f"📅 <b>{record.get('date')} — {record.get('title')}</b>", rus_style))
        elements.append(Paragraph(f"🏥 Лаборатория: {record.get('laboratory', 'н/д')}", rus_style))
        elements.append(Spacer(1, 8))

        indicators = record.get('indicators', [])
        
        if not indicators:
            elements.append(Paragraph("<b>Описание / Заключение:</b>", rus_style))
            elements.append(Paragraph(record.get('summary', 'Описание отсутствует'), rus_style))
            elements.append(Spacer(1, 10))
        else:
            data = [[
                Paragraph("<b>Показатель</b>", rus_style), 
                Paragraph("<b>Значение</b>", rus_style), 
                Paragraph("<b>Норма</b>", rus_style), 
                Paragraph("<b>Статус</b>", rus_style)
            ]]

            for ind in indicators:
                status_map = {
                    "normal": "Норма",
                    "attention": "Внимание",
                    "high": "Выше",
                    "low": "Ниже",
                    "pathology": "Патология"
                }
                status_rus = status_map.get(ind.get('status', ''), ind.get('status', ''))
                
                name_p = Paragraph(ind.get('name', 'н/д'), rus_style)
                value_p = Paragraph(f"{ind.get('value', '')} {ind.get('unit', '')}", rus_style)
                norm_p = Paragraph(ind.get('norm', ''), rus_style)
                status_p = Paragraph(status_rus, rus_style)
                
                data.append([name_p, value_p, norm_p, status_p])

            col_widths = [150, 155, 130, 80]
            
            t = Table(data, colWidths=col_widths, hAlign='LEFT')
            t.setStyle(TableStyle([
                ('FONTNAME', (0,0), (-1,-1), MAIN_FONT),
                ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
                ('GRID', (0,0), (-1,-1), 0.5, colors.lightgrey),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('LEFTPADDING', (0,0), (-1,-1), 5),
                ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ]))
            elements.append(t)
            
            if record.get('summary'):
                elements.append(Spacer(1, 8))
                elements.append(Paragraph(f"<i>Комментарий: {record.get('summary')}</i>", rus_style))

        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.lightgrey))
        elements.append(Spacer(1, 15))

    # --- БЛОК ГРАФИКОВ ---
    if charts_data:
        elements.append(PageBreak())
        elements.append(Paragraph("<b>📊 Динамика ключевых показателей</b>", title_style))
        elements.append(Spacer(1, 20))
        for chart_buf in charts_data:
            img_data = io.BytesIO(chart_buf.data)
            img = Image(img_data, width=460, height=260)
            elements.append(img)
            elements.append(Spacer(1, 20))

    doc.build(elements)
    buffer.seek(0)
    return buffer