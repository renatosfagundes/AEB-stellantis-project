import sys
import pypandoc
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, Cm, RGBColor

sys.stdout.reconfigure(encoding="utf-8")
base = r"C:\Users\rfagu\Estudo\dinamica_dt_aeb\artigo"
src = base + "\\" + (sys.argv[1] if len(sys.argv) > 1 else "rascunho_orientador.md")
dst = base + "\\" + (sys.argv[2] if len(sys.argv) > 2 else "Artigo_AEB_Rascunho_Orientador_30-10.docx")
pypandoc.convert_file(src, "docx", outputfile=dst, extra_args=["-f", "markdown+pipe_tables+link_attributes"])

doc = Document(dst)
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21), Cm(29.7)
for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
    setattr(sec, m, Cm(2.5))
for nome in ("Normal", "Body Text", "First Paragraph", "Compact"):
    try:
        st = doc.styles[nome]
        st.font.name, st.font.size = "Times New Roman", Pt(11)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), "Times New Roman")
        st.paragraph_format.space_after = Pt(6)
        st.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    except KeyError:
        pass
for nome, tam in (("Heading 1", 13), ("Heading 2", 11.5)):
    st = doc.styles[nome]
    st.font.name, st.font.size, st.font.bold, st.font.color.rgb = "Times New Roman", Pt(tam), True, RGBColor(0, 0, 0)
    rf = st.element.rPr.rFonts
    for a in ("w:asciiTheme", "w:hAnsiTheme", "w:eastAsiaTheme", "w:cstheme"):
        rf.attrib.pop(qn(a), None)
# título, autores e afiliação centralizados
for p in doc.paragraphs[:3]:
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER

largura = Cm(16)
for t in doc.tables:
    t.style = None
    tblPr = t._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for b in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{b}")
        e.set(qn("w:val"), "single"); e.set(qn("w:sz"), "4"); e.set(qn("w:color"), "808080")
        borders.append(e)
    tblPr.append(borders)
    for i, row in enumerate(t.rows):
        for cell in row.cells:
            for p in cell.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER if i == 0 else WD_ALIGN_PARAGRAPH.LEFT
                for r in p.runs:
                    r.font.size = Pt(8.5)
                    r.font.name = "Times New Roman"
                    if i == 0:
                        r.font.bold = True
                        r.font.color.rgb = RGBColor(255, 255, 255)
            if i == 0:
                tcPr = cell._tc.get_or_add_tcPr()
                shd = OxmlElement("w:shd"); shd.set(qn("w:val"), "clear"); shd.set(qn("w:fill"), "1F3864")
                tcPr.append(shd)
# legendas e parágrafos de figura centralizados; referências compactas (9 pt)
em_refs = False
for p in doc.paragraphs:
    tx = p.text.strip()
    if tx.startswith(("Figura ", "Tabela ")) and len(tx) < 260:
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        for r in p.runs:
            r.font.size = Pt(9)
        if tx.startswith("Tabela "):
            p.paragraph_format.keep_with_next = True
    if p._p.xpath(".//w:drawing"):
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
    if tx.upper().startswith("REFERÊNCIAS") and p.style.name.startswith("Heading"):
        em_refs = True
        p.paragraph_format.keep_with_next = False
        p.paragraph_format.space_before = Pt(12)
        continue
    if em_refs and tx.startswith("["):
        p.paragraph_format.space_after = Pt(2)
        p.paragraph_format.left_indent = Cm(0.6)
        p.paragraph_format.first_line_indent = Cm(-0.6)
        for r in p.runs:
            r.font.size = Pt(9)
    elif not tx.startswith(("Figura ", "Tabela ")) and p.style.name in ("Normal", "Body Text", "First Paragraph", "Compact"):
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.space_before = Pt(0)
    if em_refs and tx.startswith("["):
        p.paragraph_format.space_before = Pt(0)
from docx.text.paragraph import Paragraph
for t in doc.tables:
    nxt = t._tbl.getnext()
    if nxt is not None and nxt.tag.endswith("}p"):
        Paragraph(nxt, t._parent).paragraph_format.space_before = Pt(8)
doc.save(dst)
print("ok", dst)
