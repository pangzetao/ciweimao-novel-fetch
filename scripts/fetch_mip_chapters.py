# -*- coding: utf-8 -*-
"""抓取刺猬猫 mip 域免费章节正文并清洗。
用法:
  python fetch_mip_chapters.py --input cids.json --output chapters.json
输入 cids.json 格式: [{"cid": "113580480", "title": "序章：xxx"}, ...]
输出 chapters.json 格式: {"113580480": {"title": "...", "paras": ["...", ...]}, ...}
"""
import io, sys, json, re, time, argparse, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

# 已知水印 token 形态：固定 XozRx / 随机 4-8 位字母数字 / 单数字行
TOKEN_RE = re.compile(r'^[a-zA-Z0-9]{4,8}$')
DIGIT_RE = re.compile(r'^\d{1,3}$')


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def clean_text(html):
    """从 mip 章节页 HTML 提取正文段落并清洗。"""
    m = re.search(r'class="read-bd[^"]*"[^>]*>(.*?)</div>', html, re.S)
    body = m.group(1) if m else html
    # 去掉脚注链接标记 <a>*n*</a> 与 <sup>
    body = re.sub(r'<a[^>]*>\*?\d+\*?</a>', '', body)
    body = re.sub(r'<sup[^>]*>.*?</sup>', '', body, flags=re.S)
    # 去标签
    body = re.sub(r'<[^>]+>', '\n', body)
    # 解实体
    for k, v in (('&nbsp;', ' '), ('&amp;', '&'), ('&lt;', '<'), ('&gt;', '>'),
                 ('&quot;', '"'), ('&#39;', "'")):
        body = body.replace(k, v)
    # 按行分割
    paras = []
    for line in body.split('\n'):
        t = line.strip()
        t = re.sub(r'\s+', ' ', t)
        if not t:
            continue
        # 去水印：已知 token、随机 token 行、单数字行
        if t == 'XozRx' or TOKEN_RE.match(t) or DIGIT_RE.match(t):
            continue
        paras.append(t)
    # 去掉首尾导航行
    nav = {'上一章', '目录', '下一章', '本章结束', '返回目录'}
    while paras and paras[0] in nav:
        paras.pop(0)
    while paras and paras[-1] in nav:
        paras.pop()
    return paras


def get_chapter(cid, title, base):
    url = base.format(cid=cid)
    for attempt in range(3):
        try:
            html = fetch(url)
            return clean_text(html)
        except Exception as e:
            print(f"  retry {cid}: {e}", file=sys.stderr)
            time.sleep(3)
    return []


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--input', required=True, help='cids JSON 文件 [{cid,title}]')
    ap.add_argument('--output', required=True, help='输出 chapters JSON')
    ap.add_argument('--base', default='http://mip.ciweimao.com/chapter/{cid}',
                    help='章节页 URL 模板，默认 mip 域（无需登录）')
    ap.add_argument('--delay', type=float, default=1.0, help='章节间延迟秒数')
    args = ap.parse_args()

    cids = json.load(open(args.input, encoding='utf-8'))
    result = {}
    for i, item in enumerate(cids):
        cid, title = item['cid'], item['title']
        paras = get_chapter(cid, title, args.base)
        result[cid] = {'title': title, 'paras': paras}
        print(f"[{i+1}/{len(cids)}] {title} -> {len(paras)} 段")
        time.sleep(args.delay)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=1)
    print(f"完成 {len(result)} 章 -> {args.output}")


if __name__ == '__main__':
    main()
