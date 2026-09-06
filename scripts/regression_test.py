"""
regression_test.py — judge_net 金标准回归测试（HTTP 集成模式）

通过 HTTP POST 调用本地启动的 judge_net 服务（默认 http://localhost:7860），
对 5 个金标准案例跑 /v1/adjudicate，断言输出符合 expected_outputs/ 的关键判定。

与生产路径完全一致，避免"直接调 LLM 通过但 HTTP 不通"的偏差。

前置条件：
    1. 服务已启动：uvicorn app.main:app --port 7860
    2. .env 已配置 LLM_API_KEY（复用 ../scholar_agent/.env）

用法:
    python scripts/regression_test.py              # 跑全部
    python scripts/regression_test.py case_01      # 只跑指定案例
    python scripts/regression_test.py --report-only  # 仅从已有输出生成报告

输出:
    docs/regression_report.md        回归报告（生成物，已 .gitignore）
    docs/regression_outputs/          每案例原始输出（生成物，便于排查）

退出码: 0=全部通过, 1=有失败
"""

from __future__ import annotations

import datetime
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parent.parent
CASES_DIR = REPO_ROOT / "golden_cases"
OUTPUTS_DIR = REPO_ROOT / "docs" / "regression_outputs"
REPORT_PATH = REPO_ROOT / "docs" / "regression_report.md"

SERVICE_URL = os.environ.get("JUDGE_NET_URL", "http://localhost:7860")
HTTP_TIMEOUT = 300

TWELVE_SECTIONS = [
    "## 一、争议主题与背景",
    "## 二、冲突类型判定",
    "## 三、各方主张摘要",
    "## 四、事实核查表",
    "## 五、逻辑辨析",
    "## 六、情绪与修辞分析",
    "## 七、特殊情形提示",
    "## 八、裁决结论",
    "## 九、缺陷明细",
    "## 十、建设性建议",
    "## 十一、信心度与局限",
    "## 十二、上诉通道说明",
]


CASES: list[dict[str, Any]] = [
    {
        "id": "case_01",
        "file": "case_01_weibo_knowledge_debate.md",
        "platform": "微博",
        "type_label": "A 诚意知识争辩",
        "must_contain": [
            *TWELVE_SECTIONS,
            "对话结构复述",
            "A",
            "诚意知识争辩",
            "较正确一方",
            "凝聚态博士",
            "高",
            "同行评议",
            "撤稿",
        ],
        "must_not_contain": [
            "双方都有道理",
            "各有各的理",
        ],
    },
    {
        "id": "case_02",
        "file": "case_02_zhihu_accidental_quarrel.md",
        "platform": "知乎",
        "type_label": "B 偶发口角",
        "must_contain": [
            *TWELVE_SECTIONS,
            "对话结构复述",
            "B",
            "偶发口角",
            "价值分歧",
            "不裁决对错",
            "低",
            "羞辱嘲讽",
            "未识别到",
        ],
        "must_not_contain": [],
    },
    {
        "id": "case_03",
        "file": "case_03_bilibili_cib_water_army.md",
        "platform": "B 站",
        "type_label": "C CIB 协同造假",
        "must_contain": [
            *TWELVE_SECTIONS,
            "对话结构复述",
            "C",
            "CIB",
            "协同造假",
            "特殊情形",
            ["不作对错", "较正确一方"],
            "复制粘贴",
        ],
        "must_not_contain": [],
    },
    {
        "id": "case_04",
        "file": "case_04_reddit_conspiracy.md",
        "platform": "Reddit",
        "type_label": "E 阴谋论",
        "must_contain": [
            *TWELVE_SECTIONS,
            "对话结构复述",
            "E",
            "阴谋论",
            ["逐条证伪", "逐条反驳", "逐项证伪", "逐一证伪", "证伪"],
            ["Gish Gallop", "循环论证", "诉诸动机", "诉诸无知", "滔滔不绝"],
            "较正确一方",
            "SkepticBotanist",
            "高",
        ],
        "must_not_contain": [],
    },
    {
        "id": "case_05",
        "file": "case_05_xiaohongshu_ai_scam.md",
        "platform": "小红书",
        "type_label": "F 谣言/AI 骗局",
        "must_contain": [
            *TWELVE_SECTIONS,
            "对话结构复述",
            "F",
            ["疑似 AI 生成", "高度疑似"],
            "查无此",
            "较正确一方",
            "打假",
            "中",
            ["高度疑似", "疑似 AI"],
        ],
        "must_not_contain": [
            "已证实是 AI 生成",
            "这就是 AI 生成的",
        ],
    },
]


def _normalize(s: str) -> str:
    """去除引号与部分标点，使断言更宽容（如 '不作"对错"裁决' 可匹配 '不作对错'）。"""
    for ch in '""''「」『』""':
        s = s.replace(ch, "")
    return s


def extract_dialogue(case_path: Path) -> str:
    """从案例文件中提取 '## 对话原文' 与 '## 期望裁决要点' 之间的内容。"""
    text = case_path.read_text(encoding="utf-8")
    m = re.search(r"## 对话原文(.*?)## 期望裁决要点", text, re.DOTALL)
    if not m:
        print(f"[WARN] {case_path.name} 未找到对话原文段，退回整篇。", file=sys.stderr)
        return text
    return m.group(1).strip()


def call_adjudicate(dialogue: str, max_retries: int = 2) -> dict[str, Any]:
    """POST /v1/adjudicate，返回响应 JSON。"""
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=HTTP_TIMEOUT) as client:
                resp = client.post(
                    f"{SERVICE_URL}/v1/adjudicate",
                    data={"dialogue": dialogue},
                )
                resp.raise_for_status()
                return resp.json()
        except Exception as exc:
            last_err = exc
            wait = 5 * attempt
            print(f"  [retry {attempt}/{max_retries}] {type(exc).__name__}: {exc}; {wait}s 后重试", file=sys.stderr)
            time.sleep(wait)
    raise RuntimeError(f"HTTP 调用失败（重试 {max_retries} 次）: {last_err}")


def save_case_output(case_id: str, output: str) -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUTS_DIR / f"{case_id}.md").write_text(output, encoding="utf-8")


def run_assertions(case: dict[str, Any], output: str) -> tuple[bool, list[str], list[str]]:
    """must_contain 元素可为 str（精确子串匹配）或 list[str]（任一匹配即可）。"""
    norm_out = _normalize(output)
    missing: list[str] = []
    for kw in case["must_contain"]:
        opts = kw if isinstance(kw, list) else [kw]
        if not any(_normalize(opt) in norm_out for opt in opts):
            missing.append(" / ".join(opts))
    forbidden_hit: list[str] = []
    for kw in case["must_not_contain"]:
        if _normalize(kw) in norm_out:
            forbidden_hit.append(kw)
    return (not missing and not forbidden_hit, missing, forbidden_hit)


def check_global_assertions(results: list[dict[str, Any]]) -> list[str]:
    failures: list[str] = []
    has_correct_side = any("较正确一方" in _normalize(r["output"]) for r in results)
    if not has_correct_side:
        failures.append("全局断言失败：无任何案例出现'较正确一方'判定（疑似各打五十大板）")
    return failures


def write_report(
    results: list[dict[str, Any]],
    global_failures: list[str],
    elapsed: float,
) -> bool:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    all_pass = True
    lines: list[str] = []
    lines.append("# judge_net 金标准回归报告（HTTP 集成模式）\n")
    lines.append(f"- 生成时间：{datetime.datetime.now().isoformat(timespec='seconds')}")
    lines.append(f"- 服务地址：`{SERVICE_URL}`")
    lines.append(f"- 耗时：{elapsed:.1f}s")
    lines.append(f"- 案例数：{len(results)}")
    lines.append("")
    lines.append("## 总览\n")
    lines.append("| 案例 | 平台 | 类型 | 12 节标题 | 关键判定 | 禁止项 | 结果 |")
    lines.append("|---|---|---|---|---|---|---|")
    for r in results:
        sec_ok = all(_normalize(s) in _normalize(r["output"]) for s in TWELVE_SECTIONS)
        kw_ok = not r["missing"]
        forb_ok = not r["forbidden_hit"]
        case_pass = sec_ok and kw_ok and forb_ok
        all_pass = all_pass and case_pass
        lines.append(
            f"| {r['id']} | {r['platform']} | {r['type_label']} | "
            f"{'OK' if sec_ok else 'FAIL'} | {'OK' if kw_ok else 'FAIL'} | "
            f"{'OK' if forb_ok else 'FAIL'} | {'PASS' if case_pass else 'FAIL'} |"
        )
    if global_failures:
        all_pass = False
        lines.append("")
        lines.append("## 全局断言失败\n")
        for f in global_failures:
            lines.append(f"- {f}")
    lines.append("")
    for r in results:
        lines.append(f"## {r['id']} · {r['platform']} · {r['type_label']}\n")
        sec_ok = all(_normalize(s) in _normalize(r["output"]) for s in TWELVE_SECTIONS)
        lines.append(f"- 12 节标题完整：{'OK' if sec_ok else 'FAIL'}")
        lines.append(f"- search_used：{r.get('search_used', 'N/A')}")
        lines.append(f"- session_id：`{r.get('session_id', 'N/A')}`")
        lines.append(f"- 关键判定缺失项 ({len(r['missing'])})：")
        for m in r["missing"]:
            lines.append(f"  - `{m}`")
        lines.append(f"- 禁止项误出现 ({len(r['forbidden_hit'])})：")
        for f in r["forbidden_hit"]:
            lines.append(f"  - `{f}`")
        lines.append(f"- 原始输出：`docs/regression_outputs/{r['id']}.md`")
        lines.append("")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return all_pass


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--report-only"]
    report_only = "--report-only" in sys.argv
    only_case = args[0] if args else None
    if only_case:
        only_case = only_case.replace("case_", "").zfill(2)
        only_case = f"case_{only_case}" if only_case.isdigit() else sys.argv[1]
    print(f"[INFO] service_url={SERVICE_URL}")
    if only_case:
        print(f"[INFO] 仅运行：{only_case}")
    if report_only:
        print("[INFO] report-only 模式：从已有输出文件读取，不调用服务")

    if not report_only:
        try:
            with httpx.Client(timeout=10) as c:
                r = c.get(f"{SERVICE_URL}/healthz")
                r.raise_for_status()
                print(f"[INFO] service healthz: {r.json()}")
        except Exception as exc:
            print(f"[FATAL] 服务未启动或不可达：{exc}", file=sys.stderr)
            print("        请先执行：uvicorn app.main:app --port 7860", file=sys.stderr)
            return 2

    selected = CASES if not only_case else [c for c in CASES if c["id"] == only_case]
    if not selected:
        print(f"[FATAL] 未找到案例：{only_case}", file=sys.stderr)
        return 2

    results: list[dict[str, Any]] = []
    start = time.time()
    for case in selected:
        case_path = CASES_DIR / case["file"]
        if not case_path.exists():
            print(f"[FATAL] 案例文件不存在: {case_path}", file=sys.stderr)
            return 2
        dialogue = extract_dialogue(case_path)
        print(f"\n[CASE] {case['id']} {case['platform']} {case['type_label']}")
        print(f"  对话长度：{len(dialogue)} 字符")
        if report_only:
            out_path = OUTPUTS_DIR / f"{case['id']}.md"
            if not out_path.exists():
                print(f"  [ERROR] 输出文件不存在：{out_path}", file=sys.stderr)
                output = ""
                session_id = "N/A"
                search_used = False
            else:
                output = out_path.read_text(encoding="utf-8")
                print(f"  [report-only] 读取已有输出：{out_path}")
                session_id = "N/A"
                search_used = False
        else:
            try:
                data = call_adjudicate(dialogue)
                output = data.get("verdict", "")
                session_id = data.get("session_id", "")
                search_used = data.get("search_used", False)
                save_case_output(case["id"], output)
            except Exception as exc:
                print(f"  [ERROR] {exc}", file=sys.stderr)
                output = ""
                session_id = "N/A"
                search_used = False
        passed, missing, forbidden_hit = run_assertions(case, output)
        print(f"  输出长度：{len(output)} 字符")
        print(f"  session_id：{session_id}")
        print(f"  search_used：{search_used}")
        print(f"  12 节标题：{'OK' if all(_normalize(s) in _normalize(output) for s in TWELVE_SECTIONS) else 'FAIL'}")
        print(f"  关键判定缺失：{len(missing)} 项")
        for m in missing:
            print(f"    - {m}")
        print(f"  禁止项误出现：{len(forbidden_hit)} 项")
        for f in forbidden_hit:
            print(f"    - {f}")
        print(f"  结果：{'PASS' if passed else 'FAIL'}")
        results.append({
            "id": case["id"],
            "platform": case["platform"],
            "type_label": case["type_label"],
            "output": output,
            "session_id": session_id,
            "search_used": search_used,
            "missing": missing,
            "forbidden_hit": forbidden_hit,
            "passed": passed,
        })
    elapsed = time.time() - start

    global_failures = check_global_assertions(results)
    all_pass = write_report(results, global_failures, elapsed)
    print(f"\n[REPORT] {REPORT_PATH}")
    print(f"[RESULT] {'ALL PASS' if all_pass else 'HAS FAILURES'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
