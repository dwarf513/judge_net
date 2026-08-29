"""全局配置加载。

通过环境变量或 .env 文件读取配置。
本地开发可复用 ../scholar_agent/.env，或自行准备 .env。
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


REPO_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM
    llm_base_url: str = "https://llmapi.paratera.com/v1"
    llm_api_key: str = ""
    llm_model_reasoning: str = "GLM-4-Plus"
    llm_model_vision: str = "GLM-4V"
    llm_model_embedding: str = "GLM-Embedding-2"

    # 搜索
    tavily_api_key: str = ""

    # 服务
    port: int = 7860
    auth_enabled: bool = False

    # 会话
    session_ttl_seconds: int = 3600

    # LLM 调用参数
    llm_max_tokens: int = 16384
    llm_temperature: float = 0.3

    env: str = "production"

    @property
    def system_prompt_path(self) -> Path:
        return REPO_ROOT / "system_prompt.md"

    @property
    def knowledge_dir(self) -> Path:
        return REPO_ROOT / "knowledge"

    @property
    def static_dir(self) -> Path:
        return REPO_ROOT / "static"

    @property
    def regression_outputs_dir(self) -> Path:
        return REPO_ROOT / "docs" / "regression_outputs"

    def ensure_dirs(self) -> None:
        for p in (self.regression_outputs_dir,):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    s = Settings()
    if os.environ.get("PORT"):
        s.port = int(os.environ["PORT"])
    s.ensure_dirs()
    return s
