"""一键 OCR：拖图片 → 出文字。不占 Claude 上下文。
首次运行会下载模型 (~100MB)，之后秒出。
"""
import sys
import os
import json

_ocr = None

def get_ocr():
    global _ocr
    if _ocr is None:
        import easyocr
        _ocr = easyocr.Reader(['ch_sim', 'en'], gpu=True)
    return _ocr


def ocr_image(image_path):
    reader = get_ocr()
    results = reader.readtext(image_path)

    if not results:
        print("[无文字]")
        return ""

    lines = []
    for (bbox, text, confidence) in results:
        lines.append(text)
        print(f"  [{confidence:.0%}] {text}")

    return "\n".join(lines)


def ocr_image_structured(image_path):
    reader = get_ocr()
    results = reader.readtext(image_path)

    if not results:
        print("[无文字]")
        return []

    items = []
    for (bbox, text, confidence) in results:
        items.append({
            "text": text,
            "confidence": round(confidence, 4),
            "x": int(bbox[0][0]),
            "y": int(bbox[0][1]),
            "w": int(bbox[2][0] - bbox[0][0]),
            "h": int(bbox[2][1] - bbox[0][1]),
        })
        print(f"  [{confidence:.0%}] ({items[-1]['x']},{items[-1]['y']}) {text}")

    return items


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: py -3 ocr.py <图片路径>")
        print("      py -3 ocr.py <图片路径> --json  (结构化+坐标)")
        sys.exit(1)

    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"文件不存在: {image_path}")
        sys.exit(1)

    use_json = "--json" in sys.argv

    print(f"OCR: {image_path}")
    print("-" * 50)

    if use_json:
        items = ocr_image_structured(image_path)
        out_path = image_path + ".ocr.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"\n结构化结果: {out_path}")
    else:
        text = ocr_image(image_path)
        out_path = image_path + ".ocr.txt"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(text)
        print(f"\n文本结果: {out_path}")
