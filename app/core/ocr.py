"""截图 OCR + 发言方角色分割。

调用 GLM-4V，剥离 UI 噪声（点赞数、表情包、时间戳、平台 UI 框），
按发言方归类每段话。多图支持按时间拼接。
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.llm import vision_completion


OCR_PROMPT = """你是一个截图解析器。请对这张社交平台截图执行以下任务：

1. 识别截图中的所有文字内容。
2. 剥离 UI 噪声：点赞数、转发数、表情包图像描述、时间戳、平台 UI 框、广告等。
3. 只保留发言正文。
4. 把每段话归到正确的发言方。如不确定归属，标 [归属不明]。
5. 多张图属于同一争议时，按时间顺序拼接，去重相同内容。

请按以下 JSON 格式输出（严格 JSON，不要 markdown 代码块包裹，不要任何解释文字）：

{
  "speakers": [
    {"id": "A", "name": "@用户A 或标识依据", "identifier": "昵称/头像/位置"}
  ],
  "messages": [
    {"speaker_id": "A", "text": "发言正文", "order": 1}
  ],
  "notes": "若多图拼接去重或归属不明，在此说明"
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
    raw = await vision_completion(image_bytes, OCR_PROMPT, max_tokens=2048)
    return _extract_json(raw)


async def ocr_images(images: list[bytes]) -> dict[str, Any]:
    """多图 OCR，结果按时间顺序拼接，发言方去重，相同内容去重。"""
    if not images:
        return {"speakers": [], "messages": [], "notes": "无图片"}
    if len(images) == 1:
        return await ocr_image(images[0])

    merged_speakers: list[dict[str, Any]] = []
    merged_messages: list[dict[str, Any]] = []
    seen_texts: set[str] = set()
    order_offset = 0
    notes_parts: list[str] = []

    for idx, img in enumerate(images, 1):
        result = await ocr_image(img)
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
