"""仿真数据 — 房间与平台指标（ADR-003: 场景化注入，每个根因类别有正交区分信号）"""

from __future__ import annotations

import random
from typing import Any

_RNG = random.Random(42)

_ROOMS = ["room_001", "room_002", "room_003", "room_004", "room_005"]

# seed → (anomaly_room, category) 映射
# category: healthy, host_inactive, audio_failure, fake_traffic, ghost_room,
#           cdn_fault, network_jitter, content_mismatch
_SCENARIO_MAP: dict[int, dict] = {
    100: {"category": "healthy", "anomaly_room": None},
    33: {"category": "healthy", "anomaly_room": None},
    2: {"category": "healthy", "anomaly_room": None},
    7: {"category": "audio_failure", "anomaly_room": "room_002"},
    15: {"category": "host_inactive", "anomaly_room": "room_001"},
    13: {"category": "host_inactive", "anomaly_room": "room_003"},
    5: {"category": "fake_traffic", "anomaly_room": "room_001"},
    10: {"category": "ghost_room", "anomaly_room": "room_004"},
    20: {"category": "network_jitter", "anomaly_room": "room_005"},
}

_current_scenario: dict = {"category": "healthy", "anomaly_room": None}


def _get_scenario() -> dict:
    return _current_scenario


def get_platform_overview() -> dict[str, Any]:
    scenario = _get_scenario()
    cat = scenario["category"]

    if cat == "healthy":
        health = _RNG.randint(80, 100)
    else:
        health = _RNG.randint(55, 75)

    active = _RNG.randint(30, 80)
    return {
        "total_rooms": 100,
        "active_rooms": active,
        "health_score": health,
        "avg_occupancy": round(_RNG.uniform(0.3, 0.9), 2),
    }


def get_room_detail(room_id: str) -> dict[str, Any]:
    scenario = _get_scenario()
    cat = scenario["category"]
    anomaly_room = scenario["anomaly_room"]

    is_target = (room_id == anomaly_room)

    if not is_target or cat == "healthy":
        return _healthy_room(room_id)

    if cat == "host_inactive":
        return _host_inactive_room(room_id)
    elif cat == "audio_failure":
        return _audio_failure_room(room_id)
    elif cat == "fake_traffic":
        return _fake_traffic_room(room_id)
    elif cat == "ghost_room":
        return _ghost_room(room_id)
    elif cat == "cdn_fault":
        return _cdn_fault_room(room_id)
    elif cat == "network_jitter":
        return _network_jitter_room(room_id)
    elif cat == "content_mismatch":
        return _content_mismatch_room(room_id)

    return _healthy_room(room_id)


def _healthy_room(room_id: str) -> dict[str, Any]:
    return {
        "room_id": room_id,
        "host": f"host_{room_id[-3:]}",
        "occupancy": _RNG.randint(20, 120),
        "metrics": {
            "user_drop_rate": {"value": round(_RNG.uniform(0.01, 0.05), 4), "anomaly": False},
            "engagement_score": {"value": round(_RNG.uniform(65, 95), 1), "anomaly": False},
            "audio_quality": {"value": round(_RNG.uniform(80, 99), 1), "anomaly": False},
            "host_speak_duration_min": {"value": _RNG.randint(30, 55), "anomaly": False},
            "host_active_ratio": {"value": round(_RNG.uniform(0.7, 0.95), 2), "anomaly": False},
            "audio_error_rate": {"value": round(_RNG.uniform(0.0, 0.02), 3), "anomaly": False},
            "gift_concentration": {"value": round(_RNG.uniform(0.1, 0.3), 2), "anomaly": False},
            "new_device_ratio": {"value": round(_RNG.uniform(0.02, 0.08), 3), "anomaly": False},
            "msg_rate_per_user": {"value": round(_RNG.uniform(2.0, 8.0), 1), "anomaly": False},
            "interaction_rate": {"value": round(_RNG.uniform(0.3, 0.7), 2), "anomaly": False},
            "latency_ms": {"value": _RNG.randint(30, 80), "anomaly": False},
            "latency_variance_ms": {"value": _RNG.randint(5, 20), "anomaly": False},
            "packet_loss_rate": {"value": round(_RNG.uniform(0.0, 0.01), 4), "anomaly": False},
            "first_frame_ms": {"value": _RNG.randint(100, 300), "anomaly": False},
            "early_leave_rate": {"value": round(_RNG.uniform(0.05, 0.15), 3), "anomaly": False},
            "avg_stay_duration_min": {"value": _RNG.randint(8, 25), "anomaly": False},
        },
    }


def _host_inactive_room(room_id: str) -> dict[str, Any]:
    """主播低迷: 主播开麦时长↓, host_active_ratio↓, 互动分低, 音频正常"""
    return {
        "room_id": room_id,
        "host": f"host_{room_id[-3:]}",
        "occupancy": _RNG.randint(30, 100),
        "metrics": {
            "user_drop_rate": {"value": round(_RNG.uniform(0.08, 0.15), 4), "anomaly": True},
            "engagement_score": {"value": round(_RNG.uniform(20, 40), 1), "anomaly": True},
            "audio_quality": {"value": round(_RNG.uniform(82, 95), 1), "anomaly": False},
            "host_speak_duration_min": {"value": _RNG.randint(3, 10), "anomaly": True},
            "host_active_ratio": {"value": round(_RNG.uniform(0.1, 0.3), 2), "anomaly": True},
            "audio_error_rate": {"value": round(_RNG.uniform(0.0, 0.02), 3), "anomaly": False},
            "gift_concentration": {"value": round(_RNG.uniform(0.1, 0.3), 2), "anomaly": False},
            "new_device_ratio": {"value": round(_RNG.uniform(0.02, 0.08), 3), "anomaly": False},
            "msg_rate_per_user": {"value": round(_RNG.uniform(0.5, 2.0), 1), "anomaly": True},
            "interaction_rate": {"value": round(_RNG.uniform(0.05, 0.15), 2), "anomaly": True},
            "latency_ms": {"value": _RNG.randint(30, 70), "anomaly": False},
            "latency_variance_ms": {"value": _RNG.randint(5, 15), "anomaly": False},
            "packet_loss_rate": {"value": round(_RNG.uniform(0.0, 0.01), 4), "anomaly": False},
            "first_frame_ms": {"value": _RNG.randint(100, 250), "anomaly": False},
            "early_leave_rate": {"value": round(_RNG.uniform(0.15, 0.25), 3), "anomaly": False},
            "avg_stay_duration_min": {"value": _RNG.randint(3, 8), "anomaly": True},
        },
    }


def _audio_failure_room(room_id: str) -> dict[str, Any]:
    """音频故障: audio_error_rate↑, audio_quality↓, 主播活跃正常"""
    return {
        "room_id": room_id,
        "host": f"host_{room_id[-3:]}",
        "occupancy": _RNG.randint(20, 80),
        "metrics": {
            "user_drop_rate": {"value": round(_RNG.uniform(0.15, 0.30), 4), "anomaly": True},
            "engagement_score": {"value": round(_RNG.uniform(35, 55), 1), "anomaly": True},
            "audio_quality": {"value": round(_RNG.uniform(25, 45), 1), "anomaly": True},
            "host_speak_duration_min": {"value": _RNG.randint(30, 50), "anomaly": False},
            "host_active_ratio": {"value": round(_RNG.uniform(0.7, 0.9), 2), "anomaly": False},
            "audio_error_rate": {"value": round(_RNG.uniform(0.15, 0.35), 3), "anomaly": True},
            "gift_concentration": {"value": round(_RNG.uniform(0.1, 0.3), 2), "anomaly": False},
            "new_device_ratio": {"value": round(_RNG.uniform(0.02, 0.08), 3), "anomaly": False},
            "msg_rate_per_user": {"value": round(_RNG.uniform(1.5, 4.0), 1), "anomaly": False},
            "interaction_rate": {"value": round(_RNG.uniform(0.2, 0.4), 2), "anomaly": False},
            "latency_ms": {"value": _RNG.randint(40, 90), "anomaly": False},
            "latency_variance_ms": {"value": _RNG.randint(5, 20), "anomaly": False},
            "packet_loss_rate": {"value": round(_RNG.uniform(0.0, 0.02), 4), "anomaly": False},
            "first_frame_ms": {"value": _RNG.randint(100, 300), "anomaly": False},
            "early_leave_rate": {"value": round(_RNG.uniform(0.1, 0.2), 3), "anomaly": False},
            "avg_stay_duration_min": {"value": _RNG.randint(5, 12), "anomaly": False},
        },
    }


def _fake_traffic_room(room_id: str) -> dict[str, Any]:
    """刷量套利: 送礼集中度↑, 新设备占比↑, 充值IP集中, 真实互动数据正常"""
    return {
        "room_id": room_id,
        "host": f"host_{room_id[-3:]}",
        "occupancy": _RNG.randint(40, 100),
        "metrics": {
            "user_drop_rate": {"value": round(_RNG.uniform(0.02, 0.05), 4), "anomaly": False},
            "engagement_score": {"value": round(_RNG.uniform(60, 80), 1), "anomaly": False},
            "audio_quality": {"value": round(_RNG.uniform(82, 96), 1), "anomaly": False},
            "host_speak_duration_min": {"value": _RNG.randint(25, 50), "anomaly": False},
            "host_active_ratio": {"value": round(_RNG.uniform(0.6, 0.85), 2), "anomaly": False},
            "audio_error_rate": {"value": round(_RNG.uniform(0.0, 0.02), 3), "anomaly": False},
            "gift_concentration": {"value": round(_RNG.uniform(0.75, 0.95), 2), "anomaly": True},
            "new_device_ratio": {"value": round(_RNG.uniform(0.35, 0.60), 3), "anomaly": True},
            "recharge_ip_concentration": {"value": round(_RNG.uniform(0.70, 0.90), 2), "anomaly": True},
            "msg_rate_per_user": {"value": round(_RNG.uniform(2.0, 5.0), 1), "anomaly": False},
            "interaction_rate": {"value": round(_RNG.uniform(0.3, 0.6), 2), "anomaly": False},
            "latency_ms": {"value": _RNG.randint(30, 70), "anomaly": False},
            "latency_variance_ms": {"value": _RNG.randint(5, 15), "anomaly": False},
            "packet_loss_rate": {"value": round(_RNG.uniform(0.0, 0.01), 4), "anomaly": False},
            "first_frame_ms": {"value": _RNG.randint(100, 250), "anomaly": False},
            "early_leave_rate": {"value": round(_RNG.uniform(0.05, 0.12), 3), "anomaly": False},
            "avg_stay_duration_min": {"value": _RNG.randint(10, 20), "anomaly": False},
            "gift_revenue_surge": {"value": round(_RNG.uniform(2.5, 4.0), 1), "anomaly": True},
        },
    }


def _ghost_room(room_id: str) -> dict[str, Any]:
    """挂机刷在线: online高但 msg_rate/互动率 塌, 语音活跃度极低"""
    return {
        "room_id": room_id,
        "host": f"host_{room_id[-3:]}",
        "occupancy": _RNG.randint(50, 150),
        "metrics": {
            "user_drop_rate": {"value": round(_RNG.uniform(0.01, 0.03), 4), "anomaly": False},
            "engagement_score": {"value": round(_RNG.uniform(5, 15), 1), "anomaly": True},
            "audio_quality": {"value": round(_RNG.uniform(80, 95), 1), "anomaly": False},
            "host_speak_duration_min": {"value": _RNG.randint(0, 3), "anomaly": True},
            "host_active_ratio": {"value": round(_RNG.uniform(0.01, 0.08), 2), "anomaly": True},
            "audio_error_rate": {"value": round(_RNG.uniform(0.0, 0.01), 3), "anomaly": False},
            "gift_concentration": {"value": round(_RNG.uniform(0.1, 0.25), 2), "anomaly": False},
            "new_device_ratio": {"value": round(_RNG.uniform(0.02, 0.08), 3), "anomaly": False},
            "msg_rate_per_user": {"value": round(_RNG.uniform(0.0, 0.3), 2), "anomaly": True},
            "interaction_rate": {"value": round(_RNG.uniform(0.0, 0.03), 3), "anomaly": True},
            "voice_active_ratio": {"value": round(_RNG.uniform(0.0, 0.05), 3), "anomaly": True},
            "latency_ms": {"value": _RNG.randint(30, 60), "anomaly": False},
            "latency_variance_ms": {"value": _RNG.randint(5, 12), "anomaly": False},
            "packet_loss_rate": {"value": round(_RNG.uniform(0.0, 0.005), 4), "anomaly": False},
            "first_frame_ms": {"value": _RNG.randint(100, 200), "anomaly": False},
            "early_leave_rate": {"value": round(_RNG.uniform(0.01, 0.05), 3), "anomaly": False},
            "avg_stay_duration_min": {"value": _RNG.randint(60, 180), "anomaly": True},
        },
    }


def _cdn_fault_room(room_id: str) -> dict[str, Any]:
    """CDN/区域故障: 卡顿延迟集中在特定区域, 首帧时长↑, 全局音质分未必差"""
    return {
        "room_id": room_id,
        "host": f"host_{room_id[-3:]}",
        "occupancy": _RNG.randint(30, 100),
        "metrics": {
            "user_drop_rate": {"value": round(_RNG.uniform(0.10, 0.20), 4), "anomaly": True},
            "engagement_score": {"value": round(_RNG.uniform(45, 65), 1), "anomaly": False},
            "audio_quality": {"value": round(_RNG.uniform(65, 80), 1), "anomaly": False},
            "host_speak_duration_min": {"value": _RNG.randint(25, 50), "anomaly": False},
            "host_active_ratio": {"value": round(_RNG.uniform(0.6, 0.85), 2), "anomaly": False},
            "audio_error_rate": {"value": round(_RNG.uniform(0.02, 0.06), 3), "anomaly": False},
            "gift_concentration": {"value": round(_RNG.uniform(0.1, 0.3), 2), "anomaly": False},
            "new_device_ratio": {"value": round(_RNG.uniform(0.02, 0.08), 3), "anomaly": False},
            "msg_rate_per_user": {"value": round(_RNG.uniform(2.0, 5.0), 1), "anomaly": False},
            "interaction_rate": {"value": round(_RNG.uniform(0.25, 0.5), 2), "anomaly": False},
            "latency_ms": {"value": _RNG.randint(200, 500), "anomaly": True},
            "latency_variance_ms": {"value": _RNG.randint(80, 200), "anomaly": True},
            "packet_loss_rate": {"value": round(_RNG.uniform(0.03, 0.08), 4), "anomaly": True},
            "first_frame_ms": {"value": _RNG.randint(800, 2000), "anomaly": True},
            "affected_region": {"value": "华南-电信", "anomaly": True},
            "early_leave_rate": {"value": round(_RNG.uniform(0.1, 0.2), 3), "anomaly": False},
            "avg_stay_duration_min": {"value": _RNG.randint(5, 12), "anomaly": False},
        },
    }


def _network_jitter_room(room_id: str) -> dict[str, Any]:
    """网络抖动: 延迟方差↑, 丢包率↑, 短时波动（非持续），音质未必差"""
    return {
        "room_id": room_id,
        "host": f"host_{room_id[-3:]}",
        "occupancy": _RNG.randint(30, 100),
        "metrics": {
            "user_drop_rate": {"value": round(_RNG.uniform(0.08, 0.15), 4), "anomaly": True},
            "engagement_score": {"value": round(_RNG.uniform(50, 70), 1), "anomaly": False},
            "audio_quality": {"value": round(_RNG.uniform(60, 78), 1), "anomaly": False},
            "host_speak_duration_min": {"value": _RNG.randint(25, 50), "anomaly": False},
            "host_active_ratio": {"value": round(_RNG.uniform(0.6, 0.85), 2), "anomaly": False},
            "audio_error_rate": {"value": round(_RNG.uniform(0.02, 0.05), 3), "anomaly": False},
            "gift_concentration": {"value": round(_RNG.uniform(0.1, 0.3), 2), "anomaly": False},
            "new_device_ratio": {"value": round(_RNG.uniform(0.02, 0.08), 3), "anomaly": False},
            "msg_rate_per_user": {"value": round(_RNG.uniform(2.0, 5.0), 1), "anomaly": False},
            "interaction_rate": {"value": round(_RNG.uniform(0.25, 0.5), 2), "anomaly": False},
            "latency_ms": {"value": _RNG.randint(80, 150), "anomaly": True},
            "latency_variance_ms": {"value": _RNG.randint(60, 150), "anomaly": True},
            "packet_loss_rate": {"value": round(_RNG.uniform(0.04, 0.10), 4), "anomaly": True},
            "first_frame_ms": {"value": _RNG.randint(200, 500), "anomaly": False},
            "jitter_burst_count": {"value": _RNG.randint(5, 15), "anomaly": True},
            "early_leave_rate": {"value": round(_RNG.uniform(0.08, 0.15), 3), "anomaly": False},
            "avg_stay_duration_min": {"value": _RNG.randint(6, 15), "anomaly": False},
        },
    }


def _content_mismatch_room(room_id: str) -> dict[str, Any]:
    """内容不匹配: 早退率↑, 平均停留时长↓, 技术指标正常"""
    return {
        "room_id": room_id,
        "host": f"host_{room_id[-3:]}",
        "occupancy": _RNG.randint(30, 80),
        "metrics": {
            "user_drop_rate": {"value": round(_RNG.uniform(0.10, 0.20), 4), "anomaly": True},
            "engagement_score": {"value": round(_RNG.uniform(30, 50), 1), "anomaly": True},
            "audio_quality": {"value": round(_RNG.uniform(80, 95), 1), "anomaly": False},
            "host_speak_duration_min": {"value": _RNG.randint(25, 50), "anomaly": False},
            "host_active_ratio": {"value": round(_RNG.uniform(0.6, 0.85), 2), "anomaly": False},
            "audio_error_rate": {"value": round(_RNG.uniform(0.0, 0.02), 3), "anomaly": False},
            "gift_concentration": {"value": round(_RNG.uniform(0.1, 0.3), 2), "anomaly": False},
            "new_device_ratio": {"value": round(_RNG.uniform(0.02, 0.08), 3), "anomaly": False},
            "msg_rate_per_user": {"value": round(_RNG.uniform(1.0, 3.0), 1), "anomaly": False},
            "interaction_rate": {"value": round(_RNG.uniform(0.15, 0.3), 2), "anomaly": False},
            "latency_ms": {"value": _RNG.randint(30, 70), "anomaly": False},
            "latency_variance_ms": {"value": _RNG.randint(5, 15), "anomaly": False},
            "packet_loss_rate": {"value": round(_RNG.uniform(0.0, 0.01), 4), "anomaly": False},
            "first_frame_ms": {"value": _RNG.randint(100, 250), "anomaly": False},
            "early_leave_rate": {"value": round(_RNG.uniform(0.35, 0.55), 3), "anomaly": True},
            "avg_stay_duration_min": {"value": _RNG.randint(1, 4), "anomaly": True},
        },
    }


def reset_seed(seed: int = 42) -> None:
    global _RNG, _current_scenario
    _RNG = random.Random(seed)
    _current_scenario = _SCENARIO_MAP.get(seed, {"category": "healthy", "anomaly_room": None})