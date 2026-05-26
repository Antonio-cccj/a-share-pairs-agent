"""Rule-based MockLLM provider.

This is the default provider when ``LLM_PROVIDER=mock`` (also used in CI).
It implements just enough heuristics to make the **event classification** and
**sentiment extraction** prompts produce sensible outputs without any network
calls.

The heuristics are intentionally crude - they are not meant to compete with a
real LLM, only to allow the rest of the pipeline (data flow, RAG, backtest,
risk overlay) to run end-to-end deterministically.
"""

from __future__ import annotations

import json
import re
from typing import Any

from core.llm.base import LLMMessage, LLMProvider

# Keyword -> event_type lookup aligned with agents/event_taxonomy.yaml.
# Tried in order; first match wins.
_EVENT_KEYWORDS: list[tuple[str, list[str]]] = [
    ("fraud_investigation", ["立案", "证监会立案", "信息披露违法", "财务造假", "稽查"]),
    ("suspension", ["停牌", "暂停交易", "暂停上市"]),
    ("restructure", ["重大资产重组", "重组", "购买资产", "出售资产", "借壳"]),
    ("private_placement", ["定增", "非公开发行", "定向增发", "募集资金"]),
    ("earnings_warning", ["业绩预告", "净利润同比下降", "预亏", "扭亏", "业绩快报"]),
    ("shareholder_reduction", ["减持", "拟减持", "股份减持"]),
    ("litigation", ["重大诉讼", "诉讼", "仲裁", "起诉"]),
    ("equity_change", ["实际控制人变更", "实控人变更", "控股股东变更", "股权变动"]),
]


_SENTIMENT_POSITIVE = ["增长", "提升", "向好", "超预期", "买入", "推荐", "强烈推荐", "上调"]
_SENTIMENT_NEGATIVE = ["下滑", "下降", "低于预期", "卖出", "下调", "亏损", "减持"]


class MockLLM(LLMProvider):
    """Deterministic rule-based provider used when no API key is supplied."""

    name = "mock"

    def __init__(
        self, model: str = "mock-rule-v1", temperature: float = 0.0, max_tokens: int = 1024
    ) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens)

    def chat(self, messages: list[LLMMessage], **kwargs: Any) -> str:
        """Inspect the user prompt and reply with a routed JSON answer.

        Supported routes
        ----------------
        1. ``classify_event``    - returns ``{event_type, severity, rationale, confidence}``.
        2. ``extract_sentiment`` - returns ``{sentiment, score, summary}``.
        3. Generic ``{}`` otherwise so callers can detect "no useful info".
        """
        body = "\n".join(m.content for m in messages if m.role == "user")
        sys_prompt = "\n".join(m.content for m in messages if m.role == "system")

        if "classify_event" in sys_prompt or "event_type" in body:
            return json.dumps(self._classify_event(body), ensure_ascii=False)
        if "sentiment" in sys_prompt.lower() or "情绪" in body or "盈利预期" in body:
            return json.dumps(self._extract_sentiment(body), ensure_ascii=False)
        # Fallback: echo a non-empty JSON to keep extract_json happy.
        return json.dumps({"ok": True, "note": "mock provider"}, ensure_ascii=False)

    # ----------------------------------------------------------- internals
    @staticmethod
    def _classify_event(text: str) -> dict[str, Any]:
        for etype, keywords in _EVENT_KEYWORDS:
            if any(kw in text for kw in keywords):
                # Coarse severity: more keyword matches = higher score.
                sev = min(0.95, 0.4 + 0.1 * sum(kw in text for kw in keywords))
                return {
                    "event_type": etype,
                    "severity": round(sev, 2),
                    "rationale": f"keyword match on '{[kw for kw in keywords if kw in text][0]}'",
                    "confidence": 0.7,
                }
        return {
            "event_type": "other",
            "severity": 0.1,
            "rationale": "no risk keyword detected",
            "confidence": 0.5,
        }

    @staticmethod
    def _extract_sentiment(text: str) -> dict[str, Any]:
        pos = sum(text.count(w) for w in _SENTIMENT_POSITIVE)
        neg = sum(text.count(w) for w in _SENTIMENT_NEGATIVE)
        score = 0.0 if pos + neg == 0 else (pos - neg) / (pos + neg)
        label = "positive" if score > 0.1 else ("negative" if score < -0.1 else "neutral")
        # Pull a short summary line for traceability.
        first_line = next((ln.strip() for ln in re.split(r"[\n。]", text) if ln.strip()), "")
        return {"sentiment": label, "score": round(score, 3), "summary": first_line[:80]}
