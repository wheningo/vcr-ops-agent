"""LLM 客户端封装 — 统一调用入口，支持结构化输出"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from vcr_ops_agent.config import settings
from vcr_ops_agent.tracing import Tracer

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """封装 LangChain ChatAnthropic 调用，带 tracing 和结构化输出。"""

    _instance: LLMClient | None = None
    _chat_model: Any = None

    @classmethod
    def get(cls) -> LLMClient:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self) -> None:
        if settings.use_llm and settings.anthropic_api_key:
            from langchain_anthropic import ChatAnthropic

            self._chat_model = ChatAnthropic(
                model=settings.model,
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url or None,
                max_tokens=settings.max_tokens,
                temperature=settings.temperature,
            )

    @property
    def available(self) -> bool:
        return self._chat_model is not None

    async def invoke(
        self,
        messages: list[dict[str, str]],
        trace_id: str = "",
        span_name: str = "llm_call",
    ) -> str:
        if not self.available:
            return ""

        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = []
        for m in messages:
            if m["role"] == "system":
                lc_messages.append(SystemMessage(content=m["content"]))
            else:
                lc_messages.append(HumanMessage(content=m["content"]))

        with Tracer.span(trace_id, span_name) as span:
            response = await self._chat_model.ainvoke(lc_messages)
            span.metadata["model"] = settings.model

            if hasattr(response, "usage_metadata") and response.usage_metadata:
                usage = response.usage_metadata
                input_tokens = usage.get("input_tokens", 0)
                output_tokens = usage.get("output_tokens", 0)
                span.metadata["input_tokens"] = input_tokens
                span.metadata["output_tokens"] = output_tokens
                trace = Tracer.get_or_create(trace_id)
                trace.record_tokens(input_tokens, output_tokens)

            return response.content

    async def invoke_structured(
        self,
        messages: list[dict[str, str]],
        output_schema: type[T],
        trace_id: str = "",
        span_name: str = "llm_structured",
    ) -> T | None:
        if not self.available:
            return None

        from langchain_core.messages import HumanMessage, SystemMessage

        lc_messages = []
        for m in messages:
            if m["role"] == "system":
                lc_messages.append(SystemMessage(content=m["content"]))
            else:
                lc_messages.append(HumanMessage(content=m["content"]))

        with Tracer.span(trace_id, span_name) as span:
            structured_model = self._chat_model.with_structured_output(output_schema)
            response = await structured_model.ainvoke(lc_messages)
            span.metadata["model"] = settings.model
            span.metadata["schema"] = output_schema.__name__
            return response
