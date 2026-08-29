"""/v1/reply-script 应答话术路由（opt-in + 生成）。"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.api.schemas import (
    ErrorResponse,
    ReplyScriptOptInRequest,
    ReplyScriptOptInResponse,
    ReplyScriptRequest,
    ReplyScriptResponse,
)
from app.core.session import get_session_store
from app.core.pipeline import reply_script


router = APIRouter()


OPT_IN_MESSAGE = (
    "您已确认应答话术模式 opt-in 条款：\n"
    "1. 您是本争议的当事方之一。\n"
    "2. 仅基于已核实事实回复，不进行人身攻击、人肉、煽动群攻、欺骗性话术。\n"
    "3. 话术仅是建议，发送前的最终判断与责任由您本人承担。\n"
    "4. judge_net 不为话术的传播后果承担责任。\n\n"
    "已记录 opt-in 状态，可调用 POST /v1/reply-script 生成话术。"
)


@router.post("/v1/reply-script/opt-in", response_model=ReplyScriptOptInResponse, responses={404: {"model": ErrorResponse}})
async def reply_script_opt_in(req: ReplyScriptOptInRequest) -> Any:
    """显式 opt-in 确认。"""
    store = get_session_store()
    session = store.get(req.session_id)
    if session is None:
        return JSONResponse(status_code=404, content={"error": f"session_id {req.session_id} 不存在或已过期"})
    store.set_reply_script_opt_in(req.session_id, True)
    return ReplyScriptOptInResponse(
        session_id=req.session_id,
        opted_in=True,
        message=OPT_IN_MESSAGE,
    )


@router.post("/v1/reply-script", response_model=ReplyScriptResponse, responses={400: {"model": ErrorResponse}, 404: {"model": ErrorResponse}})
async def reply_script_endpoint(req: ReplyScriptRequest) -> Any:
    """生成应答话术（须先 opt-in，支持多轮对话）。"""
    valid_styles = {"直接说理", "反讽克制", "委婉纠正", "引经据典", "降温退场"}
    if req.style not in valid_styles:
        return JSONResponse(
            status_code=400,
            content={"error": f"style 必须是 {valid_styles} 之一"},
        )

    result = await reply_script(
        session_id=req.session_id,
        style=req.style,
        extra=req.extra,
        opponent_reply=req.opponent_reply,
        round_num=req.round_num,
    )

    if "error" in result:
        if "不存在" in result["error"]:
            return JSONResponse(status_code=404, content={"error": result["error"]})
        return JSONResponse(status_code=400, content={"error": result["error"]})

    return ReplyScriptResponse(
        session_id=result["session_id"],
        style=result["style"],
        round=result["round"],
        script=result["script"],
        total_rounds=result["total_rounds"],
    )
