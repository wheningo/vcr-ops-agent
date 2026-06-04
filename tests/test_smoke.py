"""Smoke test — 全链路离线跑通"""

import pytest

from vcr_ops_agent.graph import compile_graph
from vcr_ops_agent.simulator import setup_scenario
from vcr_ops_agent.state import OpsState, TaskStatus
from vcr_ops_agent.tracing import Tracer


@pytest.fixture(autouse=True)
def clean_tracer():
    Tracer.clear()
    yield
    Tracer.clear()


@pytest.mark.asyncio
async def test_full_pipeline_completes():
    setup_scenario(42)
    state = OpsState(task="scheduled_inspection")
    app = compile_graph()

    result = await app.ainvoke(state)

    assert result["status"] in (TaskStatus.COMPLETED, TaskStatus.COMPLETED.value, "completed")
    assert len(result.get("decisions", [])) > 0
    assert len(result.get("findings", [])) > 0


@pytest.mark.asyncio
async def test_pipeline_with_healthy_scenario():
    setup_scenario(100)
    state = OpsState(task="scheduled_inspection")
    app = compile_graph()

    result = await app.ainvoke(state)

    assert result["status"] in (TaskStatus.COMPLETED, TaskStatus.COMPLETED.value, "completed")


@pytest.mark.asyncio
async def test_tracing_captures_spans():
    setup_scenario(42)
    state = OpsState(task="scheduled_inspection")
    app = compile_graph()

    result = await app.ainvoke(state)

    trace_id = result.get("trace_id", state.trace_id)
    summary = Tracer.get_summary(trace_id)
    assert summary.get("total_spans", 0) > 0