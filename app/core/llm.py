"""LLM 客户端封装。

复用 paratera MaaS（OpenAI 兼容协议）。
- chat_completion：调用 GLM-5.2 做三层分析与裁决报告生成。
- vision_completion：调用 GLM-4V 做截图 OCR 与角色分割。
"""
from __future__ import annotations

import base64
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import get_settings


def get_client() -> AsyncOpenAI:
    s = get_settings()
    return AsyncOpenAI(
        base_url=s.llm_base_url,
        api_key=s.llm_api_key,
        timeout=600,
    )


@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=3, min=3, max=15),
)
async def chat_completion(
    system_prompt: str,
    user_msg: str,
    *,
    model: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> str:
    """同步聊天补全（非流式）。返回文本。"""
    s = get_settings()
    client = get_client()
    resp = await client.chat.completions.create(
        model=model or s.llm_model_reasoning,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_msg},
        ],
        temperature=temperature if temperature is not None else s.llm_temperature,
        max_tokens=max_tokens or s.llm_max_tokens,
    )
    return resp.choices[0].message.content or ""


@retry(
    reraise=True,
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=3, min=3, max=15),
)
async def vision_completion(
    image_bytes: bytes,
    prompt: str,
    *,
    model: str | None = None,
    max_tokens: int = 2048,
) -> str:
    """视觉模型补全。输入图像 bytes + 文本指令，返回文本。

    用于截图 OCR + 发言方角色分割。
    注意：paratera GLM-4V 限制 max_tokens 范围 [1, 2048]。
    """
    s = get_settings()
    if not s.llm_model_vision:
        raise RuntimeError("LLM_MODEL_VISION 未配置，无法处理截图")
    client = get_client()
    b64 = base64.b64encode(image_bytes).decode("ascii")
    data_url = f"data:image/png;base64,{b64}"
    resp = await client.chat.completions.create(
        model=model or s.llm_model_vision,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url},
                    },
                ],
            }
        ],
        max_tokens=min(max_tokens, 2048),
        temperature=0.1,
    )
    return resp.choices[0].message.content or ""
