"""仿真数据生成器测试 — 确保可复现"""

from vcr_ops_agent.tools.room_metrics import get_platform_overview, reset_seed as reset_room
from vcr_ops_agent.tools.alerts import get_active_alerts, reset_seed as reset_alert


def test_room_metrics_reproducible():
    reset_room(42)
    a = get_platform_overview()
    reset_room(42)
    b = get_platform_overview()
    assert a == b


def test_alerts_reproducible():
    reset_alert(42)
    a = get_active_alerts()
    reset_alert(42)
    b = get_active_alerts()
    assert a == b