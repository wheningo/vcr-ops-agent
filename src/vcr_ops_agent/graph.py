"""LangGraph 图定义 — Supervisor Loop 编排

START → supervisor → inspection → supervisor →（异常则）analytics → supervisor → END
"""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from vcr_ops_agent.agents.analytics import AnalyticsAgent
from vcr_ops_agent.agents.inspection import InspectionAgent
from vcr_ops_agent.agents.supervisor import SupervisorAgent
from vcr_ops_agent.state import OpsState
from vcr_ops_agent.tracing import Tracer


_supervisor = SupervisorAgent()
_inspection = InspectionAgent()
_analytics = AnalyticsAgent()


async def supervisor_node(state: OpsState) -> dict:
    with Tracer.span(state.trace_id, "supervisor"):
        return await _supervisor.run(state)


async def inspection_node(state: OpsState) -> dict:
    with Tracer.span(state.trace_id, "inspection"):
        return await _inspection.run(state)


async def analytics_node(state: OpsState) -> dict:
    with Tracer.span(state.trace_id, "analytics"):
        return await _analytics.run(state)


def _router(state: OpsState) -> str:
    next_val = state.next
    if next_val == "end":
        return END
    return next_val


def build_graph() -> StateGraph:
    graph = StateGraph(OpsState)

    graph.add_node("supervisor", supervisor_node)
    graph.add_node("inspection", inspection_node)
    graph.add_node("analytics", analytics_node)

    graph.set_entry_point("supervisor")

    graph.add_conditional_edges("supervisor", _router, {
        "inspection": "inspection",
        "analytics": "analytics",
        END: END,
    })
    graph.add_conditional_edges("inspection", _router, {
        "inspection": "inspection",
        "supervisor": "supervisor",
        "analytics": "analytics",
        END: END,
    })
    graph.add_conditional_edges("analytics", _router, {
        "analytics": "analytics",
        "supervisor": "supervisor",
        END: END,
    })

    return graph


def compile_graph():
    return build_graph().compile()
