"""入口 — 离线 fake 模式跑通全链路"""

from __future__ import annotations

import asyncio

from vcr_ops_agent.graph import compile_graph
from vcr_ops_agent.simulator import setup_scenario
from vcr_ops_agent.state import OpsState
from vcr_ops_agent.tracing import Tracer


async def run_inspection_pipeline(scenario_seed: int = 7) -> dict:
    setup_scenario(scenario_seed)

    initial_state = OpsState(task="scheduled_inspection")
    app = compile_graph()

    final_state = await app.ainvoke(initial_state)

    trace_summary = Tracer.get_summary(initial_state.trace_id)
    return {
        "final_state": final_state,
        "trace": trace_summary,
    }


def main() -> None:
    result = asyncio.run(run_inspection_pipeline())

    print("=" * 60)
    print("巡检 → 根因分析 Pipeline 完成")
    print("=" * 60)

    state = result["final_state"]
    if isinstance(state, dict):
        print(f"\n状态: {state.get('status', 'unknown')}")
        print(f"焦点房间: {state.get('focus_room', '无')}")
        rec = state.get("recommendation")
        if rec:
            print(f"\n建议: {rec.get('summary', '') if isinstance(rec, dict) else rec.summary}")
            actions = rec.get("actions", []) if isinstance(rec, dict) else rec.actions
            for a in actions:
                print(f"  - {a}")
        print(f"\n发现数: {len(state.get('findings', []))}")
        print(f"决策数: {len(state.get('decisions', []))}")
    else:
        print(f"\n状态: {state.status}")
        print(f"焦点房间: {state.focus_room or '无'}")
        if state.recommendation:
            print(f"\n建议: {state.recommendation.summary}")
            for a in state.recommendation.actions:
                print(f"  - {a}")
        print(f"\n发现数: {len(state.findings)}")
        print(f"决策数: {len(state.decisions)}")

    print("\nTrace 摘要:")
    trace = result["trace"]
    print(f"  总 Span 数: {trace.get('total_spans', 0)}")
    print(f"  总耗时: {trace.get('total_duration_ms', 0):.1f} ms")


if __name__ == "__main__":
    main()