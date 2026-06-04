"""Agent 基类与注册表 — 按 domain 分组，支持分层就绪扩展（ADR-001）"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from vcr_ops_agent.state import OpsState


class BaseAgent(ABC):
    name: str = "base"
    domain: str = "default"

    @abstractmethod
    async def run(self, state: OpsState, **kwargs: Any) -> dict:
        """执行 Agent 逻辑，返回要合并到 state 的字段字典。"""
        ...


class AgentRegistry:
    """全局 Agent 注册表，按 domain 分组管理。"""

    _agents: dict[str, BaseAgent] = {}
    _domains: dict[str, list[str]] = {}

    @classmethod
    def register(cls, agent: BaseAgent) -> None:
        cls._agents[agent.name] = agent
        cls._domains.setdefault(agent.domain, []).append(agent.name)

    @classmethod
    def get(cls, name: str) -> BaseAgent:
        return cls._agents[name]

    @classmethod
    def list_by_domain(cls, domain: str) -> list[str]:
        return cls._domains.get(domain, [])

    @classmethod
    def all_names(cls) -> list[str]:
        return list(cls._agents.keys())

    @classmethod
    def clear(cls) -> None:
        cls._agents.clear()
        cls._domains.clear()
