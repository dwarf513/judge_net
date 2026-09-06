"""截图 OCR + 发言方角色分割。

调用 GLM-4V，剥离 UI 噪声（点赞数、表情包、时间戳、平台 UI 框），
按发言方归类每段话。多图支持按时间拼接。
"""
from __future__ import annotations

import io
import json
import re
from typing import Any

from app.core.llm import vision_completion


def _compress_image(image_bytes: bytes, max_size_mb: float = 1.0, max_dimension: int = 1920) -> bytes:
    """压缩图片到合理大小，避免超过 API 限制。

    - 超过 max_size_mb 的图片会被压缩
    - 最长边超过 max_dimension 的图片会被缩放
    - 统一转为 JPEG 格式（更小、API 兼容性更好）
    """
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


OCR_PROMPT = """你是一个截图解析器。请对这张社交平台截图执行以下任务：

**第一步：提取所有用户名**
先扫描整张截图，列出所有出现的用户名/昵称。用户名特征：
- 通常是短文本（2-15字符），在头像旁边或发言上方
- 可能含中文、日文、英文、数字、特殊符号
- 日期、点赞数、"回复"按钮不是用户名

在 JSON 的 "speakers" 字段中列出所有用户名。

**第二步：逐条归属发言**
对每条发言，根据其在截图中的位置（用户名旁边、回复关系）归到正确的发言方。

**第三步：剥离 UI 噪声**
点赞数、转发数、表情包描述、时间戳、平台 UI 框、广告等不是发言内容。

**注意事项**：
- 嵌套回复（A 发帖 → B 回复 A → C 回复 B）必须理清谁回复谁
- 如果一条回复引用了前一条，在 text 中标注"[回复 @被回复者]"
- 如不确定归属，标 [归属不明]
- **用户名拼写必须与截图中完全一致**，不要修改或简化

JSON 格式输出（严格 JSON，不要 markdown 代码块）：

{
  "speakers": [
    {"id": "A", "name": "截图中出现的完整用户名", "identifier": "昵称/头像/位置"}
  ],
  "messages": [
    {"speaker_id": "A", "text": "发言正文", "order": 1, "reply_to": "被回复者的 id 或 null"}
  ],
  "notes": "若有归属不明或其他说明"
}

若图片无法识别（模糊、截断、非对话截图），返回：
{"speakers": [], "messages": [], "notes": "无法识别原因"}
"""


def _extract_json(text: str) -> dict[str, Any]:
    """从可能含 markdown 代码块的文本中提取 JSON。"""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", cleaned)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {"speakers": [], "messages": [], "notes": f"JSON 解析失败，原文：{text[:200]}"}


async def ocr_image(image_bytes: bytes) -> dict[str, Any]:
    """单图 OCR + 角色分割。返回结构化 dict。"""
    compressed = _compress_image(image_bytes)
    raw = await vision_completion(compressed, OCR_PROMPT, max_tokens=2048)
    return _extract_json(raw)


async def ocr_images(images: list[bytes]) -> dict[str, Any]:
    """多图 OCR，结果按时间顺序拼接，发言方去重，相同内容去重。

    并发策略：最多 2 张一批，避免 API 限流。
    """
    import asyncio

    if not images:
        return {"speakers": [], "messages": [], "notes": "无图片"}
    if len(images) == 1:
        return await ocr_image(images[0])

    BATCH_SIZE = 2
    results: list[Any] = []

    for i in range(0, len(images), BATCH_SIZE):
        batch = images[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(images) + BATCH_SIZE - 1) // BATCH_SIZE
        print(f"[ocr] batch {batch_num}/{total_batches} start ({len(batch)} images)", flush=True)

        tasks = [ocr_image(img) for img in batch]
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        results.extend(batch_results)

        print(f"[ocr] batch {batch_num}/{total_batches} done", flush=True)

    merged_speakers: list[dict[str, Any]] = []
    merged_messages: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    order_offset = 0
    notes_parts: list[str] = []

    for idx, result in enumerate(results, 1):
        if isinstance(result, Exception):
            notes_parts.append(f"图{idx} OCR 失败: {type(result).__name__}: {result}")
            continue
        for sp in result.get("speakers", []):
            if sp not in merged_speakers:
                merged_speakers.append(sp)
        for msg in result.get("messages", []):
            text = msg.get("text", "").strip()
            if text and text not in seen_texts:
                seen_texts.add(text)
                msg["order"] = order_offset + 1
                order_offset += 1
                merged_messages.append(msg)
        if result.get("notes"):
            notes_parts.append(f"图{idx}: {result['notes']}")

    return {
        "speakers": merged_speakers,
        "messages": merged_messages,
        "notes": "多图拼接。" + " | ".join(notes_parts) if notes_parts else "多图拼接",
    }


def format_dialogue_text(ocr_result: dict[str, Any]) -> str:
    """把 OCR 结果格式化为可读对话文本，供 LLM 三层分析使用。"""
    speakers = {sp["id"]: sp.get("name", sp["id"]) for sp in ocr_result.get("speakers", [])}
    messages = ocr_result.get("messages", [])
    if not messages:
        return "(无识别到的对话内容)"
    lines: list[str] = []
    for msg in sorted(messages, key=lambda m: m.get("order", 0)):
        sid = msg.get("speaker_id", "?")
        name = speakers.get(sid, sid)
        text = msg.get("text", "").strip()
        lines.append(f"{name}：{text}")
    return "\n\n".join(lines)
