"""/v1/adjudicate 主裁决路由。

支持 multipart/form-data（含截图上传）或 application/json（纯文本）。
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from app.api.schemas import AdjudicateResponse, ErrorResponse
from app.core.pipeline import adjudicate


router = APIRouter()


@router.post("/v1/adjudicate", response_model=AdjudicateResponse, responses={400: {"model": ErrorResponse}})
async def adjudicate_endpoint(
    dialogue: str | None = Form(default=None),
    context_url: str | None = Form(default=None),
    images: list[UploadFile] | None = File(default=None),
) -> Any:
    """主裁决端点。

    - multipart/form-data：传 dialogue（可选）+ context_url（可选）+ images（可选多图）
    - 至少一项非空。
    """
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
