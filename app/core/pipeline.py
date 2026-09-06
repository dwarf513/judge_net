"""主流水线：编排 OCR → 分割 → LLM 三层分析 → 裁决报告生成。

对应 system_prompt.md 的全流程指令。
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.llm import chat_completion, chat_completion_stream
from app.core.ocr import format_dialogue_text, ocr_images
from app.core.prompt_builder import get_system_prompt
from app.core.search import format_search_results, search
from app.core.session import get_session_store
from app.core.url_fetcher import fetch_url_content, format_url_content


ADJUDICATE_USER_PROMPT = """请对以下网络对话做出裁决，严格按 system_prompt.md 中规定的 12 节裁决报告格式输出。

**【第零步：完整提取用户名清单（必须先做，不可跳过）】**
在分析任何内容之前，你必须先从头到尾扫描整个对话，**逐条列出所有出现过的不同用户名/昵称**。要求：
1. 逐条扫描，每遇到一个新用户名就记录。
2. 统计每位用户名的发言条数。
3. 检查清单完整性：对话中每一个发言标记都必须对应清单中的某个人。
4. **禁止捏造清单中不存在的用户名**——你后文引用的每一位发言方，必须来自这份清单。
5. **禁止遗漏**——对话中出现 ≥2 次的用户名，遗漏即是严重错误。

**【第一步：逐条归属发言】**
对清单中的每位用户，逐条确认哪些发言属于他/她。特别注意：
1. 嵌套回复的引用前缀（如"用户甲：用户乙：内容"）——"用户甲"是当前发言者，他引用了"用户乙"之前的话，冒号后的内容是"用户甲"的发言。
2. 被引用的部分不是被引用者的新发言——不要重复计数。
3. 回复关系：谁在回复谁、谁支持谁、谁反对谁。

**【第二步：输出结构表】**
在报告"一、争议主题与背景"的"对话结构复述"小节，输出如下表格：

| 发言方 | 发言条数 | 核心立场（一句话） | 代表性原话摘录 |
|---|---|---|---|
| @用户名A | N 条 | ... | "..." |
| @用户名B | N 条 | ... | "..." |

表格下方补充一行"回复关系"说明（谁与谁对立、谁围观）。

**如果对话结构有误，一切分析都会崩塌。宁可慢，不可错位，不可遗漏，不可捏造。**

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

请依据 knowledge/appeal_protocol.md 的协议，执行以下两步：

## 第一步：二审备忘录
针对上诉条目做局部重审，输出"二审备忘录"：
- 上诉条目
- 上诉理由
- 二审结论（维持原判 / 改判 / 仍存疑）
- 二审理由
- 对原裁决报告的影响

## 第二步：整体修正报告（若改判）
若二审结论为"改判"，在二审备忘录之后，输出**完整的修正后裁决报告**（12 节全量），在改动的条目处用 `**[二审修正]**` 标注。这样用户拿到的是一份完整可用的更新版报告，而非残缺的局部修改。

若二审结论为"维持原判"或"仍存疑"，不输出完整报告，仅在备忘录中说明。

不接受无理由的全文重跑。若上诉未指明条目或未提供新证据/异议理由，按协议拒绝受理。
"""


FACT_CHECK_TRIGGER_PATTERNS = [
    r"已证实", r"已证伪", r"存疑", r"无法核实",
    r"声称", r"据[报道说]", r"数据[显示表明]", r"研究[显示表明]",
    r"\d{4}年", r"\d+%",
    r"复现", r"撤稿", r"诺贝尔", r"实验", r"研究",
    r"报道", r"声明", r"政策", r"法规", r"统计",
    r"证实", r"证伪", r"反驳", r"虚假",
    r"世界杯", r"奥运会", r"联赛", r"决赛", r"半决赛",
    r"裁判", r"判罚", r"犯规", r"黄牌", r"红牌", r"VAR",
    r"总统", r"总理", r"选举", r"法案",
    r"温度", r"超导", r"疫苗", r"病毒",
    r"历史", r"战争", r"条约",
    r"法院", r"判决", r"诉讼",
    r"CEO", r"公司", r"市值", r"财报",
]


def _needs_fact_check(verdict_or_dialogue: str) -> bool:
    """启发式：判断是否需要触发联网检索。"""
    return any(re.search(p, verdict_or_dialogue) for p in FACT_CHECK_TRIGGER_PATTERNS)


DIALOGUE_PARSE_PROMPT = """把下面这段格式混乱的网络对话，解析成清晰的"序号+用户名：内容"格式。

识别规则：
1. 用户名通常是单独一行的短文本（2-15字符，不含句号问号等标点），可能含中文/日文/英文/混合字符。
2. 内容在用户名的下一行。日期（如2022-12-14 19:41）、纯数字（如167）、平台按钮文字（如"回复""赞"）不是内容，跳过。
3. "回复 @某某："中的"某某"是被回复者，不是当前发言者——当前发言者是这条消息的用户名。
4. **逐行扫描，不要遗漏任何发言方**。某人发3条就列3条。
5. **不要捏造**不存在的用户名。用户名拼写必须与原文完全一致。
6. 宁可多识别不可遗漏。

**完整性自检**：输出前，回头检查：
- 原文中出现了几个不同的用户名？你的统计列表中有几个？
- 如果原文有7个人但只列出了5个，说明遗漏了——回去补上。
- 特别检查长英文名或含特殊符号的用户名（如 muttttttghygbh、ーはじまりの未来ー）。

输出格式：
=== 格式化对话 ===
1. [用户名A]：[发言内容]
2. [用户名B]：[发言内容]
...

=== 发言方统计 ===
- [用户名A]：N 条
- [用户名B]：N 条

=== 待解析对话 ===
{dialogue}
"""


async def _parse_dialogue_structure(dialogue: str) -> str:
    """用快速模型把混乱的对话文本解析成清晰的格式化对话。

    返回格式化后的对话文本，供主裁决 LLM 使用。
    如果解析失败，返回原始对话。
    """
    from app.core.llm import chat_completion
    try:
        prompt = DIALOGUE_PARSE_PROMPT.format(dialogue=dialogue[:4000])
        result = await chat_completion(
            system_prompt="你是对话结构解析器。只输出格式化结果。",
            user_msg=prompt,
            model="DeepSeek-V3.2-Instruct",
            max_tokens=1024,
            temperature=0.1,
        )
        if result and "格式化对话" in result:
            return result
        return dialogue
    except Exception as exc:
        print(f"[pipeline] dialogue parse failed: {exc}", flush=True)
        return dialogue


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
    context_url: str | None = None,
) -> dict[str, Any]:
    """主裁决流程。

    输入：对话文本（可空）+ 截图列表（可空）+ 事件背景链接（可空），至少一项。
    输出：{session_id, dialogue_used, verdict, search_used, notes}
    """
    import asyncio as _asyncio
    import time as _time
    import sys

    def log(msg: str) -> None:
        print(f"[pipeline {_time.strftime('%H:%M:%S')}] {msg}", file=sys.stdout, flush=True)

    if not dialogue and not images:
        return {"error": "必须提供对话文本或截图"}

    log(f"start adjudicate: dialogue={len(dialogue or '')} chars, images={len(images or [])}, url={'yes' if context_url else 'no'}")
    t0 = _time.time()

    system_prompt = get_system_prompt()
    search_used = False
    search_context = ""

    # OCR 阶段（带超时，避免卡死）
    if images and not dialogue:
        log("OCR stage start (images only)")
        try:
            ocr_result = await _asyncio.wait_for(ocr_images(images), timeout=300)
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
            ocr_result = await _asyncio.wait_for(ocr_images(images), timeout=300)
            ocr_text = format_dialogue_text(ocr_result)
            dialogue = f"{dialogue}\n\n=== 截图识别补充 ===\n{ocr_text}"
            log(f"OCR done in {_time.time()-t0:.1f}s, dialogue={len(dialogue)} chars")
        except _asyncio.TimeoutError:
            log(f"OCR timeout, continue with text only")
        except Exception as exc:
            log(f"OCR failed: {exc}, continue with text only")

    # 对话结构解析（关键步骤：先格式化再裁决，避免人物错位）
    if dialogue and len(dialogue) > 100:
        log("dialogue structure parse start")
        try:
            parsed = await _asyncio.wait_for(_parse_dialogue_structure(dialogue), timeout=60)
            if parsed != dialogue and "格式化对话" in parsed:
                # 提取发言方统计输出到日志
                stats_lines = [line for line in parsed.split("\n") if "条" in line and "：" in line]
                log(f"dialogue parsed OK: {len(dialogue)} → {len(parsed)} chars")
                for sl in stats_lines[:10]:
                    log(f"  {sl.strip()}")
                dialogue = parsed
            else:
                log("dialogue parse returned no valid format, using original")
        except _asyncio.TimeoutError:
            log("dialogue parse timeout (60s), use original")
        except Exception as exc:
            log(f"dialogue parse failed: {exc}")

    t1 = _time.time()
    user_msg = ADJUDICATE_USER_PROMPT.format(dialogue=dialogue)
    log(f"user_msg built: {len(user_msg)} chars")

    # 用户提供的事件背景链接抓取
    if context_url:
        log(f"fetching context URL: {context_url[:80]}")
        try:
            url_result = await _asyncio.wait_for(fetch_url_content(context_url), timeout=20)
            if url_result.get("content"):
                url_text = format_url_content(url_result)
                user_msg += f"\n\n{url_text}"
                log(f"URL fetched: {len(url_result['content'])} chars, title={url_result.get('title','')[:50]}")
                # 基于抓取内容做拓展搜索，深挖事件背景
                title = url_result.get("title", "")
                if title:
                    log(f"expanding search based on URL title: {title[:60]}")
                    try:
                        expand_results = await _asyncio.wait_for(search(title, max_results=3), timeout=30)
                        if expand_results.get("results"):
                            expand_text = format_search_results([expand_results])
                            user_msg += f"\n\n=== 基于链接的拓展检索 ===\n{expand_text}"
                            search_used = True
                            log(f"expand search done: {len(expand_results.get('results',[]))} results")
                    except _asyncio.TimeoutError:
                        log("expand search timeout, continue without")
                    except Exception as exc:
                        log(f"expand search error: {exc}")
            else:
                log(f"URL fetch failed: {url_result.get('notes','')}")
        except _asyncio.TimeoutError:
            log("URL fetch timeout (20s), continue without")
        except Exception as exc:
            log(f"URL fetch error: {exc}")

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
    # 主模型 DeepSeek-V3.2-Instruct 30-60s；内容审核拦截时 fallback 到 GLM-5.2 需要 200-300s
    verdict = ""
    for attempt in range(3):
        try:
            verdict = await _asyncio.wait_for(
                chat_completion(system_prompt, user_msg),
                timeout=360,
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
            return {"error": "主裁决生成超时（360s）。建议：1) 简化对话内容 2) 减少截图数量 3) 稍后重试"}

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


async def adjudicate_stream(
    dialogue: str | None = None,
    images: list[bytes] | None = None,
    context_url: str | None = None,
):
    """流式主裁决。yield dict 事件。

    事件类型：
    - {"type": "stage", "stage": "ocr"} — 阶段开始
    - {"type": "stage", "stage": "parse"} — 对话结构解析
    - {"type": "stage", "stage": "search"} — 联网检索
    - {"type": "stage", "stage": "verdict"} — 主裁决开始
    - {"type": "chunk", "content": "..."} — 裁决文本片段
    - {"type": "done", "session_id": "...", "search_used": bool} — 完成
    - {"type": "error", "error": "..."} — 错误
    """
    import asyncio as _asyncio
    import time as _time
    import sys

    def log(msg: str) -> None:
        print(f"[pipeline {_time.strftime('%H:%M:%S')}] {msg}", file=sys.stdout, flush=True)

    if not dialogue and not images:
        yield {"type": "error", "error": "必须提供对话文本或截图"}
        return

    log(f"start adjudicate_stream: dialogue={len(dialogue or '')} chars, images={len(images or [])}")
    system_prompt = get_system_prompt()
    search_used = False

    # OCR 阶段
    if images and not dialogue:
        yield {"type": "stage", "stage": "ocr"}
        log("OCR stage start")
        try:
            ocr_result = await _asyncio.wait_for(ocr_images(images), timeout=300)
            dialogue = format_dialogue_text(ocr_result)
            log(f"OCR done, dialogue={len(dialogue)} chars")
        except _asyncio.TimeoutError:
            yield {"type": "error", "error": "截图 OCR 超时（180s），请尝试更清晰的截图或改用文本粘贴"}
            return
        except Exception as exc:
            log(f"OCR error: {type(exc).__name__}: {exc}")
            yield {"type": "error", "error": f"截图 OCR 失败（{type(exc).__name__}）：{exc}"}
            return
    elif images and dialogue:
        yield {"type": "stage", "stage": "ocr"}
        try:
            ocr_result = await _asyncio.wait_for(ocr_images(images), timeout=300)
            ocr_text = format_dialogue_text(ocr_result)
            dialogue = f"{dialogue}\n\n=== 截图识别补充 ===\n{ocr_text}"
        except _asyncio.TimeoutError:
            log("OCR timeout, continue with text only")
        except Exception as exc:
            log(f"OCR failed: {type(exc).__name__}: {exc}, continue with text only")

    # 对话结构解析
    if dialogue and len(dialogue) > 100:
        yield {"type": "stage", "stage": "parse"}
        log("dialogue structure parse start")
        try:
            parsed = await _asyncio.wait_for(_parse_dialogue_structure(dialogue), timeout=60)
            if parsed != dialogue and "格式化对话" in parsed:
                dialogue = parsed
                log("dialogue parsed OK")
        except Exception:
            log("dialogue parse failed, use original")

    user_msg = ADJUDICATE_USER_PROMPT.format(dialogue=dialogue)

    # URL 抓取
    if context_url:
        try:
            url_result = await _asyncio.wait_for(fetch_url_content(context_url), timeout=20)
            if url_result.get("content"):
                user_msg += f"\n\n{format_url_content(url_result)}"
                title = url_result.get("title", "")
                if title:
                    expand_results = await _asyncio.wait_for(search(title, max_results=3), timeout=30)
                    if expand_results.get("results"):
                        user_msg += f"\n\n=== 基于链接的拓展检索 ===\n{format_search_results([expand_results])}"
                        search_used = True
        except Exception:
            pass

    # 联网检索
    if _needs_fact_check(dialogue):
        yield {"type": "stage", "stage": "search"}
        log("fact-check stage start")
        try:
            queries = await _asyncio.wait_for(_llm_extract_queries(dialogue), timeout=30)
            if queries:
                tasks = [search(q, max_results=3) for q in queries]
                search_results_list = await _asyncio.wait_for(
                    _asyncio.gather(*tasks, return_exceptions=True), timeout=60
                )
                search_results = [r for r in search_results_list if isinstance(r, dict)]
                if search_results:
                    search_used = True
                    user_msg += f"\n\n=== 联网检索补充 ===\n{format_search_results(search_results)}"
        except Exception:
            log("search failed")

    # 主裁决流式
    yield {"type": "stage", "stage": "verdict"}
    log("main verdict stream start")

    full_verdict = ""
    try:
        async for chunk in chat_completion_stream(system_prompt, user_msg):
            full_verdict += chunk
            yield {"type": "chunk", "content": chunk}
    except Exception as exc:
        log(f"main verdict stream error: {exc}")
        yield {"type": "error", "error": f"主裁决生成失败：{exc}"}
        return

    if not full_verdict.strip():
        yield {"type": "error", "error": "主裁决返回空内容"}
        return

    session = get_session_store().create(dialogue=dialogue, verdict=full_verdict)
    log(f"main verdict stream done, verdict={len(full_verdict)} chars")

    yield {"type": "done", "session_id": session.session_id, "search_used": search_used}


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


REPLY_SCRIPT_ROUND1_PROMPT = """用户已确认 opt-in，请求第一轮应答话术。

=== 原争议对话 ===
{dialogue}

=== 原裁决报告 ===
{verdict}

=== 用户选择的话术风格 ===
{style}

=== 用户额外说明 ===
{extra}

请依据 knowledge/response_script_guardrails.md 的分步策略模式生成话术。

输出格式（必须包含两部分）：

【即时话术】（1-3 句，≤100 字）
[可直接发送的简短回复，有情商、不敏感、有尊严、点出对方缺陷]

【后续策略指引】
- 若对方[回应类型 A]：建议[策略 A]
- 若对方[回应类型 B]：建议[策略 B]
- 若对方[回避/拉黑/情绪升级]：建议[应对]

要求：
- 即时话术像发帖不像写信，不用"您"，用"你"。
- ≤100 字，长文=敏感。
- 有态度但不人身攻击。
- 只用裁决报告中"已证实"的事实。
- 若触发拒绝清单，直接拒绝。
"""


REPLY_SCRIPT_NEXT_ROUND_PROMPT = """用户已在进行多轮话术对话，现在请求下一轮。

=== 原争议对话 ===
{dialogue}

=== 原裁决报告 ===
{verdict}

=== 用户选择的话术风格 ===
{style}

=== 之前各轮话术历史 ===
{history}

=== 用户告知对方实际回复了什么 ===
{opponent_reply}

=== 用户额外说明 ===
{extra}

请依据 knowledge/response_script_guardrails.md 生成下一轮话术。

输出格式（同上，包含即时话术 + 后续策略指引两部分）。

要求：
- 记住上下文，不重复之前说过的话。
- 根据对方实际回复调整策略——对方认真回应就深化论证，对方人身攻击就降温退场。
- 即时话术 ≤100 字。
- 若对方已拉黑或停止回复，建议用户体面退出。
- 若已进行 3 轮以上且无效，强烈建议降温退场。
"""


async def reply_script(
    session_id: str,
    style: str,
    extra: str = "",
    opponent_reply: str = "",
    round_num: int = 1,
) -> dict[str, Any]:
    """应答话术生成（须先 opt-in）。支持多轮对话。"""
    store = get_session_store()
    session = store.get(session_id)
    if session is None:
        return {"error": f"session_id {session_id} 不存在或已过期"}
    if not session.reply_script_opted_in:
        return {"error": "请先发起 opt-in 确认（POST /v1/reply-script/opt-in）。"}

    system_prompt = get_system_prompt()

    if round_num <= 1 or not opponent_reply:
        prompt_template = REPLY_SCRIPT_ROUND1_PROMPT
        user_msg = prompt_template.format(
            dialogue=session.dialogue,
            verdict=session.verdict,
            style=style,
            extra=extra or "(无)",
        )
    else:
        history = getattr(session, "reply_script_history", []) or []
        history_text = ""
        for i, h in enumerate(history, 1):
            history_text += f"\n第{i}轮：\n  即时话术：{h.get('script','')}\n  对方回复：{h.get('opponent_reply','')}\n"
        user_msg = REPLY_SCRIPT_NEXT_ROUND_PROMPT.format(
            dialogue=session.dialogue,
            verdict=session.verdict,
            style=style,
            history=history_text or "(无历史)",
            opponent_reply=opponent_reply,
            extra=extra or "(无)",
        )

    script = await chat_completion(system_prompt, user_msg, max_tokens=1024)

    if not hasattr(session, "reply_script_history"):
        session.reply_script_history = []
    session.reply_script_history.append({
        "round": round_num,
        "style": style,
        "script": script,
        "opponent_reply": opponent_reply,
        "extra": extra,
    })

    return {
        "session_id": session_id,
        "style": style,
        "round": round_num,
        "script": script,
        "total_rounds": len(session.reply_script_history),
    }
