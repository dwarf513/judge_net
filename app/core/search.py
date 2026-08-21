"""联网检索客户端（Tavily）。

按 source_credibility.md 的 Tier 分层映射信源。
不强制每次裁决都搜索——只在 LLM 判定"需要事实核查"时调用，节省额度。
"""
from __future__ import annotations

from typing import Any

import httpx

from app.config import get_settings


TAVILY_ENDPOINT = "https://api.tavily.com/search"


GOV_DOMAINS = {"gov.cn", "stats.gov.cn", "gov.uk", "usa.gov"}
ORG_DOMAINS = {"who.int", "un.org", "wto.org", "imf.org", "worldbank.org"}
ACADEMIC_DOMAINS = {"nature.com", "science.com", "arxiv.org", "cnki.net", "pubmed.ncbi.nlm.nih.gov"}
NEWS_DOMAINS = {
    "xinhuanet.com", "news.cn", "people.com.cn", "cctv.com",
    "bbc.com", "bbc.co.uk", "nytimes.com", "reuters.com", "apnews.com",
}
WIKI_DOMAINS = {"wikipedia.org", "zh.wikipedia.org", "en.wikipedia.org"}


def classify_tier(url: str) -> str:
    """根据 URL 域名映射信源层级。"""
    url_lower = url.lower()
    for d in GOV_DOMAINS:
        if d in url_lower:
            return "Tier-1 政府官方"
    for d in ORG_DOMAINS:
        if d in url_lower:
            return "Tier-1 国际组织"
    for d in ACADEMIC_DOMAINS:
        if d in url_lower:
            return "Tier-1 学术同行评议"
    for d in NEWS_DOMAINS:
        if d in url_lower:
            return "Tier-2 主流媒体"
    for d in WIKI_DOMAINS:
        if d in url_lower:
            return "Tier-2 百科（受控编辑）"
    return "Tier-3 参考性信源"


async def search(query: str, max_results: int = 5) -> dict[str, Any]:
    """调用 Tavily 搜索 API。

    返回：{query, results: [{title, url, content, tier}], notes}
    若未配置 TAVILY_API_KEY，返回降级结果。
    """
    s = get_settings()
    if not s.tavily_api_key:
        return {
            "query": query,
            "results": [],
            "notes": "未配置 TAVILY_API_KEY，跳过联网检索。本次裁决仅基于模型训练知识，所有事实结论须标'截至训练数据'。",
        }

    payload = {
        "api_key": s.tavily_api_key,
        "query": query,
        "search_depth": "advanced",
        "max_results": max_results,
        "include_answer": True,
        "include_raw_content": False,
    }
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(TAVILY_ENDPOINT, json=payload)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        return {
            "query": query,
            "results": [],
            "notes": f"Tavily 调用失败：{type(exc).__name__}: {exc}。本次裁决降级为仅模型知识。",
        }

    results: list[dict[str, Any]] = []
    for r in data.get("results", [])[:max_results]:
        url = r.get("url", "")
        results.append({
            "title": r.get("title", ""),
            "url": url,
            "content": (r.get("content") or "")[:500],
            "tier": classify_tier(url),
        })

    return {
        "query": query,
        "direct_answer": data.get("answer", ""),
        "results": results,
        "notes": f"找到 {len(results)} 条结果，按 source_credibility.md 分层标注。",
    }


async def search_batch(queries: list[str], max_results: int = 3) -> list[dict[str, Any]]:
    """批量搜索多个查询。"""
    return [await search(q, max_results=max_results) for q in queries]


def format_search_results(results: list[dict[str, Any]]) -> str:
    """把搜索结果格式化为可注入 LLM 的文本。"""
    if not results:
        return "(无信源)"
    parts: list[str] = []
    for r in results:
        parts.append(f"### 查询：{r.get('query', '')}")
        if r.get("direct_answer"):
            parts.append(f"直接答案：{r['direct_answer']}")
        if r.get("notes"):
            parts.append(f"说明：{r['notes']}")
        for item in r.get("results", []):
            parts.append(
                f"- [{item['tier']}] {item['title']}\n  URL: {item['url']}\n  摘要: {item['content']}"
            )
    return "\n\n".join(parts)
