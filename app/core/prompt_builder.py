"""提示词组装器。

启动时加载 system_prompt.md + 7 个 knowledge/*.md，拼接为完整系统提示词。
缓存在内存中，避免每次请求 IO。修改提示词后需重启服务。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from app.config import get_settings


@lru_cache(maxsize=1)
def get_system_prompt() -> str:
    """加载并组装完整系统提示词。

    结构：system_prompt.md + 知识库附件（7 个 .md 拼接）。
    与 scripts/regression_test.py 的 build_system_prompt 保持一致。
    """
    s = get_settings()
    sp_path = s.system_prompt_path
    if not sp_path.exists():
        raise FileNotFoundError(f"system_prompt.md 未找到：{sp_path}")
    sp = sp_path.read_text(encoding="utf-8")

    parts: list[str] = [sp, "\n\n---\n\n# 知识库附件（由后端 prompt_builder 注入）\n"]
    knowledge_dir = s.knowledge_dir
    if not knowledge_dir.is_dir():
        raise FileNotFoundError(f"knowledge 目录未找到：{knowledge_dir}")
    for kf in sorted(knowledge_dir.glob("*.md")):
        parts.append(f"\n\n## 知识库文件：{kf.name}\n\n")
        parts.append(kf.read_text(encoding="utf-8"))
    return "".join(parts)


def reload_system_prompt() -> str:
    """清缓存重新加载。供 /admin/reload 调用（若实现）。"""
    get_system_prompt.cache_clear()
    return get_system_prompt()
