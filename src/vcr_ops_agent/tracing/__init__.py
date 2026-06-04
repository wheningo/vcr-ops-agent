"""自建可观测 — 轻量 tracing（ADR-002）

每任务一个 trace_id，逐 span 记录耗时 / token / 成本 / 路由决策。
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

import structlog

logger = structlog.get_logger()


@dataclass
class Span:
    name: str
    trace_id: str
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_ms(self) -> float:
        if self.end_time is None:
            return 0.0
        return (self.end_time - self.start_time) * 1000

    def finish(self) -> None:
        self.end_time = time.time()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "trace_id": self.trace_id,
            "duration_ms": round(self.duration_ms, 2),
            "metadata": self.metadata,
        }


@dataclass
class Trace:
    trace_id: str
    spans: list[Span] = field(default_factory=list)
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0

    def add_span(self, span: Span) -> None:
        self.spans.append(span)

    def record_tokens(self, input_tokens: int = 0, output_tokens: int = 0) -> None:
        self.total_tokens += input_tokens + output_tokens
        self.estimated_cost_usd += (input_tokens * 3 + output_tokens * 15) / 1_000_000

    def summary(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_spans": len(self.spans),
            "total_duration_ms": round(sum(s.duration_ms for s in self.spans), 2),
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": round(self.estimated_cost_usd, 6),
            "spans": [s.to_dict() for s in self.spans],
        }


class Tracer:
    """全局 Tracer，管理当前活跃的 trace。"""

    _traces: dict[str, Trace] = {}

    @classmethod
    def get_or_create(cls, trace_id: str) -> Trace:
        if trace_id not in cls._traces:
            cls._traces[trace_id] = Trace(trace_id=trace_id)
        return cls._traces[trace_id]

    @classmethod
    @contextmanager
    def span(cls, trace_id: str, name: str, **metadata: Any) -> Generator[Span, None, None]:
        trace = cls.get_or_create(trace_id)
        s = Span(name=name, trace_id=trace_id, metadata=metadata)
        try:
            yield s
        finally:
            s.finish()
            trace.add_span(s)
            logger.info("span_finished", span=s.to_dict())

    @classmethod
    def get_summary(cls, trace_id: str) -> dict[str, Any]:
        trace = cls._traces.get(trace_id)
        if not trace:
            return {"error": "trace not found"}
        return trace.summary()

    @classmethod
    def clear(cls) -> None:
        cls._traces.clear()
