"""Tests for the mock LLM event classifier."""

from __future__ import annotations

from core.llm import LLMMessage
from core.llm.mock_provider import MockLLM


def _classify(content: str) -> dict:
    llm = MockLLM()
    return llm.extract_json(
        [
            LLMMessage(
                "system",
                "你是 classify_event，输出 JSON {event_type, severity, rationale, confidence}",
            ),
            LLMMessage("user", content),
        ]
    )


def test_classifier_routes_suspension():
    out = _classify("公司股票自2023年起停牌，等待重大事项披露。")
    assert out["event_type"] == "suspension"
    assert out["severity"] >= 0.4


def test_classifier_routes_fraud():
    out = _classify("公司收到中国证监会立案告知书，涉嫌信息披露违法违规。")
    assert out["event_type"] == "fraud_investigation"
    assert out["severity"] >= 0.4


def test_classifier_routes_other_when_no_keyword():
    out = _classify("公司发布关于召开2024年第一次临时股东大会的通知。")
    assert out["event_type"] == "other"
