"""截图 OCR。

GLM-4V 只负责"读字"——把截图中的文字逐行识别出来。
不做任何结构化/归人——那交给 DeepSeek 对话结构解析。
"""
from __future__ import annotations

import io
from typing import Any

from app.core.llm import vision_completion


OCR_PROMPT = """请识别这张社交平台截图中的所有文字内容，逐行输出。

要求：
1. 从上到下、从左到右，逐行识别截图中可见的所有文字。
2. 保留原始格式：用户名、发言内容、日期、点赞数、"回复"按钮等，全部原样输出。
3. 不做任何结构化处理——不要分发言人、不要做JSON、不要判断谁说了什么。
4. 只是把图片中的文字"读出来"，逐行排列。
5. 如果有"回复 @某某"等引用格式，保留原文。
6. 用户名拼写必须与截图中完全一致（包括日文、特殊符号、英文字母数量）。
7. 如果某行看不清，标 [模糊] 跳过。
8. 不要添加任何解释说明，只输出识别到的文字。
9. **即使某个人只说了一句话，也必须完整识别其用户名和发言——不要遗漏任何发言方**。一个用户名后面即使只有一个短回复（如"哈哈哈哈"或"赞成"），也要完整输出。
10. **特别注意截图边缘的发言**——用户可能只回复了一个字或一个表情，这些容易被遗漏，必须识别出来。

直接输出纯文本，每行一条。"""


def _compress_image(image_bytes: bytes, max_size_mb: float = 1.0, max_dimension: int = 1920) -> bytes:
    """压缩图片到合理大小，避免超过 API 限制。

    对长图（高度远大于宽度）特殊处理：
    - 不把高度压缩到 1920 以下（否则文字不可读）
    - 改为按宽度限制 + 分段策略
    """
    try:
        from PIL import Image
    except ImportError:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return image_bytes

    w, h = img.size
    size_mb = len(image_bytes) / (1024 * 1024)

    # 判断是否为长图（高度 > 宽度 * 3）
    is_long = h > w * 3

    print(f"[ocr] image: {w}x{h}, {size_mb:.1f}MB, long={is_long}", flush=True)

    if not is_long and size_mb <= max_size_mb and max(img.size) <= max_dimension:
        return image_bytes

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    if is_long:
        # 长图：限制宽度到 1080（保持文字清晰），高度不限制
        target_width = min(w, 1080)
        if w > target_width:
            ratio = target_width / w
            new_h = int(h * ratio)
            img = img.resize((target_width, new_h), Image.Resampling.LANCZOS)
            print(f"[ocr] long image resized: {w}x{h} → {target_width}x{new_h}", flush=True)

        # 检查压缩后大小，如果仍超 2MB，降低 JPEG 质量
        quality = 85
        while quality > 40:
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=quality, optimize=True)
            compressed = buf.getvalue()
            if len(compressed) / (1024 * 1024) <= 2.0:
                break
            quality -= 10

        print(f"[ocr] long image compressed: {size_mb:.1f}MB → {len(compressed)/1024/1024:.1f}MB, "
              f"size={img.size}, quality={quality}", flush=True)
        return compressed
    else:
        # 普通图片：最长边限制 1920
        if max(img.size) > max_dimension:
            ratio = max_dimension / max(img.size)
            new_size = (int(img.width * ratio), int(img.height * ratio))
            img = img.resize(new_size, Image.Resampling.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85, optimize=True)
        compressed = buf.getvalue()

        print(f"[ocr] image compressed: {size_mb:.1f}MB → {len(compressed)/1024/1024:.1f}MB, "
              f"size={img.size}", flush=True)
        return compressed


def _split_long_image(img_bytes: bytes, segment_height: int = 3000) -> list[bytes]:
    """将长图按高度分段，每段约 3000px（保持文字可读）。

    返回多个 JPEG bytes。
    """
    try:
        from PIL import Image
    except ImportError:
        return [img_bytes]

    try:
        img = Image.open(io.BytesIO(img_bytes))
    except Exception:
        return [img_bytes]

    w, h = img.size
    if h <= segment_height:
        return [img_bytes]

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

    segments = []
    overlap = 200  # 重叠 200px 避免切割处丢文字

    y = 0
    while y < h:
        bottom = min(y + segment_height, h)
        seg = img.crop((0, y, w, bottom))
        buf = io.BytesIO()
        seg.save(buf, format="JPEG", quality=85, optimize=True)
        segments.append(buf.getvalue())
        print(f"[ocr] segment: y={y}-{bottom}, {w}x{bottom-y}px", flush=True)
        y = bottom - overlap if bottom < h else h

    print(f"[ocr] long image split into {len(segments)} segments", flush=True)
    return segments


async def ocr_image(image_bytes: bytes) -> str:
    """单图 OCR。返回纯文本（逐行识别的文字）。

    对长图自动分段处理。
    """
    import asyncio

    compressed = _compress_image(image_bytes)

    # 检查是否需要分段
    try:
        from PIL import Image
        img = Image.open(io.BytesIO(compressed))
        w, h = img.size
        if h > w * 3 and h > 3000:
            # 长图分段
            segments = _split_long_image(compressed)
            if len(segments) > 1:
                results = []
                for i, seg in enumerate(segments, 1):
                    print(f"[ocr] segment {i}/{len(segments)} start", flush=True)
                    raw = await vision_completion(seg, OCR_PROMPT, max_tokens=2048)
                    results.append(raw.strip())
                    print(f"[ocr] segment {i}/{len(segments)} done, {len(raw)} chars", flush=True)
                return "\n".join(results)
    except Exception as exc:
        print(f"[ocr] split check failed: {exc}, use whole image", flush=True)

    raw = await vision_completion(compressed, OCR_PROMPT, max_tokens=2048)
    return raw.strip()


async def ocr_images(images: list[bytes]) -> str:
    """多图 OCR。分批并发，拼接为一段纯文本。

    返回纯文本（不是 JSON），供 DeepSeek 对话结构解析使用。
    """
    import asyncio

    if not images:
        return "(无图片)"
    if len(images) == 1:
        return await ocr_image(images[0])

    BATCH_SIZE = 2
    all_texts: list[str] = []

    for i in range(0, len(images), BATCH_SIZE):
        batch = images[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(images) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"[ocr] batch {batch_num}/{total_batches} start ({len(batch)} images)", flush=True)

        tasks = [ocr_image(img) for img in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for idx, result in enumerate(batch_results, 1):
            if isinstance(result, Exception):
                print(f"[ocr] image {i+idx} failed: {type(result).__name__}: {result}", flush=True)
                all_texts.append(f"\n[截图 {i+idx} 识别失败]\n")
            else:
                all_texts.append(f"\n=== 截图 {i+idx} ===\n{result}\n")

        print(f"[ocr] batch {batch_num}/{total_batches} done", flush=True)

    return "\n".join(all_texts)
