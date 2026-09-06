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

直接输出纯文本，每行一条。"""


def _compress_image(image_bytes: bytes, max_size_mb: float = 1.0, max_dimension: int = 1920) -> bytes:
    """压缩图片到合理大小，避免超过 API 限制。"""
    try:
        from PIL import Image
    except ImportError:
        return image_bytes

    try:
        img = Image.open(io.BytesIO(image_bytes))
    except Exception:
        return image_bytes

    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb <= max_size_mb and max(img.size) <= max_dimension:
        return image_bytes

    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")

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


async def ocr_image(image_bytes: bytes) -> str:
    """单图 OCR。返回纯文本（逐行识别的文字）。"""
    compressed = _compress_image(image_bytes)
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
