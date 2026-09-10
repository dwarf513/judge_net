"""FastAPI 应用入口。

挂载路由、CORS、健康检查、根路径信息、静态文件服务。
监听端口由 Settings 决定（默认 7860）。
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.api.adjudicate import router as adjudicate_router
from app.api.appeal import router as appeal_router
from app.api.reply_script import router as reply_script_router
from app.api.chat import router as chat_router
from app.core.prompt_builder import get_system_prompt


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    s.ensure_dirs()
    print(f"[judge_net] starting env={s.env} port={s.port}")
    print(f"[judge_net] reasoning model={s.llm_model_reasoning}")
    print(f"[judge_net] vision model={s.llm_model_vision}")
    print(f"[judge_net] auth_enabled={s.auth_enabled}")
    try:
        sp = get_system_prompt()
        print(f"[judge_net] system prompt ready: {len(sp)} chars")
    except Exception as e:
        print(f"[judge_net] system prompt load failed: {e}")
    yield
    print("[judge_net] shutting down")


def create_app() -> FastAPI:
    s = get_settings()
    app = FastAPI(
        title="judge_net",
        description="网络冲突法官智能体 - DIY 高代码赛道",
        version="0.2.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(adjudicate_router)
    app.include_router(appeal_router)
    app.include_router(reply_script_router)
    app.include_router(chat_router)

    @app.get("/")
    async def root():
        index_path = s.static_dir / "index.html"
        if index_path.is_file():
            return FileResponse(index_path, media_type="text/html")
        return {"name": "judge_net", "version": "0.2.0", "error": "static/index.html not found"}

    @app.get("/info")
    async def info():
        return {
            "name": "judge_net",
            "version": "0.2.0",
            "description": "网络冲突法官智能体",
            "endpoints": {
                "adjudicate": "/v1/adjudicate",
                "adjudicate_stream": "/v1/adjudicate/stream",
                "appeal": "/v1/appeal",
                "reply_script": "/v1/reply-script",
                "chat": "/v1/chat",
                "health": "/healthz",
            },
        }

    @app.get("/healthz")
    async def healthz():
        return {
            "status": "ok",
            "model": s.llm_model_reasoning,
            "vision_model": s.llm_model_vision,
        }

    @app.get("/readyz")
    async def readyz():
        ok = bool(s.llm_api_key)
        return {
            "ready": ok,
            "auth_enabled": s.auth_enabled,
            "search_configured": bool(s.tavily_api_key),
            "vision_configured": bool(s.llm_model_vision),
        }

    static_dir = s.static_dir
    if os.path.isdir(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir, html=True), name="static")

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    s = get_settings()
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=s.port,
        reload=False,
        log_level="info",
    )
