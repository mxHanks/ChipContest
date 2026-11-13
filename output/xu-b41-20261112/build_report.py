#!/usr/bin/env python3
"""Render the reviewed Markdown source as an A4 engineering report."""
import html
import json
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Flowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = Path(__file__).with_name('B41-作品设计报告.md')
DATA = json.loads(SOURCE.with_name('report-data.json').read_text())
OUT = ROOT / 'output/pdf/B41-作品设计报告.pdf'
OUT.parent.mkdir(parents=True, exist_ok=True)
FONT = 'B41Unicode'
pdfmetrics.registerFont(TTFont(FONT, '/System/Library/Fonts/Supplemental/Arial Unicode.ttf'))
BLUE = colors.HexColor('#154C7E')
INK = colors.HexColor('#203246')
MUTED = colors.HexColor('#617285')
LIGHT = colors.HexColor('#EAF1F7')
RULE = colors.HexColor('#CCD9E5')
WIDTH = A4[0] - 88
DRAFT = DATA['status'] != 'FINAL_REVIEWED'

STYLES = {
    'title': ParagraphStyle('title', fontName=FONT, fontSize=25, leading=33, textColor=BLUE,
                            spaceAfter=13, wordWrap='CJK'),
    'h2': ParagraphStyle('h2', fontName=FONT, fontSize=14.5, leading=21, textColor=BLUE,
                         spaceBefore=18, spaceAfter=8, keepWithNext=True, wordWrap='CJK'),
    'body': ParagraphStyle('body', fontName=FONT, fontSize=10.2, leading=16.4,
                           textColor=INK, spaceAfter=8.5, wordWrap='CJK'),
    'small': ParagraphStyle('small', fontName=FONT, fontSize=8.5, leading=13,
                            textColor=MUTED, spaceAfter=6, wordWrap='CJK'),
    'cell': ParagraphStyle('cell', fontName=FONT, fontSize=8.4, leading=12.8,
                           textColor=INK, wordWrap='CJK'),
    'code': ParagraphStyle('code', fontName=FONT, fontSize=8.5, leading=14,
                           textColor=INK, backColor=LIGHT, borderPadding=9,
                           spaceAfter=10, wordWrap='CJK'),
}


def rich(s):
    s = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', s)
    s = s.replace('`', '')
    return html.escape(s).replace('**', '')


def paragraph(s, style='body'):
    return Paragraph(rich(s), STYLES[style])


class Architecture(Flowable):
    def __init__(self):
        super().__init__()
        self.width, self.height = WIDTH, 216

    def draw(self):
        c = self.canv
        c.setFillColor(colors.HexColor('#F5F8FB'))
        c.roundRect(0, 0, self.width, self.height, 8, stroke=0, fill=1)

        def box(x, y, w, h, title, detail, fill=colors.white):
            c.setFillColor(fill)
            c.setStrokeColor(RULE)
            c.roundRect(x, y, w, h, 5, stroke=1, fill=1)
            c.setFont(FONT, 10)
            c.setFillColor(BLUE)
            c.drawCentredString(x+w/2, y+h-17, title)
            c.setFont(FONT, 8)
            c.setFillColor(MUTED)
            c.drawCentredString(x+w/2, y+10, detail)

        def arrow(points, both=False):
            c.setStrokeColor(BLUE)
            c.setLineWidth(1.1)
            for a, b in zip(points, points[1:]):
                c.line(a[0], a[1], b[0], b[1])
            import math
            def head(a, b):
                ang = math.atan2(b[1]-a[1], b[0]-a[0])
                for delta in [-0.47, 0.47]:
                    c.line(b[0], b[1], b[0]-5*math.cos(ang+delta), b[1]-5*math.sin(ang+delta))
            head(points[-2], points[-1])
            if both:
                head(points[1], points[0])

        box(14, 154, 110, 45, 'E203 驱动', 'MMIO / 有限等待')
        box(177, 154, 160, 45, '共享 SRAM 512 KiB', '复用存储 / 完整 SoC 计功耗')
        box(14, 78, 110, 48, 'DMA 与寄存器', '请求 / 响应退休')
        box(186, 96, 127, 43, '权重与偏置 SRAM', '16 + 1 个内部宏')
        box(186, 42, 127, 43, '两组 X 行缓冲', '2 × 8 × 64')
        box(360, 76, 127, 50, '64 PE 计算核心', '8 引擎 × 8 PE / signed41')
        box(350, 12, 137, 43, '两槽结果 FIFO', '行 / 通道组 / 累加结果')
        box(14, 12, 150, 43, 'RNE 与 64 位结果写回', 'Y32 / 最后响应退休后完成')
        arrow([(69,154),(69,126)])
        arrow([(177,176),(148,176),(148,102),(124,102)], both=True)
        arrow([(124,113),(158,113),(158,118),(186,118)])
        arrow([(124,92),(158,92),(158,64),(186,64)])
        arrow([(313,118),(337,118),(337,110),(360,110)])
        arrow([(313,64),(337,64),(337,91),(360,91)])
        arrow([(423,76),(423,55)])
        arrow([(350,34),(164,34)])
        arrow([(69,55),(69,78)])


def markdown_table(lines):
    rows = [[v.strip() for v in line.strip().strip('|').split('|')] for line in lines]
    rows = [row for row in rows if not all(re.fullmatch(r'[:\- ]+', v or '-') for v in row)]
    n = len(rows[0])
    widths = [132, WIDTH-132] if n == 2 else [105]+[(WIDTH-105)/(n-1)]*(n-1)
    cells = [[paragraph(v, 'cell') for v in row] for row in rows]
    t = Table(cells, colWidths=widths, repeatRows=1, hAlign='LEFT')
    t.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,0),LIGHT),
        ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#F8FAFC')]),
        ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),
        ('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),
        ('LINEBELOW',(0,0),(-1,0),0.7,RULE),
        ('LINEBELOW',(0,-1),(-1,-1),0.5,RULE),
    ]))
    return [t, Spacer(1,9)]


def page_frame(c, doc):
    c.saveState()
    w, h = A4
    c.setFont(FONT, 8)
    c.setFillColor(MUTED)
    c.drawString(44, h-29, 'B41  |  E203 集成与工程验证')
    c.drawRightString(w-44, h-29, '2026-11-12 / 13')
    c.setStrokeColor(RULE)
    c.line(44,h-37,w-44,h-37)
    c.line(44,37,w-44,37)
    c.drawString(44,24,'工程审阅稿 · 未完成测量见正文' if DRAFT else '版本与原件 SHA 绑定见随包清单')
    c.drawRightString(w-44,24,f'{doc.page}')
    c.restoreState()


def build():
    a = SOURCE.read_text().splitlines()
    story = []
    i = 0
    while i < len(a):
        s = a[i].strip()
        if not s:
            i += 1
            continue
        if s.startswith('# '):
            story.extend([Spacer(1,11),paragraph('64 PE · 41 位累加 · DMA64','small'),
                          paragraph(s[2:],'title')])
            i += 1
        elif s.startswith('## '):
            story.append(paragraph(s[3:],'h2'))
            i += 1
        elif s.startswith('|'):
            lines = []
            while i < len(a) and a[i].lstrip().startswith('|'):
                lines.append(a[i]); i += 1
            story.extend(markdown_table(lines))
        elif s.startswith('```'):
            kind = s[3:]
            lines = []
            i += 1
            while i < len(a) and not a[i].strip().startswith('```'):
                lines.append(a[i]); i += 1
            i += 1
            if kind == 'mermaid':
                story.extend([Architecture(),Spacer(1,10)])
            else:
                story.append(Paragraph('<br/>'.join(rich(v) for v in lines), STYLES['code']))
        else:
            lines = [s]
            i += 1
            while i < len(a) and a[i].strip() and not a[i].lstrip().startswith(('#','|','```')):
                lines.append(a[i].strip()); i += 1
            story.append(paragraph(' '.join(lines)))
    doc = SimpleDocTemplate(str(OUT),pagesize=A4,rightMargin=44,leftMargin=44,
                            topMargin=54,bottomMargin=52,title='B41 作品设计报告',
                            author='B41 项目组',subject='同版本 RTL、综合与门级证据审阅')
    doc.build(story,onFirstPage=page_frame,onLaterPages=page_frame)
    print(OUT)


if __name__ == '__main__':
    build()
