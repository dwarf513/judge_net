"""主流水线：编排 OCR → 分割 → LLM 三层分析 → 裁决报告生成。

对应 system_prompt.md 的全流程指令。
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.llm import chat_completion
from app.core.ocr import format_dialogue_text, ocr_images
from app.core.prompt_builder import get_system_prompt
from app.core.search import format_search_results, search
from app.core.session import get_session_store


ADJUDICATE_USER_PROMPT = """请对以下网络对话做出裁决，严格按 system_prompt.md 中规定的 12 节裁决报告格式输出。

=== 对话原文 ===
{dialogue}
"""

APPEAL_USER_PROMPT = """以下是此前生成的裁决报告：

=== 原裁决报告 ===
{verdict}

用户对该裁决不服，发起上诉：

=== 上诉条目 ===
{appealed_section}

=== 上诉理由 / 新证据 ===
{appeal_reason}

请依据 knowledge/appeal_protocol.md 的协议，仅针对上诉条目做局部重审，输出"二审备忘录"格式。
不接受无理由的全文重跑。若上诉未指明条目或未提供新证据/异议理由，按协议拒绝受理。
"""


FACT_CHECK_TRIGGER_PATTERNS = [
    r"已证实", r"已证伪", r"存疑", r"无法核实",
    r"声称", r"据[报道说]", r"数据[显示表明]", r"研究[显示表明]",
    r"\d{4}年", r"\d+%",
    r"复现", r"撤稿", r"诺贝尔", r"实验", r"研究",
    r"报道", r"声明", r"政策", r"法规", r"统计",
    r"证实", r"证伪", r"反驳", r"虚假",
]


def _needs_fact_check(verdict_or_dialogue: str) -> bool:
    """启发式：判断是否需要触发联网检索。"""
    return any(re.search(p, verdict_or_dialogue) for p in FACT_CHECK_TRIGGER_PATTERNS)


QUERY_EXTRACTION_PROMPT = """从下面这段网络争议对话中，抽取 1-3 个最适合用于联网检索的事实性查询词。

要求：
1. 抽取具体的事实实体：人名+事件、赛事名+年份、机构+决策、政策名+日期等。
2. 避免抽象词（如"事件""实验"等单独词），优先具体组合（如"阿根廷 vs 埃及 2026 世界杯""LK-99 复现""阿波罗登月 阴谋论"）。
3. 若对话仅含价值偏好/生活琐事（如"粽子甜咸"），返回空数组。
4. 严格输出 JSON：{{"queries": ["query1", "query2"]}}，不要其他解释。

=== 对话原文 ===
{dialogue}
"""


async def _llm_extract_queries(dialogue: str) -> list[str]:
    """用 LLM 抽取 1-3 个检索查询词（替代正则，更精准）。

    使用 DeepSeek-V3.2-Instruct（1.5s 快速），不用 GLM-5-Turbo（65s 慢，疑似走 reasoning）。
    """
    from app.core.llm import chat_completion
    prompt = QUERY_EXTRACTION_PROMPT.format(dialogue=dialogue[:3000])
    try:
        raw = await chat_completion(
            system_prompt="你是一个事实查询词抽取器。只输出JSON，不要其他文字。",
            user_msg=prompt,
            model="DeepSeek-V3.2-Instruct",
            max_tokens=128,
            temperature=0.1,
        )
        m = re.search(r'\{[\s\S]*\}', raw)
        if not m:
            return []
        data = json.loads(m.group(0))
        queries = [q.strip() for q in data.get("queries", []) if q and q.strip()]
        return queries[:3]
    except Exception as exc:
        print(f"[pipeline] LLM extract queries failed: {exc}", flush=True)
        return _extract_search_queries_legacy(dialogue)


def _extract_search_queries_legacy(dialogue: str) -> list[str]:
    """正则兜底：当 LLM 抽取失败时使用。"""
    queries: list[str] = []
    for m in re.finditer(r"([\u4e00-\u9fa5a-zA-Z]{2,30}(?:事件|实验|复现|数据|研究|声明|政策|法规))", dialogue):
        q = m.group(1).strip()
        if q and q not in queries:
            queries.append(q)
    return queries[:3]


async def adjudicate(
    dialogue: str | None = None,
    images: list[bytes] | None = None,
) -> dict[str, Any]:
    """主裁决流程。

    输入：对话文本（可空）+ 截图列表（可空），至少一项。
    输出：{session_id, dialogue_used, verdict, search_used, notes}
    """
    import asyncio as _asyncio
    import time as _time
    import sys

    def log(msg: str) -> None:
        print(f"[pipeline {_time.strftime('%H:%M:%S')}] {msg}", file=sys.stdout, flush=True)

    if not dialogue and not images:
        return {"error": "必须提供对话文本或截图"}

    log(f"start adjudicate: dialogue={len(dialogue or '')} chars, images={len(images or [])}")
    t0 = _time.time()

    system_prompt = get_system_prompt()
    search_used = False
    search_context = ""

    # OCR 阶段（带超时，避免卡死）
    if images and not dialogue:
        log("OCR stage start (images only)")
        try:
            ocr_result = await _asyncio.wait_for(ocr_images(images), timeout=180)
            dialogue = format_dialogue_text(ocr_result)
            log(f"OCR done in {_time.time()-t0:.1f}s, dialogue={len(dialogue)} chars")
        except _asyncio.TimeoutError:
            log(f"OCR TIMEOUT after {_time.time()-t0:.1f}s")
            return {"error": "截图 OCR 超时（180s），请尝试更清晰的截图或改用文本粘贴"}
        except Exception as exc:
            log(f"OCR FAIL: {type(exc).__name__}: {exc}")
            return {"error": f"截图 OCR 失败：{type(exc).__name__}: {exc}"}
    elif images and dialogue:
        log("OCR stage start (images + text)")
        try:
            ocr_result = await _asyncio.wait_for(ocr_images(images), timeout=180)
            ocr_text = format_dialogue_text(ocr_result)
            dialogue = f"{dialogue}\n\n=== 截图识别补充 ===\n{ocr_text}"
            log(f"OCR done in {_time.time()-t0:.1f}s, dialogue={len(dialogue)} chars")
        except _asyncio.TimeoutError:
            log(f"OCR timeout, continue with text only")
        except Exception as exc:
            log(f"OCR failed: {exc}, continue with text only")

    t1 = _time.time()
    user_msg = ADJUDICATE_USER_PROMPT.format(dialogue=dialogue)
    log(f"user_msg built: {len(user_msg)} chars")

    # 联网检索阶段（LLM 抽词 + 并发搜索，带超时）
    if _needs_fact_check(dialogue):
        log("fact-check stage start")
        try:
            queries = await _asyncio.wait_for(_llm_extract_queries(dialogue), timeout=30)
            log(f"extract queries done in {_time.time()-t1:.1f}s: {queries}")
            if queries:
                tasks = [search(q, max_results=3) for q in queries]
                search_results_list = await _asyncio.wait_for(
                    _asyncio.gather(*tasks, return_exceptions=True),
                    timeout=60,
                )
                search_results = [r for r in search_results_list if isinstance(r, dict)]
                log(f"search done in {_time.time()-t1:.1f}s, {len(search_results)} results")
                if search_results:
                    search_used = True
                    search_context = format_search_results(search_results)
                    user_msg += f"\n\n=== 联网检索补充 ===\n{search_context}"
        except _asyncio.TimeoutError:
            log("search stage timeout, continue without search")
        except Exception as exc:
            log(f"search failed: {exc}")

    t2 = _time.time()
    log(f"main verdict stage start, total user_msg={len(user_msg)} chars")

    # 主裁决（带超时）
    # GLM-4-Plus 非 reasoning 模型，30-60s 完成；给 180s 兜底
    verdict = ""
    for attempt in range(3):
        try:
            verdict = await _asyncio.wait_for(
                chat_completion(system_prompt, user_msg),
                timeout=180,
            )
            log(f"main verdict attempt {attempt+1} done in {_time.time()-t2:.1f}s, verdict={len(verdict)} chars")
            if verdict.strip():
                break
            log(f"verdict empty, retrying (attempt {attempt+1}/3)")
        except _asyncio.TimeoutError:
            log(f"main verdict attempt {attempt+1} TIMEOUT after {_time.time()-t2:.1f}s")
            if attempt < 2:
                t2 = _time.time()
                continue
            return {"error": "主裁决生成超时（180s）。建议：1) 简化对话内容 2) 减少截图数量 3) 稍后重试"}

    if not verdict.strip():
        return {"error": "主裁决返回空内容（模型可能因 max_tokens 不足或内容过滤未输出）。建议：1) 简化对话内容 2) 稍后重试"}

    session = get_session_store().create(dialogue=dialogue, verdict=verdict)

    return {
        "session_id": session.session_id,
        "dialogue_used": dialogue,
        "verdict": verdict,
        "search_used": search_used,
        "notes": "若 search_used=True，事实结论附信源；否则仅基于模型训练知识。" if not search_used else "已注入 Tavily 检索结果。",
    }


async def appeal(
    session_id: str,
    appealed_section: str,
    appeal_reason: str,
) -> dict[str, Any]:
    """上诉流程：局部重审，输出二审备忘录。"""
    store = get_session_store()
    session = store.get(session_id)
    if session is None:
        return {"error": f"session_id {session_id} 不存在或已过期"}

    if not appealed_section.strip():
        return {"error": "上诉须指明不服的具体结论条目。请补充条目编号。"}
    if not appeal_reason.strip():
        return {"error": "上诉须提供新证据或具体异议理由。无理由重审不予受理。"}

    system_prompt = get_system_prompt()
    user_msg = APPEAL_USER_PROMPT.format(
        verdict=session.verdict,
        appealed_section=appealed_section,
        appeal_reason=appeal_reason,
    )

    second_verdict = await chat_completion(system_prompt, user_msg)

    appeal_record = {
        "appealed_section": appealed_section,
        "appeal_reason": appeal_reason,
        "second_verdict": second_verdict,
    }
    store.append_appeal(session_id, appeal_record)

    return {
        "session_id": session_id,
        "appealed_section": appealed_section,
        "second_verdict": second_verdict,
    }


REPLY_SCRIPT_OPT_IN_PROMPT = """以下是用户已确认 opt-in 的应答话术请求。

对应原争议：
{dialogue}

对应原裁决报告：
{verdict}

用户请求的风格：{style}
用户的额外说明：{extra}

请依据 knowledge/response_script_guardrails.md 生成应答话术：
- 必须基于裁决报告中"已证实"的事实。
- 单次 ≤ 300 字。
- 不评价对方人格。
- 拒绝清单内容（人身攻击/人肉/煽动/欺骗/情绪操纵/法律风险/针对未成年人）任何情况不生成。
"""


REPLY_SCRIPT_GENERATE_PROMPT = """以下是用户已确认 opt-in 的应答话术请求。

=== 原争议对话 ===
{dialogue}

=== 原裁决报告 ===
{verdict}

=== 用户选择的话术风格 ===
{style}

=== 用户额外说明 ===
{extra}

请依据 knowledge/response_script_guardrails.md 生成应答话术。要求：
- 只用裁决报告"四、事实核查表"中标"已证实"的事实。
- 单次生成 ≤ 300 字。
- 不评价对方人格，不预测对方反应，不诱导转发。
- 若用户请求的内容触发拒绝清单，直接拒绝并说明原因。
"""


async def reply_script(
    session_id: str,
    style: str,
    extra: str = "",
) -> dict[str, Any]:
    """应答话术生成（须先 opt-in）。"""
    store = get_session_store()
    session = store.get(session_id)
    if session is None:
        return {"error": f"session_id {session_id} 不存在或已过期"}
    if not session.reply_script_opted_in:
        return {"error": "请先发起 opt-in 确认（POST /v1/reply-script/opt-in）。"}

    system_prompt = get_system_prompt()
    user_msg = REPLY_SCRIPT_GENERATE_PROMPT.format(
        dialogue=session.dialogue,
        verdict=session.verdict,
        style=style,
        extra=extra or "(无)",
    )
    script = await chat_completion(system_prompt, user_msg, max_tokens=1024)
    return {"session_id": session_id, "style": style, "script": script}
