"""/v1/adjudicate 主裁决路由。

支持 multipart/form-data（含截图上传）或 application/json（纯文本）。
SSE 流式端点 /v1/adjudicate/stream 实时推送生成进度。
"""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.api.schemas import AdjudicateResponse, ErrorResponse
from app.core.pipeline import adjudicate, adjudicate_stream


router = APIRouter()


@router.post("/v1/adjudicate", response_model=AdjudicateResponse, responses={400: {"model": ErrorResponse}})
async def adjudicate_endpoint(
    dialogue: str | None = Form(default=None),
    context_url: str | None = Form(default=None),
    images: list[UploadFile] | None = File(default=None),
) -> Any:
    """主裁决端点（非流式）。"""
    if not dialogue and not images:
        return JSONResponse(status_code=400, content={"error": "必须提供 dialogue 或 images"})

    image_bytes_list: list[bytes] = []
    if images:
        for img in images:
            content = await img.read()
            if content:
                image_bytes_list.append(content)

    result = await adjudicate(dialogue=dialogue, images=image_bytes_list or None, context_url=context_url)

    if "error" in result:
        return JSONResponse(status_code=400, content={"error": result["error"]})

    return AdjudicateResponse(
        session_id=result["session_id"],
        dialogue_used=result["dialogue_used"],
        verdict=result["verdict"],
        search_used=result["search_used"],
        notes=result["notes"],
    )


@router.post("/v1/adjudicate/stream")
async def adjudicate_stream_endpoint(
    dialogue: str | None = Form(default=None),
    context_url: str | None = Form(default=None),
    images: list[UploadFile] | None = File(default=None),
) -> Any:
    """主裁决流式端点（SSE）。

    返回 Server-Sent Events 流：
    - {"type":"stage","stage":"ocr"} — 阶段开始
    - {"type":"chunk","content":"..."} — 文本片段
    - {"type":"done","session_id":"...","search_used":bool} — 完成
    - {"type":"error","error":"..."} — 错误
    """
    image_bytes_list: list[bytes] = []
    if images:
        for img in images:
            content = await img.read()
            if content:
                image_bytes_list.append(content)

    async def event_generator():
        async for event in adjudicate_stream(
            dialogue=dialogue,
            images=image_bytes_list or None,
            context_url=context_url,
        ):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
