"""/v1/appeal 上诉路由。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.schemas import AppealRequest, AppealResponse, ErrorResponse
from app.core.pipeline import appeal


router = APIRouter()


@router.post("/v1/appeal", response_model=AppealResponse, responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def appeal_endpoint(req: AppealRequest) -> Any:
    """上诉端点：局部重审。"""
    result = await appeal(
        session_id=req.session_id,
        appealed_section=req.appealed_section,
        appeal_reason=req.appeal_reason,
    )

    if "error" in result:
        if "不存在" in result["error"]:
            return JSONResponse(status_code=404, content={"error": result["error"]})
        return JSONResponse(status_code=400, content={"error": result["error"]})

    return AppealResponse(
        session_id=result["session_id"],
        appealed_section=result["appealed_section"],
        second_verdict=result["second_verdict"],
    )
