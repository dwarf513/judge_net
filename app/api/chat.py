"""/v1/chat 聊天路由（SSE 流式）。

用户可以在裁决后继续追问、补充、讨论。
基于原争议对话 + 裁决报告作为上下文，保持连贯。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.api.schemas import ErrorResponse
from app.core.pipeline import _parse_dialogue_structure
from app.core.session import get_session_store
from app.core.llm import chat_completion_stream
from app.core.prompt_builder import get_system_prompt


router = APIRouter()


CHAT_SYSTEM_SUFFIX = """

你正在与用户进行裁决后的追问对话。用户可能：
- 对裁决某节不理解，请进一步解释
- 补充新的信息或证据
- 询问如何应对某个特定发言方
- 讨论裁决的公正性

要求：
- 保持裁决的一致性，不推翻已做出的裁决（除非用户提供了确凿的新证据）
- 回答简洁有力，像对话而非写报告
- 引用裁决报告中的具体条目时标注节号（如"在第五节中指出的……"）
- 如果用户的问题超出裁决范围（如要求评价当事人的人格），温和拒绝
- 温度与同理心：理解用户的困惑，帮用户释然而非说教
"""


class ChatRequest(BaseModel):
    session_id: str = Field(..., description="裁决时返回的 session_id")
    message: str = Field(..., description="用户的追问内容")


@router.post("/v1/chat")
async def chat_endpoint(req: ChatRequest) -> Any:
    """裁决后追问对话（SSE 流式）。

    基于原争议对话 + 裁决报告作为上下文，保持连贯。
    """
    store = get_session_store()
    session = store.get(req.session_id)
    if session is None:
        return JSONResponse(status_code=404, content={"error": f"session_id {req.session_id} 不存在或已过期"})

    if not req.message.strip():
        return JSONResponse(status_code=400, content={"error": "消息不能为空"})

    system_prompt = get_system_prompt() + CHAT_SYSTEM_SUFFIX

    # 构建上下文消息
    context_msg = f"""以下是之前的争议对话和裁决报告，作为本次对话的上下文：

=== 原争议对话 ===
{session.dialogue[:3000]}

=== 原裁决报告 ===
{session.verdict[:4000]}

=== 用户追问 ===
{req.message}
"""

    async def event_generator():
        try:
            async for chunk in chat_completion_stream(system_prompt, context_msg):
                yield f"data: {json.dumps({'type': 'chunk', 'content': chunk}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'error': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
