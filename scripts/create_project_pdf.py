"""Create a portable report from the authored project explanation content."""
from pathlib import Path
from xml.sax.saxutils import escape

from docx import Document
from docx.text.paragraph import Paragraph as WordParagraph
from docx.table import Table as WordTable
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak, Image
from pypdf import PdfReader
from pdf2image import convert_from_path

root = Path(__file__).resolve().parents[1]
qa = root / 'artifacts/project-document/pdf-render'
qa.mkdir(parents=True, exist_ok=True)
out = root / 'output/pdf'
out.mkdir(parents=True, exist_ok=True)
for name, filename in [('Calibri','calibri.ttf'),('CalibriBold','calibrib.ttf'),('CalibriItalic','calibrii.ttf'),('Consolas','consola.ttf')]:
    pdfmetrics.registerFont(TTFont(name, 'C:/Windows/Fonts/' + filename))
pdfmetrics.registerFontFamily('Calibri',normal='Calibri',bold='CalibriBold',italic='CalibriItalic',boldItalic='CalibriBold')
body = ParagraphStyle('Body',fontName='Calibri',fontSize=11,leading=12.8,spaceAfter=8)
title = ParagraphStyle('Title',parent=body,fontSize=27,leading=30,spaceAfter=14,keepWithNext=True)
sub = ParagraphStyle('Subtitle',parent=body,fontSize=12,leading=15,spaceAfter=12,keepWithNext=True)
h1 = ParagraphStyle('Heading1',parent=body,fontName='CalibriBold',fontSize=20,leading=23,spaceAfter=12,keepWithNext=True)
h2 = ParagraphStyle('Heading2',parent=body,fontName='CalibriBold',fontSize=12.5,leading=15,spaceBefore=8,spaceAfter=7,keepWithNext=True)
caption = ParagraphStyle('Caption',parent=body,fontSize=9,leading=11,spaceAfter=10)
cell = ParagraphStyle('Cell',parent=body,fontSize=9.3,leading=10.8,spaceAfter=0)
head = ParagraphStyle('TableHead',parent=cell,fontName='CalibriBold',textColor=colors.white)
mono = ParagraphStyle('Code',parent=body,fontName='Consolas',fontSize=9,leading=11,spaceAfter=10)


def text(p):
    result = ''
    for run in p.runs:
        value=escape(run.text).replace('\n','<br/>')
        if run.bold:
            value='<b>'+value+'</b>'
        result+=value
    return result


story=[]
d=Document(root/'docs/Self_Correcting_Data_Pipeline_Project_Explanation.docx')
for item in d.element.body:
    if item.tag.endswith('}p'):
        wp=WordParagraph(item,d)
        if any(br.get('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}type')=='page' for br in item.iter('{http://schemas.openxmlformats.org/wordprocessingml/2006/main}br')):
            story.append(PageBreak())
            continue
        if list(item.iter('{http://schemas.openxmlformats.org/drawingml/2006/main}blip')):
            story.append(Image(str(root/'artifacts/project-document/architecture.png'),width=482,height=140.6))
            continue
        if not wp.text:
            continue
        style={'Title':title,'Subtitle':sub,'Heading 1':h1,'Heading 2':h2,'Caption':caption}.get(wp.style.name,body)
        if wp.runs and wp.runs[0].font.name=='Consolas':
            style=mono
        story.append(Paragraph(text(wp),style))
    elif item.tag.endswith('}tbl'):
        wt=WordTable(item,d)
        data=[[Paragraph(escape(c.text),head if i==0 else cell) for c in row.cells] for i,row in enumerate(wt.rows)]
        widths=[c.width.pt for c in wt.columns]
        t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
        t.setStyle(TableStyle([
            ('BACKGROUND',(0,0),(-1,0),colors.HexColor('#24445B')),
            ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#F1F5F7'),colors.white]),
            ('GRID',(0,0),(-1,-1),.4,colors.HexColor('#D9D9D9')),
            ('VALIGN',(0,0),(-1,-1),'MIDDLE'),
            ('LEFTPADDING',(0,0),(-1,-1),5),('RIGHTPADDING',(0,0),(-1,-1),5),
            ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
        ]))
        story.extend([t,Spacer(1,8)])


def furniture(canvas, doc):
    canvas.saveState()
    canvas.setFillColor(colors.black)
    canvas.setFont('Calibri',8)
    canvas.drawString(54,A4[1]-27,'SELF CORRECTING DATA PIPELINE   |   PROJECT EXPLANATION')
    canvas.drawRightString(A4[0]-54,25,f'Project version 1.0.0  •  {doc.page}')
    canvas.restoreState()


path=out/'Self_Correcting_Data_Pipeline_Project_Explanation.pdf'
SimpleDocTemplate(str(path),pagesize=A4,rightMargin=54,leftMargin=54,topMargin=52,bottomMargin=52,
                  title='Self Correcting Data Pipeline Project Explanation',author='').build(story,onFirstPage=furniture,onLaterPages=furniture)
reader=PdfReader(path)
print('PDF pages:',len(reader.pages))
for i,p in enumerate(reader.pages,1):
    txt=p.extract_text()
    print(i,len(txt.split()),txt.splitlines()[1:3])
images=convert_from_path(str(path),dpi=130,poppler_path=r'C:\Users\tanis\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\poppler\Library\bin')
for i,im in enumerate(images,1):
    im.save(qa/f'page-{i}.png')
print(path)
