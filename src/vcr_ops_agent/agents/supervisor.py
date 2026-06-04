"""Supervisor — 规则路由，不调 LLM（ADR-004）

运行流: START → supervisor → inspection → supervisor →（异常则）analytics → supervisor → END
"""

from __future__ import annotations

from typing import Any

from vcr_ops_agent.agents.base import BaseAgent
from vcr_ops_agent.state import Decision, OpsState, TaskStatus


class SupervisorAgent(BaseAgent):
    name = "supervisor"
    domain = "orchestration"

    async def run(self, state: OpsState, **kwargs: Any) -> dict:
        decisions: list[Decision] = []
        next_agent = state.next

        # 规则路由逻辑
        if next_agent == "supervisor":
            next_agent = self._route(state)

        decisions.append(Decision(
            agent=self.name,
            action="route",
            reasoning=f"路由决策: 下一跳 → {next_agent}",
            confidence=1.0,
        ))

        status = TaskStatus.COMPLETED if next_agent == "end" else TaskStatus.RUNNING
        return {"decisions": decisions, "next": next_agent, "status": status}

    def _route(self, state: OpsState) -> str:
        if state.status == TaskStatus.PENDING:
            return "inspection"

        has_anomaly = any(
            f.severity in ("warning", "high", "critical") for f in state.findings
        )
        inspection_done = state.inspection_steps > 0

        if inspection_done and has_anomaly and not state.recommendation:
            return "analytics"

        if state.recommendation:
            return "end"

        if state.inspection_steps >= state.max_steps:
            return "end"

        return "end"