# 刺猬猫（ciweimao.com）站点知识、坑与实战结论

本文件汇总从实战中验证过的刺猬猫抓取知识。SKILL.md 为主线流程，本文件供遇到分支场景时按需查阅。

## 站点结构

- 书详情页：`https://wap.ciweimao.com/book/{book_id}`（wap 域，浏览器可读）
- 章节阅读页：`https://www.ciweimao.com/chapter/{cid}` 与 `https://wap.ciweimao.com/chapter/{cid}`
- **mip 服务端渲染域：`http://mip.ciweimao.com/chapter/{cid}`** —— 免费章节无需登录即可直接 HTTP 抓取正文 HTML
- 书列表/分类：`https://wap.ciweimao.com/book_list/1/{tag}/`；列表分页用 `?page=2`（不是路径 /2）

## 获取书号与章节目录（浏览器，建议 bu）

1. 站内搜索页 `www.ciweimao.com/search-result?...` 与旧 API `get-search-book-list/...` 已失效（404/被吞）。
2. 推荐：通用搜索 `site:ciweimao.com <书名>` 找分类列表页 → 列表页按 `?page=N` 翻页 → `bu.find("书名")` 拿书页链接（`/book/{id}`）。
3. 打开书页后，目录区所有章节链接为 `a[href*="/chapter/{cid}"]`，文本即章节标题。用 `bu.js` 一次性抓取前 N 章：
   `Array.from(document.querySelectorAll('a')).map(a=>({href:a.href,text:(a.textContent||'').trim()})).filter(x=>/\/chapter\/\d+/.test(x.href))`
4. 用 `re.match(r'^(序章|第[一二三四五六七八九十百]+章)', t)` 过滤出正文章节；"作品相关"（简介、设定、上架公告）按需决定是否收录。

## 免费 / VIP 判定（重要分支）

- 对目标 cid 请求 `http://mip.ciweimao.com/chapter/{cid}`：
  - **HTTP 200 + 正文容器** → 免费，直接抓（脚本 `fetch_mip_chapters.py`）。
  - **HTTP 401 / 400002 提示"此章节需图片化"** → VIP 图片化章节，文本接口无论登录态都不可用，走图片 + OCR 流程（见下）。
- 连载书通常前几十章免费；上架后章节图片化。

## VIP 章节图片流程（登录态浏览器）

1. POST `https://www.ciweimao.com/chapter/ajax_get_image_session_code`（form: `chapter_id={cid}`，浏览器同源、带登录 Cookie）→ 返回 `image_code`。
2. GET `https://www.ciweimao.com/chapter/book_chapter_image?chapter_id={cid}&area_width=1500&font_size=40&image_code={code}` → 整章 PNG。无登录态只有约 10KB 预览图（不可用）。
3. 下载：`bu.download` 整体不可用。用浏览器内 `fetch → blob → arrayBuffer → 分块 btoa → 写盘 txt`（每行 `cid\tbase64`）再解码为 PNG。1500px 出图质量足够 OCR（750px 漏检严重）。
4. 识别用 `scripts/ocr_vip_images.py`（rapidocr PP-OCRv5 server + OpenVINO）。

## OCR 关键结论（rapidocr 3.9.x）

- **最优组合**：Det/Rec 均 `ModelType.SERVER + OCRVersion.PPOCRV5 + EngineType.OPENVINO`；
  `Global.max_side_len=4000`、`Det.limit_side_len=2500 / limit_type=max`；**不设 inference_num_threads**（保持默认，单线程反而更快）。
- **内存硬约束**：16GB 整机最多 2 个 OCR 进程并行（约 4GB/进程）；3/4/6 进程会内存耗尽崩溃。det server 推理是单线程瓶颈，多进程抢线程更慢。
- **增量写盘**：每章完成即追加 jsonl + flush，崩溃不丢，重启自动跳过已完成 cid。
- **切块**：整章图（约 6600px 高）按 1100px 高度横切逐块识别，行坐标 `lines:[{y,t}]` 用于后续按 y 聚类还原段落。
- **不可用的替代**：PP-OCRv6 small（快 3.6 倍但丢字 39%）、det mobile（漏检）、onnxruntime（慢 ~4 倍）、Windows.Media.Ocr（差）、750px 输入（漏检）。

## 文本清洗规则（免费 mip 与 OCR 均适用）

- 水印 token：`XozRx` 及随机 4-8 位字母数字行（如 `17tm5b`）、单数字行（1-3 位）——删除。
- mip HTML：脚注链接 `<a>*1*</a>`、`<sup>` 删除；`read-bd`/`J_BookRead` 容器内 p 标签未闭合，必须 `re.split` 分割，`findall` 返回 0；实体解码 `&nbsp;` 等。
- OCR 文本常把引号识别成 ASCII `"`：生成 Word 前按整章文本流交替替换为中文 `“` `”`（audit 规则：中文段落不得含 ASCII 双引号）。

## 合并与交付

- 按目录顺序合并免费 + OCR 章节为统一 JSON（key 顺序即目录序）；缺失章节保留标题、paras 为空并在 Word 中占位"（本章内容整理中，暂未收录，待后续补全）"。
- Word 生成后必须跑 word skill 的 `scripts/audit.py audit` 至退出码 0，再跑 `catalogue.py --file` 更新 TOC 域。
- 用户手机阅读偏好：额外生成手机版目录长图并上传 CDN 链接（非本地路径）。
