"""仿真数据 — 告警源（场景化注入，与 room_metrics 的 seed→scenario 映射一致）"""

from __future__ import annotations

import random
from typing import Any

_RNG = random.Random(42)

_SCENARIO_ALERTS: dict[str, list[dict]] = {
    "healthy": [],
    "host_inactive": [
        {"type": "engagement_low", "severity": "warning", "message": "房间互动分持续走低"},
        {"type": "host_inactive", "severity": "warning", "message": "主播开麦时长异常低"},
    ],
    "audio_failure": [
        {"type": "audio_quality_degraded", "severity": "critical", "message": "音频质量跌破阈值"},
        {"type": "audio_error_rate_high", "severity": "critical", "message": "音频错误率飙升"},
        {"type": "user_drop_spike", "severity": "warning", "message": "用户流失率突增"},
        {"type": "audio_quality_degraded", "severity": "warning", "message": "音频质量持续低于正常值"},
    ],
    "fake_traffic": [
        {"type": "gift_anomaly", "severity": "warning", "message": "送礼数据异常：集中度过高"},
        {"type": "new_device_spike", "severity": "warning", "message": "新设备占比异常飙升"},
    ],
    "ghost_room": [
        {"type": "engagement_low", "severity": "warning", "message": "高在线但零互动，疑似挂机"},
        {"type": "voice_inactive", "severity": "warning", "message": "语音活跃度极低"},
    ],
    "cdn_fault": [
        {"type": "latency_spike", "severity": "critical", "message": "区域延迟飙升"},
        {"type": "first_frame_slow", "severity": "warning", "message": "首帧加载超时"},
        {"type": "user_drop_spike", "severity": "warning", "message": "区域用户集中流失"},
    ],
    "network_jitter": [
        {"type": "packet_loss_high", "severity": "warning", "message": "丢包率超阈值"},
        {"type": "latency_variance_high", "severity": "warning", "message": "延迟方差异常"},
    ],
    "content_mismatch": [
        {"type": "early_leave_high", "severity": "warning", "message": "用户早退率异常高"},
        {"type": "engagement_low", "severity": "warning", "message": "互动分走低，停留时长短"},
    ],
}

_current_category: str = "healthy"
_current_anomaly_room: str | None = None


def get_active_alerts() -> list[dict[str, Any]]:
    templates = _SCENARIO_ALERTS.get(_current_category, [])
    if not templates or not _current_anomaly_room:
        return []

    alerts = []
    for t in templates:
        alerts.append({
            "room_id": _current_anomaly_room,
            "type": t["type"],
            "severity": t["severity"],
            "message": t["message"],
        })
    return alerts


def get_alert_history(room_id: str) -> list[dict[str, Any]]:
    if room_id != _current_anomaly_room:
        return []

    templates = _SCENARIO_ALERTS.get(_current_category, [])
    history = []
    for i, t in enumerate(templates):
        history.append({
            "room_id": room_id,
            "type": t["type"],
            "resolved": False,
            "hours_ago": (i + 1) * 2,
        })
    # 添加一些已解决的老告警使历史更真实
    if templates:
        history.append({
            "room_id": room_id,
            "type": templates[0]["type"],
            "resolved": True,
            "hours_ago": 24,
        })
    return history


def reset_seed(seed: int = 42) -> None:
    global _RNG, _current_category, _current_anomaly_room
    from vcr_ops_agent.tools.room_metrics import _SCENARIO_MAP
    _RNG = random.Random(seed)
    scenario = _SCENARIO_MAP.get(seed, {"category": "healthy", "anomaly_room": None})
    _current_category = scenario["category"]
    _current_anomaly_room = scenario["anomaly_room"]