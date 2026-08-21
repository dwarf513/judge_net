"""请求与响应模型（Pydantic）。"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AdjudicateRequest(BaseModel):
    dialogue: str | None = Field(default=None, description="对话原文（与 images 至少一项非空）")


class AdjudicateResponse(BaseModel):
    session_id: str
    dialogue_used: str
    verdict: str
    search_used: bool
    notes: str


class AppealRequest(BaseModel):
    session_id: str = Field(..., description="裁决时返回的 session_id")
    appealed_section: str = Field(..., description="不服的具体条目，如'四、事实核查表第 2 条'")
    appeal_reason: str = Field(..., description="新证据或具体异议理由")


class AppealResponse(BaseModel):
    session_id: str
    appealed_section: str
    second_verdict: str


class ReplyScriptOptInRequest(BaseModel):
    session_id: str = Field(..., description="裁决时返回的 session_id")


class ReplyScriptOptInResponse(BaseModel):
    session_id: str
    opted_in: bool
    message: str


class ReplyScriptRequest(BaseModel):
    session_id: str = Field(..., description="已 opt-in 的 session_id")
    style: str = Field(
        default="降温退场",
        description="话术风格：直接说理 / 反讽克制 / 委婉纠正 / 引经据典 / 降温退场",
    )
    extra: str = Field(default="", description="用户额外说明")


class ReplyScriptResponse(BaseModel):
    session_id: str
    style: str
    script: str


class ErrorResponse(BaseModel):
    error: str
