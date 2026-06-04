"""Layer 2 — 质量 eval：真实 Claude，N 次重复抗非确定性，LLM-as-Judge 评分

运行方式: uv run python tests/evals/quality/run.py
需要: ANTHROPIC_API_KEY 环境变量
"""

from __future__ import annotations

import asyncio
import os
import statistics
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
os.environ.setdefault("VCR_OPS_FAKE_MODE", "false")

from vcr_ops_agent.graph import compile_graph
from vcr_ops_agent.simulator import setup_scenario
from vcr_ops_agent.state import OpsState
from vcr_ops_agent.tracing import Tracer

from tests.evals.quality.judge import judge_root_cause
from tests.evals.quality.score import ClsCounts

N = int(os.getenv("VCR_OPS_EVAL_N", "3"))


async def run_pipeline(case: dict) -> dict:
    """单次跑全链路或直接跑 analytics，返回结果字典。"""
    Tracer.clear()
    setup_scenario(case["seed"])

    if case.get("focus_room"):
        # analytics case: 直接跑 analytics agent 多轮，跳过巡检
        return await _run_analytics_direct(case)

    # 巡检 case: 走全图
    state = OpsState(task="quality_eval")
    app = compile_graph()
    result = await app.ainvoke(state)

    has_anomaly = any(
        f.severity in ("warning", "high", "critical")
        for f in result.get("findings", [])
    )
    rec = result.get("recommendation")
    root_cause = ""
    if rec:
        root_cause = rec.summary if hasattr(rec, "summary") else rec.get("summary", "")

    return {
        "has_anomaly": has_anomaly,
        "root_cause": root_cause,
        "focus_room": result.get("focus_room"),
    }


async def _run_analytics_direct(case: dict) -> dict:
    """直接跑 analytics agent 多轮，模拟巡检已完成移交的状态。"""
    from vcr_ops_agent.agents.analytics import AnalyticsAgent

    agent = AnalyticsAgent()
    state = OpsState(
        task="quality_eval",
        focus_room=case["focus_room"],
        inspection_steps=3,
        status="running",
    )

    current = state
    max_loops = 6
    final_result = {}
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
        final_result = result
        if result.get("next") != "analytics":
            break

    has_anomaly = any(
        f.severity in ("warning", "high", "critical")
        for f in current.findings
    )
    rec = final_result.get("recommendation")
    root_cause = ""
    if rec:
        root_cause = rec.summary if hasattr(rec, "summary") else rec.get("summary", "")

    return {
        "has_anomaly": has_anomaly,
        "root_cause": root_cause,
        "focus_room": current.focus_room,
    }


async def main():
    cases_path = Path(__file__).parent / "cases.yaml"
    with open(cases_path) as f:
        data = yaml.safe_load(f)

    cases = data.get("quality_cases", [])
    cls = ClsCounts()
    judge_scores: list[float] = []
    results_detail: list[dict] = []

    print("=" * 70)
    print(f"质量 Eval — 真实模式, N={N} 次/case")
    print("=" * 70)

    for case in cases:
        case_id = case["id"]
        expected_anomaly = case["expected_anomaly"]
        expected_category = case.get("expected_cause_category", "")
        difficulty = case.get("difficulty", "easy")

        print(f"\n[{case_id}] {case['name']} (difficulty={difficulty})")

        # 跑 N 次
        preds = []
        for i in range(N):
            try:
                pred = await run_pipeline(case)
                preds.append(pred)
                print(f"  run {i+1}/{N}: anomaly={pred['has_anomaly']}, root_cause={pred['root_cause'][:40]}...")
            except Exception as e:
                print(f"  run {i+1}/{N}: ERROR — {e}")
                preds.append({"has_anomaly": False, "root_cause": "", "focus_room": None})

        # 分类：多数票
        anomaly_votes = sum(1 for p in preds if p["has_anomaly"])
        pred_anomaly = anomaly_votes > N / 2
        cls.add(pred_anomaly, expected_anomaly)

        # 根因 judge（仅对有 expected_cause_category 且不是"无"的 case）
        case_judge_scores = []
        if expected_category and expected_category != "无" and expected_anomaly:
            for p in preds:
                if p["root_cause"]:
                    try:
                        verdict = await judge_root_cause(
                            description=case["description"],
                            expected_category=expected_category,
                            agent_root_cause=p["root_cause"],
                        )
                        case_judge_scores.append(verdict.score)
                        print(f"    judge: {verdict.verdict} ({verdict.score}) — {verdict.reason[:60]}")
                    except Exception as e:
                        print(f"    judge ERROR: {e}")
                        case_judge_scores.append(0.0)
                else:
                    case_judge_scores.append(0.0)

        avg_score = statistics.mean(case_judge_scores) if case_judge_scores else None
        if avg_score is not None:
            judge_scores.append(avg_score)

        results_detail.append({
            "id": case_id,
            "pred_anomaly": pred_anomaly,
            "expected_anomaly": expected_anomaly,
            "judge_avg": avg_score,
            "difficulty": difficulty,
        })

        status = "OK" if pred_anomaly == expected_anomaly else "MISMATCH"
        score_str = f", judge={avg_score:.2f}" if avg_score is not None else ""
        print(f"  → {status}: pred={pred_anomaly}, expected={expected_anomaly}{score_str}")

    # 汇总
    print("\n" + "=" * 70)
    print("汇总结果")
    print("=" * 70)
    print(f"\n分类指标: {cls.summary()}")

    if judge_scores:
        print(f"根因命中率(judge): {statistics.mean(judge_scores):.2f}")
        hard_scores = [
            r["judge_avg"] for r in results_detail
            if r["difficulty"] == "hard" and r["judge_avg"] is not None
        ]
        if hard_scores:
            print(f"  hard cases 均分: {statistics.mean(hard_scores):.2f}")
        easy_scores = [
            r["judge_avg"] for r in results_detail
            if r["difficulty"] == "easy" and r["judge_avg"] is not None
        ]
        if easy_scores:
            print(f"  easy cases 均分: {statistics.mean(easy_scores):.2f}")
    else:
        print("根因命中率: N/A（无需要 judge 的 case）")

    print("\n逐 case 结果:")
    for r in results_detail:
        mark = "✓" if r["pred_anomaly"] == r["expected_anomaly"] else "✗"
        score_str = f" judge={r['judge_avg']:.2f}" if r["judge_avg"] is not None else ""
        print(f"  {mark} [{r['id']}] pred={r['pred_anomaly']} exp={r['expected_anomaly']}{score_str} ({r['difficulty']})")

    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())