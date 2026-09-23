# -*- coding: utf-8 -*-
"""VIP 章节正文图片 OCR（刺猬猫图片化章节）。

前提：已用浏览器（登录态）把每章正文图下载为 {cid}.png（见 SKILL.md）。
配置：rapidocr 3.9.x + PP-OCRv5 server(det+rec) + OpenVINO，经实测是本流程
      质量与速度的最优组合。内存约束：整机 16GB 时最多 2 进程并行，
      det server 推理为单线程瓶颈，多进程抢 CPU 反而更慢。

用法:
  python ocr_vip_images.py --images-dir DIR --output-dir OUT [--workers 2] [--block-h 1100]
输出: OUT/inc_{worker}.jsonl，每行 {"cid","status","text","lines":[{y,t}]}，
      status ∈ ok/empty/error；每章完成即追加写盘（崩溃不丢）。
"""
import io, sys, os, json, time, argparse
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')


def build_engine():
    from rapidocr import RapidOCR, EngineType, LangDet, ModelType, OCRVersion
    params = {
        "Global.max_side_len": 4000,
        "Det.engine_type": EngineType.OPENVINO,
        "Det.lang_type": LangDet.CH,
        "Det.model_type": ModelType.SERVER,
        "Det.ocr_version": OCRVersion.PPOCRV5,
        "Det.limit_side_len": 2500,
        "Det.limit_type": "max",
        "Rec.engine_type": EngineType.OPENVINO,
        "Rec.lang_type": LangDet.CH,
        "Rec.model_type": ModelType.SERVER,
        "Rec.ocr_version": OCRVersion.PPOCRV5,
        # 不设置 inference_num_threads（保持默认）——实测单线程更快
    }
    return RapidOCR(params=params)


def ocr_chapter(engine, img_path, block_h=1100):
    """整章图片切块识别，返回 (text, lines)。lines 按 y 坐标升序。"""
    from PIL import Image
    im = Image.open(img_path)
    w, h = im.size
    all_lines = []
    tmp = img_path + '.blk.png'
    for i, y0 in enumerate(range(0, h, block_h)):
        y1 = min(y0 + block_h, h)
        blk = im.crop((0, y0, w, y1))
        blk.save(tmp)
        try:
            r = engine(tmp)
            if r is not None and r.txts:
                for box, t in zip(r.boxes, r.txts):
                    try:
                        yy = int(box[0][1]) + y0
                    except Exception:
                        yy = 0
                    all_lines.append({"y": yy, "t": t})
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)
    all_lines.sort(key=lambda x: x["y"])
    text = "".join(x["t"] for x in all_lines)
    return text, all_lines


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--images-dir', required=True, help='正文图目录（{cid}.png）')
    ap.add_argument('--output-dir', required=True, help='jsonl 输出目录')
    ap.add_argument('--workers', type=int, default=2, help='并行进程数，16GB 内存上限 2')
    ap.add_argument('--block-h', type=int, default=1100, help='切块高度像素')
    ap.add_argument('--shard', type=int, default=0, help='本进程负责的分片序号（0 起）')
    args = ap.parse_args()

    os.makedirs(args.output_dir, exist_ok=True)
    pngs = sorted(f for f in os.listdir(args.images_dir) if f.endswith('.png'))
    cids = [f[:-4] for f in pngs]
    # 分片：把任务均分给 workers 个进程
    my = cids[args.shard::args.workers]
    out = os.path.join(args.output_dir, f'inc_{args.shard}.jsonl')
    # 跳过已完成
    done = set()
    if os.path.exists(out):
        for line in open(out, encoding='utf-8'):
            try:
                done.add(json.loads(line)['cid'])
            except Exception:
                pass
    todo = [c for c in my if c not in done]
    print(f"进程{args.shard}: 共{len(my)} 待处理{len(todo)}")

    engine = build_engine()
    with open(out, 'a', encoding='utf-8') as f:
        for cid in todo:
            p = os.path.join(args.images_dir, cid + '.png')
            try:
                text, lines = ocr_chapter(engine, p, args.block_h)
                status = 'ok' if text else 'empty'
                rec = {"cid": cid, "status": status, "text": text, "lines": lines}
            except Exception as e:
                rec = {"cid": cid, "status": "error", "text": "", "lines": [], "err": str(e)}
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
            f.flush()
            print(f"[{args.shard}] {cid} {rec['status']} {len(rec.get('text') or '')}字")
    print(f"进程{args.shard} 完成")


if __name__ == '__main__':
    main()
