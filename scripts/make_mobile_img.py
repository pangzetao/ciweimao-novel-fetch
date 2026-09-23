# -*- coding: utf-8 -*-
"""生成手机版章节目录长图（PNG，两列目录）。
用法:
  python make_mobile_img.py --input chapters.json --output out.png \
      --title 书名 --subtitle 范围说明 --author 作者 --book-id 书号
依赖: Pillow；Windows 字体自动探测（微软雅黑/黑体/宋体）
"""
import io, sys, json, argparse
from PIL import Image, ImageDraw, ImageFont

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def get_font(size, bold=False):
    candidates = []
    if bold:
        candidates = [r"C:\Windows\Fonts\msyhbd.ttc", r"C:\Windows\Fonts\Dengb.ttf"]
    candidates += [r"C:\Windows\Fonts\msyh.ttc", r"C:\Windows\Fonts\simhei.ttf",
                   r"C:\Windows\Fonts\simsun.ttc"]
    for c in candidates:
        try:
            return ImageFont.truetype(c, size)
        except Exception:
            continue
    return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='chapters JSON')
    ap.add_argument('--output', required=True, help='输出 PNG 路径')
    ap.add_argument('--title', required=True, help='书名')
    ap.add_argument('--subtitle', default='', help='副标题/范围说明')
    ap.add_argument('--author', default='', help='作者')
    ap.add_argument('--book-id', default='', help='书号')
    ap.add_argument('--status', default='', help='连载/完结状态')
    ap.add_argument('--note', default='', help='额外说明（如已收录章数）')
    args = ap.parse_args()

    data = json.load(open(args.input, encoding='utf-8'))
    items = list(data.items())

    W = 750
    MARGIN = 40
    COL_GAP = 20
    COL_W = (W - MARGIN * 2 - COL_GAP) // 2
    LINE_H = 42
    rows = (len(items) + 1) // 2
    H = 140 + 240 + 40 + rows * LINE_H + 80

    img = Image.new('RGB', (W, H), (252, 250, 246))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 140], fill=(44, 62, 80))
    f_title = get_font(42, bold=True)
    f_sub = get_font(24)
    tw = draw.textlength(args.title, font=f_title)
    draw.text(((W - tw) / 2, 25), args.title, font=f_title, fill=(255, 255, 255))
    if args.subtitle:
        sw = draw.textlength(args.subtitle, font=f_sub)
        draw.text(((W - sw) / 2, 92), args.subtitle, font=f_sub, fill=(200, 220, 240))

    f_info = get_font(22)
    y = 160
    info_parts = [x for x in [f'作者：{args.author}' if args.author else '',
                              f'书号：{args.book_id}' if args.book_id else '',
                              args.status] if x]
    if info_parts:
        line = ' ｜ '.join(info_parts)
        lw = draw.textlength(line, font=f_info)
        draw.text(((W - lw) / 2, y), line, font=f_info, fill=(90, 90, 90))
        y += 34
    if args.note:
        lw = draw.textlength(args.note, font=f_info)
        draw.text(((W - lw) / 2, y), args.note, font=f_info, fill=(90, 90, 90))
        y += 34

    total_chars = sum(sum(len(p) for p in ch['paras']) for _, ch in items)
    line = f"全文约 {total_chars/10000:.1f} 万字"
    lw = draw.textlength(line, font=f_info)
    draw.text(((W - lw) / 2, y), line, font=f_info, fill=(150, 90, 60))
    y += 40

    draw.line([(MARGIN, y), (W - MARGIN, y)], fill=(200, 195, 185), width=2)
    y += 24

    f_ch = get_font(22)
    f_num = get_font(20)
    start_y = y
    for i, (cid, ch) in enumerate(items):
        col = i % 2
        row = i // 2
        x = MARGIN + col * (COL_W + COL_GAP)
        yy = start_y + row * LINE_H
        title = ch['title'].strip()
        num_str = f"{i+1:02d}"
        if row % 2 == 0:
            draw.rectangle([MARGIN - 10, yy - 4, W - MARGIN + 10, yy + LINE_H - 6],
                           fill=(244, 241, 236))
        draw.text((x, yy), num_str, font=f_num, fill=(180, 120, 60))
        if len(title) > 15:
            title = title[:15] + "…"
        draw.text((x + 50, yy), title, font=f_ch, fill=(50, 50, 50))

    img.save(args.output, 'PNG')
    print(f"已生成: {args.output} 尺寸: {W}x{H}")


if __name__ == '__main__':
    main()
