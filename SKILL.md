---
name: ciweimao-novel-fetch
description: 抓取刺猬猫（ciweimao.com）小说章节并整理为 Word 文档。适用于用户要求"爬取/下载/整理刺猬猫某本小说"、给出具体书名（如《大师姐弃疗了》《异种女友养成计划》）并要求前 N 章/全集/整理成 Word/文档/手机可读版本时使用。覆盖找书定位、目录获取、免费章节文本抓取、VIP 图片章节 OCR、文本清洗、Word 生成与格式审计、手机版长图交付的完整流程。
---

# 刺猬猫小说抓取与 Word 整理

把刺猬猫连载小说章节抓取下来，清洗后整理为带封面/目录/页码的 Word 文档，并交付手机版目录长图。

## 主线流程总览

1. 定位书：找到书号 `book_id` 与书详情页
2. 获取目录：抓取目标章节的 `cid` 与标题列表
3. 判定免费/VIP：mip 域探测
4. 抓取正文：免费→脚本；VIP→浏览器取图 + OCR
5. 清洗合并：水印、引号、按目录排序
6. 生成交付：Word（audit 通过）→ 目录长图 → CDN 链接

## Step 1 · 定位书（浏览器，bu）

- 用通用搜索 `site:ciweimao.com <书名>` 找刺猬猫页面；搜索接口与旧 API 已失效，不要浪费时间。
- 站内分类列表分页用 `?page=N`；用 `bu.find("书名")` 命中后取其 `href` 中的书号。
- 打开 `https://wap.ciweimao.com/book/{book_id}` 确认作者、状态（连载/完结）、总章数、章节名格式。

## Step 2 · 获取目录（浏览器，bu）

- 在书页执行 JS 抓取目录链接，得到 `[{cid, title}]`：
  `Array.from(document.querySelectorAll('a')).map(a=>({href:a.href,text:(a.textContent||'').trim()})).filter(x=>/\/chapter\/\d+/.test(x.href))`
- 用 `re.match(r'^(序章|第[一二三四五六七八九十百]+章)', t)` 过滤正文；"作品相关"条目按用户意图取舍。
- 按用户要求的范围截取（如"前50章"= 序章 + 第一章～第四十九章），保存为 cids JSON。

## Step 3 · 判定免费/VIP

对首个目标 cid 请求 `http://mip.ciweimao.com/chapter/{cid}`：

- 返回正文 → 免费章节，走 **路径 A**。
- 返回 401 或提示"需图片化" → VIP 图片章节，走 **路径 B**。

（免费/VIP 判定、水印形态、OCR 结论等细节见 `references/ciweimao-knowledge.md`。）

## 路径 A · 免费章节抓取

```bash
python scripts/fetch_mip_chapters.py --input cids.json --output chapters.json
```

输出 `{cid: {title, paras[]}}`；脚本内置水印/脚注/实体清洗。抓完后抽查 1-2 章段落质量，确认无 `XozRx`、随机 token 行残留。

## 路径 B · VIP 图片章节（登录态浏览器 + OCR）

1. 浏览器（保持登录态）执行：POST `chapter/ajax_get_image_session_code`（form `chapter_id={cid}`）→ 取 `image_code`。
2. GET `chapter/book_chapter_image?chapter_id={cid}&area_width=1500&font_size=40&image_code=...` 取整章 PNG。
3. 下载方式：浏览器内 `fetch → blob → arrayBuffer → 分块 btoa` 写盘，再解码为 `{cid}.png`（`bu.download` 不可用）。
4. 识别：
```bash
python scripts/ocr_vip_images.py --images-dir PNG目录 --output-dir OCR输出 --workers 2
```
   - **16GB 内存机器最多 2 进程**；每章完成即写 jsonl，可随时中断续跑。
   - 完成后按 y 坐标聚类还原段落（gap > 1.8×中位行距断段），并与免费章节按目录合并。

## Step 4 · 清洗与合并

- 引号：OCR 文本的 ASCII `"` 按整章文本流交替替换为中文 `“` `”`（Word audit 硬性要求）。
- 合并：免费 + OCR 结果按目录顺序输出统一 JSON；缺失章节保留标题、paras 为空。

## Step 5 · 生成 Word 并审计

```bash
python scripts/make_word_novel.py --input chapters.json --output 书名.docx \
    --title 书名 --author 作者 --book-id 书号 --subtitle "前50章" --date 2026-09-23
```

- 空 paras 章节写占位"（本章内容整理中，暂未收录，待后续补全）"。
- **必须**用 word skill 的 `scripts/audit.py audit <docx>` 循环审计至退出码 0（重点：中文段落无 ASCII 双引号、字体无 shadowed）。
- 再跑 word skill 的 `scripts/catalogue.py --file <docx>` 更新 TOC 域。

## Step 6 · 手机版长图与交付

```bash
python scripts/make_mobile_img.py --input chapters.json --output 目录长图.png \
    --title 书名 --subtitle "前50章·第一卷" --author 作者 --book-id 书号 --status 连载中
```

- 交付 Word（本地路径）+ 手机版长图（**必须上传 CDN 链接**，用户手机端查看）。
- 交付前用 artifact-preview 渲染验证内容结构。

## 关键约束（勿踩）

- 免费文本统一走 mip 域（无需登录、服务端渲染）；不要尝试文本接口拿 VIP 章节（已证实不可行）。
- OCR 用 PP-OCRv5 server + OpenVINO；v6 small/det mobile/onnxruntime/低分辨率均不可用（丢字或漏检）。
- OCR 并行上限 2 进程（16GB 内存）；不要在脚本里加线程数参数。
- 交付 Word 前必须过 audit；中文段落禁用 ASCII 双引号。
