"""仿真数据生成器 — 可复现场景，用于 demo 与 evals（ADR-003）"""

from __future__ import annotations

from vcr_ops_agent.tools.room_metrics import reset_seed as reset_room_seed
from vcr_ops_agent.tools.alerts import reset_seed as reset_alert_seed


def setup_scenario(seed: int = 42) -> None:
    """重置所有仿真数据源的随机种子，确保可复现。"""
    reset_room_seed(seed)
    reset_alert_seed(seed)


SCENARIOS: dict[str, int] = {
    "healthy_platform": 100,
    "single_room_anomaly": 7,
    "multi_room_degradation": 15,
    "audio_infrastructure_issue": 13,
}

DEFAULT_SCENARIO_SEED = 7
