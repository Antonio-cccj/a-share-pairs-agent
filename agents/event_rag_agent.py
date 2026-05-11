"""Event RAG agent.

Pipeline
--------
1. Pull candidate announcements for a (ts_code, date-range) from the DB.
2. For each announcement, retrieve top-K similar items already classified (if any)
   from the Chroma collection as few-shot context.
3. Ask the LLM to classify the announcement into one of the 9 taxonomy keys
   defined in :file:`agents/event_taxonomy.yaml`, returning JSON.
4. Persist the structured result into the ``events`` table.

When ``LLM_PROVIDER=mock`` the provider applies keyword rules instead of
calling an external API; the rest of the pipeline behaves identically.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sqlalchemy import text

from core.data import IngestService
from core.llm import LLMMessage, build_llm
from core.logger import get_logger
from core.rag import ChromaStore

log = get_logger(__name__)


_TAXONOMY_PATH = Path(__file__).parent / "event_taxonomy.yaml"


@dataclass
class EventRecord:
    event_id: str
    ann_id: str
    ts_code: str
    event_date: str
    event_type: str
    severity: float
    rationale: str
    confidence: float
    model: str

    def as_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


class EventRAGAgent:
    """Classify announcements into the 9 risk-event types."""

    def __init__(
        self,
        ingest: IngestService | None = None,
        store: ChromaStore | None = None,
        llm: Any = None,
    ) -> None:
        self.ingest = ingest or IngestService()
        self.store = store or ChromaStore()
        self.llm = llm or build_llm()
        with _TAXONOMY_PATH.open(encoding="utf-8") as f:
            self.taxonomy = yaml.safe_load(f)["events"]

    # ----------------------------------------------------------- public API
    def classify(self, title: str, content: str, ts_code: str = "") -> EventRecord:
        """Classify a single announcement and return a structured record."""
        prompt_text = f"{title}\n{content}"
        # Retrieve similar examples (if any) for soft few-shot context.
        examples = self.store.query(prompt_text, top_k=3)
        ex_block = "\n\n".join(
            f"[示例] 标题: {e['text'][:80]}\n类别: {e['meta'].get('event_type', '?')}"
            for e in examples
            if e["meta"].get("event_type")
        )
        system = self._build_system_prompt()
        user = (
            f"待分类公告：\n标题：{title}\n正文：{content}\n\n"
            f"参考相似公告（若有）：\n{ex_block or '无'}\n\n"
            "请按 system 指令输出 JSON。"
        )
        messages = [LLMMessage("system", system), LLMMessage("user", user)]
        try:
            raw = self.llm.extract_json(messages)
        except Exception as e:
            log.warning("LLM JSON parse failed for {}: {}", ts_code, e)
            raw = {"event_type": "other", "severity": 0.1, "rationale": "parse_error", "confidence": 0.0}

        event_type = str(raw.get("event_type", "other"))
        if event_type not in self.taxonomy:
            event_type = "other"
        severity = float(raw.get("severity", self.taxonomy[event_type].get("severity", 0.1)))
        rationale = str(raw.get("rationale", ""))
        confidence = float(raw.get("confidence", 0.5))

        event_id = hashlib.sha1(
            f"{ts_code}|{title}|{event_type}".encode()
        ).hexdigest()[:16]
        return EventRecord(
            event_id=event_id,
            ann_id="",  # filled by run_batch
            ts_code=ts_code,
            event_date="",  # filled by run_batch
            event_type=event_type,
            severity=severity,
            rationale=rationale,
            confidence=confidence,
            model=f"{self.llm.name}:{self.llm.model}",
        )

    def run_batch(self, codes: list[str] | None = None, start: str | None = None, endd: str | None = None) -> int:
        """Classify every announcement in the date range and persist results."""
        anns = self.ingest.load_announcements(codes=codes, start=start, endd=endd)
        if anns.empty:
            log.warning("no announcements to classify")
            return 0
        records: list[dict] = []
        for _, row in anns.iterrows():
            rec = self.classify(
                title=str(row.get("title", "")),
                content=str(row.get("content", "")),
                ts_code=str(row.get("ts_code", "")),
            )
            rec.ann_id = str(row["ann_id"])
            rec.event_date = str(row["ann_date"])
            records.append(rec.as_dict())
        df = pd.DataFrame(records)
        with self.ingest.engine.begin() as conn:
            # Avoid duplicate primary keys on re-runs.
            for ev_id in df["event_id"].unique():
                conn.execute(text("DELETE FROM events WHERE event_id = :i"), {"i": ev_id})
            from core.data.ingest import _safe_chunksize

            df.to_sql(
                "events",
                conn,
                if_exists="append",
                index=False,
                method="multi",
                chunksize=_safe_chunksize(len(df.columns)),
            )
        log.info("classified & persisted {} events", len(df))
        return len(df)

    # --------------------------------------------------------- prompt helper
    def _build_system_prompt(self) -> str:
        """Compose a Chinese system prompt grounded in the taxonomy."""
        cat_lines = []
        for k, v in self.taxonomy.items():
            kws = "、".join(v.get("keywords", []))
            cat_lines.append(f"- {k} ({v['label']}, 严重度={v['severity']}, 关键词: {kws})")
        cats_block = "\n".join(cat_lines)
        return (
            "你是一名 A 股事件风控分析师，任务是 classify_event：\n"
            "把给定的上市公司公告归入下列 9 个类别之一，并输出 JSON。\n"
            f"类别清单：\n{cats_block}\n\n"
            "输出 JSON schema：\n"
            "{\n"
            '  "event_type": "<one of the keys above>",\n'
            '  "severity":   <float 0..1>,\n'
            '  "rationale":  "<one sentence>",\n'
            '  "confidence": <float 0..1>\n'
            "}\n"
            "若公告无明确风险信号，输出 event_type=other, severity 接近 0.1。"
        )
