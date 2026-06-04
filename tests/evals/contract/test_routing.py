"""Layer 1 — 契约测试：规则驱动骨架，fake 模式，pytest，CI gate 100%

只测确定性行为（路由、状态流转、字段填充），不依赖 LLM 判断。
"""

import os
import asyncio

import pytest

os.environ["VCR_OPS_FAKE_MODE"] = "true"

from vcr_ops_agent.graph import compile_graph
from vcr_ops_agent.simulator import setup_scenario
from vcr_ops_agent.state import OpsState, TaskStatus
from vcr_ops_agent.agents.analytics import AnalyticsAgent
from vcr_ops_agent.tracing import Tracer


@pytest.fixture(autouse=True)
def clean():
    Tracer.clear()
    yield
    Tracer.clear()


# ─── 巡检路由契约 ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_healthy_platform_no_escalation():
    """seed=100: 健康≥80 → has_anomaly=False, next=supervisor, focus_room is None"""
    setup_scenario(100)
    state = OpsState(task="contract_test")
    app = compile_graph()
    result = await app.ainvoke(state)

    assert result["status"] in (TaskStatus.COMPLETED, TaskStatus.COMPLETED.value, "completed")
    assert result.get("focus_room") is None
    # 不应有 warning/high/critical 级别 finding
    high_findings = [f for f in result.get("findings", []) if f.severity in ("warning", "high", "critical")]
    assert len(high_findings) == 0
    # recommendation 不应存在（没走到 analytics）
    assert result.get("recommendation") is None


@pytest.mark.asyncio
async def test_unhealthy_with_alerts_escalates_to_analytics():
    """seed=15: 健康<80 + 有告警 → next=analytics, focus_room 已设"""
    setup_scenario(15)
    state = OpsState(task="contract_test")
    app = compile_graph()
    result = await app.ainvoke(state)

    assert result.get("focus_room") is not None
    # 应有 recommendation（走完了 analytics）
    assert result.get("recommendation") is not None
    # 应有 anomaly_confirmed 决策
    actions = {d.action for d in result.get("decisions", [])}
    assert "anomaly_confirmed" in actions


@pytest.mark.asyncio
async def test_unhealthy_no_alerts_no_escalation():
    """seed=2: 健康<80 + 无告警 → 不升级, focus_room is None"""
    setup_scenario(2)
    state = OpsState(task="contract_test")
    app = compile_graph()
    result = await app.ainvoke(state)

    assert result.get("focus_room") is None
    assert result.get("recommendation") is None


@pytest.mark.asyncio
async def test_analytics_no_focus_room_rejects():
    """analytics 无 focus_room → action="no_target", 无 recommendation"""
    setup_scenario(42)
    agent = AnalyticsAgent()
    state = OpsState(task="contract_test", focus_room=None, inspection_steps=3)

    result = await agent.run(state)

    actions = {d.action for d in result.get("decisions", [])}
    assert "no_target" in actions
    assert result.get("recommendation") is None


@pytest.mark.asyncio
async def test_analytics_multi_round_steps_increment():
    """analytics 多轮: analytics_steps > 1"""
    setup_scenario(7)
    agent = AnalyticsAgent()
    state = OpsState(task="contract_test", focus_room="room_002", inspection_steps=3)

    current = state
    max_loops = 6
    for _ in range(max_loops):
        result = await agent.run(current)
        data = current.model_dump()
        data["findings"] = (
            [f.model_dump() for f in current.findings]
            + [f.model_dump() if hasattr(f, "model_dump") else f for f in result.get("findings", [])]
        )
        data["decisions"] = (
            [d.model_dump() for d in current.decisions]
            + [d.model_dump() if hasattr(d, "model_dump") else d for d in result.get("decisions", [])]
        )
        for k, v in result.items():
            if k not in ("findings", "decisions"):
                data[k] = v
        current = OpsState(**data)
        if result.get("next") != "analytics":
            break

    assert current.analytics_steps > 1
    assert len(current.analytics_hypotheses) > 0