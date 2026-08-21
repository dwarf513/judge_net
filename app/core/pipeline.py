"""主流水线：编排 OCR → 分割 → LLM 三层分析 → 裁决报告生成。

对应 system_prompt.md 的全流程指令。
"""
from __future__ import annotations

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
]


def _needs_fact_check(verdict_or_dialogue: str) -> bool:
    """启发式：判断是否需要触发联网检索。"""
    return any(re.search(p, verdict_or_dialogue) for p in FACT_CHECK_TRIGGER_PATTERNS)


def _extract_search_queries(dialogue: str) -> list[str]:
    """从对话中抽取候选检索查询（人名、事件、数据）。"""
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
    if not dialogue and not images:
        return {"error": "必须提供对话文本或截图"}

    system_prompt = get_system_prompt()
    search_used = False
    search_context = ""

    if images and not dialogue:
        ocr_result = await ocr_images(images)
        dialogue = format_dialogue_text(ocr_result)
    elif images and dialogue:
        ocr_result = await ocr_images(images)
        ocr_text = format_dialogue_text(ocr_result)
        dialogue = f"{dialogue}\n\n=== 截图识别补充 ===\n{ocr_text}"

    user_msg = ADJUDICATE_USER_PROMPT.format(dialogue=dialogue)

    if _needs_fact_check(dialogue):
        queries = _extract_search_queries(dialogue)
        if queries:
            search_results = await search(queries[0], max_results=5)
            search_used = True
            search_context = format_search_results([search_results])
            user_msg += f"\n\n=== 联网检索补充 ===\n{search_context}"

    verdict = await chat_completion(system_prompt, user_msg)

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
