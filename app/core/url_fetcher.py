"""网页内容抓取。

用户可提供事件背景链接，agent 抓取摘要后注入裁决上下文。
"""
from __future__ import annotations

import re
from typing import Any

import httpx


def _strip_html(text: str) -> str:
    """简单 HTML 标签剥离 + 多余空白清理。"""
    text = re.sub(r"<script[\s\S]*?</script>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


async def fetch_url_content(url: str, max_chars: int = 3000) -> dict[str, Any]:
    """抓取网页内容，返回标题 + 正文摘要。

    返回：{url, title, content, notes}
    若抓取失败，返回 notes 说明原因。
    """
    if not url or not url.strip():
        return {"url": "", "title": "", "content": "", "notes": "无 URL"}

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        return {"url": url, "title": "", "content": "", "notes": "URL 格式不正确"}

    try:
        async with httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; judge_net/1.0)"},
        ) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "")
            if "text/html" not in content_type and "text/plain" not in content_type:
                return {"url": url, "title": "", "content": "", "notes": f"非文本内容: {content_type}"}
            raw = resp.text
    except Exception as exc:
        return {"url": url, "title": "", "content": "", "notes": f"抓取失败: {type(exc).__name__}: {exc}"}

    title = ""
    title_match = re.search(r"<title>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
    if title_match:
        title = title_match.group(1).strip()[:200]

    text = _strip_html(raw)
    if not text:
        return {"url": url, "title": title, "content": "", "notes": "页面无可提取文本"}

    content = text[:max_chars]
    if len(text) > max_chars:
        content += "...（已截断）"

    return {"url": url, "title": title, "content": content, "notes": "抓取成功"}


def format_url_content(result: dict[str, Any]) -> str:
    """把抓取结果格式化为可注入 LLM 的文本。"""
    if not result.get("content"):
        return ""
    parts = [f"=== 用户提供的事件背景链接 ===", f"URL: {result['url']}"]
    if result.get("title"):
        parts.append(f"标题: {result['title']}")
    parts.append(f"内容摘要:\n{result['content']}")
    return "\n".join(parts)
