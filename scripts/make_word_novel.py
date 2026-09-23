# -*- coding: utf-8 -*-
"""把章节 JSON 整理为 Word 文档（封面 + TOC 域 + 章节标题 + 正文 + 页脚页码）。
用法:
  python make_word_novel.py --input chapters.json --output 书名.docx \
      --title 书名 --author 作者 --book-id 书号 --subtitle 卷/范围说明
依赖: python-docx
"""
import io, sys, json, argparse
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def set_font(style, cn_font, en_font, size, bold=False, color=RGBColor(0, 0, 0)):
    """显式设置字体；删除 theme 属性，避免 audit E_FONT_EXPLICIT_VALUE_SHADOWED。"""
    style.font.name = en_font
    style.font.size = Pt(size)
    style.font.bold = bold
    style.font.color.rgb = color
    rpr = style.element.get_or_add_rPr()
    rfonts = rpr.find(qn('w:rFonts'))
    if rfonts is None:
        rfonts = OxmlElement('w:rFonts')
        rpr.append(rfonts)
    rfonts.set(qn('w:eastAsia'), cn_font)
    rfonts.set(qn('w:ascii'), en_font)
    rfonts.set(qn('w:hAnsi'), en_font)
    for attr in ('w:asciiTheme', 'w:eastAsiaTheme', 'w:hAnsiTheme', 'w:cstheme'):
        if rfonts.get(qn(attr)) is not None:
            del rfonts.attrib[qn(attr)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='chapters JSON')
    ap.add_argument('--output', required=True, help='输出 .docx 路径')
    ap.add_argument('--title', required=True, help='书名')
    ap.add_argument('--author', default='', help='作者')
    ap.add_argument('--book-id', default='', help='书号')
    ap.add_argument('--subtitle', default='', help='副标题（如“前50章”）')
    ap.add_argument('--date', default='', help='整理日期，默认今天')
    args = ap.parse_args()
    if not args.date:
        import datetime
        args.date = datetime.date.today().isoformat()

    data = json.load(open(args.input, encoding='utf-8'))
    total_chars = sum(len(''.join(ch['paras'])) for ch in data.values())
    print(f"章节数: {len(data)}, 总字数: {total_chars}")

    doc = Document()
    for sec in doc.sections:
        sec.page_width = Cm(21.0)
        sec.page_height = Cm(29.7)
        sec.top_margin = Cm(2.5)
        sec.bottom_margin = Cm(2.5)
        sec.left_margin = Cm(2.5)
        sec.right_margin = Cm(2.5)

    st_title = doc.styles['Title']
    set_font(st_title, '黑体', 'Times New Roman', 18, bold=True)
    st_title.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st_title.paragraph_format.space_after = Pt(18)

    st_sub = doc.styles['Subtitle']
    set_font(st_sub, '楷体', 'Times New Roman', 12, bold=False)
    st_sub.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    st_sub.paragraph_format.space_after = Pt(12)

    st_h1 = doc.styles['Heading 1']
    set_font(st_h1, '黑体', 'Times New Roman', 16, bold=True)
    st_h1.paragraph_format.space_before = Pt(14)
    st_h1.paragraph_format.space_after = Pt(6)
    st_h1.paragraph_format.keep_with_next = True

    st_normal = doc.styles['Normal']
    set_font(st_normal, '宋体', 'Times New Roman', 12, bold=False)
    st_normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    st_normal.paragraph_format.line_spacing = 1.5
    st_normal.paragraph_format.space_before = Pt(0)
    st_normal.paragraph_format.space_after = Pt(0)
    st_normal.paragraph_format.first_line_indent = Pt(24)

    # 封面
    p = doc.add_paragraph(args.title, style='Title')
    if args.subtitle:
        doc.add_paragraph(args.subtitle, style='Subtitle')
    info = ' ｜ '.join(x for x in [f'作者：{args.author}' if args.author else '',
                                   f'刺猬猫书号：{args.book_id}' if args.book_id else '',
                                   '整理日期：' + args.date] if x)
    if info:
        doc.add_paragraph(info, style='Subtitle')

    # 目录页
    doc.add_page_break()
    toc_para = doc.add_paragraph()
    run = toc_para.add_run()
    f1 = OxmlElement('w:fldChar'); f1.set(qn('w:fldCharType'), 'begin')
    it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve')
    it.text = 'TOC \\o "1-2" \\h \\z \\u'
    f2 = OxmlElement('w:fldChar'); f2.set(qn('w:fldCharType'), 'separate')
    tt = OxmlElement('w:t'); tt.text = '（目录将在打开文档后自动更新）'
    f3 = OxmlElement('w:fldChar'); f3.set(qn('w:fldCharType'), 'end')
    run._r.append(f1); run._r.append(it); run._r.append(f2); run._r.append(tt); run._r.append(f3)
    doc.add_page_break()

    # 正文
    for cid, ch in data.items():
        title = ch['title'].strip()
        doc.add_heading(title, level=1)
        for para_text in ch['paras']:
            doc.add_paragraph(para_text, style='Normal')

    # 页脚页码
    sec = doc.sections[0]
    footer = sec.footer
    footer.is_linked_to_previous = False
    fp = footer.paragraphs[0] if footer.paragraphs else footer.add_paragraph()
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = fp.add_run()
    f1 = OxmlElement('w:fldChar'); f1.set(qn('w:fldCharType'), 'begin')
    it = OxmlElement('w:instrText'); it.set(qn('xml:space'), 'preserve')
    it.text = 'PAGE'
    f2 = OxmlElement('w:fldChar'); f2.set(qn('w:fldCharType'), 'end')
    run._r.append(f1); run._r.append(it); run._r.append(f2)

    doc.save(args.output)
    print(f"完成 {len(data)} 章 -> {args.output}")


if __name__ == '__main__':
    main()
