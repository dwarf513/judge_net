"""judge_net 流水线单元测试。

只测试不依赖 LLM 调用的纯函数逻辑。
LLM 相关测试在 scripts/regression_test.py 中以 HTTP 集成测试形式覆盖。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from app.core.search import classify_tier
from app.core.segmentation import flag_unknown_speakers, merge_speaker_aliases
from app.core.ocr import format_dialogue_text, _extract_json
from app.core.pipeline import _extract_search_queries, _needs_fact_check
from app.core.session import SessionStore


class TestSourceClassification:
    def test_gov_domain_is_tier1(self):
        assert "Tier-1 政府官方" in classify_tier("https://www.stats.gov.cn/xxgk/sjdg/2024/")

    def test_international_org_is_tier1(self):
        assert "Tier-1 国际组织" in classify_tier("https://www.who.int/news")

    def test_academic_is_tier1(self):
        assert "Tier-1 学术同行评议" in classify_tier("https://www.nature.com/articles/xxx")

    def test_news_is_tier2(self):
        assert "Tier-2 主流媒体" in classify_tier("https://www.bbc.com/news/world")

    def test_wiki_is_tier2(self):
        assert "Tier-2 百科" in classify_tier("https://zh.wikipedia.org/wiki/LK-99")

    def test_unknown_is_tier3(self):
        assert classify_tier("https://some-blog.example.com/post") == "Tier-3 参考性信源"


class TestSegmentation:
    def test_merge_speaker_aliases(self):
        speakers = [
            {"id": "A", "name": "@用户A"},
            {"id": "B", "name": "@用户B"},
        ]
        result = merge_speaker_aliases(speakers)
        assert result == {"A": "@用户A", "B": "@用户B"}

    def test_flag_unknown_speakers_marks_empty(self):
        messages = [
            {"speaker_id": "", "text": "无归属消息"},
            {"speaker_id": "[归属不明]", "text": "另一段"},
            {"speaker_id": "A", "text": "已知归属"},
        ]
        flagged = flag_unknown_speakers(messages)
        assert flagged[0]["speaker_id"] == "?"
        assert flagged[0]["speaker_unknown"] is True
        assert flagged[1]["speaker_id"] == "?"
        assert flagged[1]["speaker_unknown"] is True
        assert flagged[2]["speaker_unknown"] is False


class TestOcrHelpers:
    def test_extract_json_plain(self):
        text = '{"speakers": [], "messages": [], "notes": "ok"}'
        result = _extract_json(text)
        assert result["notes"] == "ok"

    def test_extract_json_with_markdown_fence(self):
        text = '```json\n{"speakers": [], "messages": [], "notes": "fenced"}\n```'
        result = _extract_json(text)
        assert result["notes"] == "fenced"

    def test_extract_json_with_surrounding_text(self):
        text = '解析结果：\n{"speakers": [], "messages": [], "notes": "wrapped"}\n以上是结果'
        result = _extract_json(text)
        assert result["notes"] == "wrapped"

    def test_extract_json_failure_returns_notes(self):
        text = "完全不是 JSON"
        result = _extract_json(text)
        assert "JSON 解析失败" in result["notes"]

    def test_format_dialogue_text_orders_messages(self):
        ocr_result = {
            "speakers": [{"id": "A", "name": "@甲"}, {"id": "B", "name": "@乙"}],
            "messages": [
                {"speaker_id": "B", "text": "第二句", "order": 2},
                {"speaker_id": "A", "text": "第一句", "order": 1},
            ],
        }
        out = format_dialogue_text(ocr_result)
        assert out.index("第一句") < out.index("第二句")
        assert "@甲" in out
        assert "@乙" in out

    def test_format_dialogue_empty_returns_placeholder(self):
        out = format_dialogue_text({"speakers": [], "messages": []})
        assert "无识别到的对话内容" in out


class TestPipelineHelpers:
    def test_needs_fact_check_with_data_keywords(self):
        assert _needs_fact_check("据统计 2024年增长了 25%")
        assert _needs_fact_check("据报道某事件发生")
        assert _needs_fact_check("研究显示这个结论")

    def test_needs_fact_check_without_keywords(self):
        assert not _needs_fact_check("我觉得你说的不对")
        assert not _needs_fact_check("你说得真好")

    def test_extract_search_queries_returns_chinese_terms(self):
        dialogue = "关于登月实验复现的研究声明"
        queries = _extract_search_queries(dialogue)
        assert len(queries) > 0
        assert any("实验" in q or "研究" in q or "声明" in q for q in queries)

    def test_extract_search_queries_caps_at_three(self):
        dialogue = "事件A 实验 复现 数据 显示 研究 声明 政策"
        queries = _extract_search_queries(dialogue)
        assert len(queries) <= 3


class TestSessionStore:
    def test_create_and_get(self):
        store = SessionStore(ttl_seconds=60)
        s = store.create(dialogue="测试对话", verdict="测试裁决")
        assert s.session_id
        retrieved = store.get(s.session_id)
        assert retrieved is not None
        assert retrieved.dialogue == "测试对话"
        assert retrieved.verdict == "测试裁决"

    def test_get_nonexistent_returns_none(self):
        store = SessionStore(ttl_seconds=60)
        assert store.get("nonexistent-id") is None

    def test_update_verdict(self):
        store = SessionStore(ttl_seconds=60)
        s = store.create(dialogue="对话", verdict="")
        assert store.update_verdict(s.session_id, "新裁决")
        assert store.get(s.session_id).verdict == "新裁决"
        assert not store.update_verdict("nonexistent", "裁决")

    def test_append_appeal(self):
        store = SessionStore(ttl_seconds=60)
        s = store.create(dialogue="对话", verdict="裁决")
        record = {"appealed_section": "八、裁决结论", "second_verdict": "维持"}
        assert store.append_appeal(s.session_id, record)
        retrieved = store.get(s.session_id)
        assert len(retrieved.appeals) == 1
        assert retrieved.appeals[0]["second_verdict"] == "维持"

    def test_reply_script_opt_in(self):
        store = SessionStore(ttl_seconds=60)
        s = store.create(dialogue="对话", verdict="裁决")
        assert not s.reply_script_opted_in
        assert store.set_reply_script_opt_in(s.session_id, True)
        assert store.get(s.session_id).reply_script_opted_in is True
