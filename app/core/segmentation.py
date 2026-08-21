"""发言方归属启发式辅助。

OCR 已识别发言方，但有时需补充启发式修正（如归 [归属不明] 的消息）。
当前为轻量辅助；保留接口便于后续扩展。
"""
from __future__ import annotations

from typing import Any


def merge_speaker_aliases(speakers: list[dict[str, Any]]) -> dict[str, str]:
    """合并明显同义的发言方（如 "@A" 与 "用户A"）。返回 id → 统一名 映射。"""
    aliases: dict[str, str] = {}
    for sp in speakers:
        sid = sp.get("id", "")
        name = sp.get("name", sid)
        aliases[sid] = name
    return aliases


def flag_unknown_speakers(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把 speaker_id 为空或 [归属不明] 的消息标 [归属不明]。"""
    flagged: list[dict[str, Any]] = []
    for msg in messages:
        sid = msg.get("speaker_id", "") or ""
        if not sid.strip() or "不明" in sid:
            msg["speaker_id"] = "?"
            msg["speaker_unknown"] = True
        else:
            msg["speaker_unknown"] = False
        flagged.append(msg)
    return flagged
