"""共享状态定义 — OpsState (Pydantic v2)

decisions 决策日志是可观测与可解释的核心载体，支持任务级回放。
findings / decisions 用 LangGraph reducer 做追加合并而非覆盖。
"""

from __future__ import annotations

import operator
import uuid
from datetime import datetime
from enum import Enum
from typing import Annotated, Any

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class RootCauseCategory(str, Enum):
    HOST_INACTIVE = "host_inactive"
    AUDIO_FAILURE = "audio_failure"
    FAKE_TRAFFIC = "fake_traffic"
    GHOST_ROOM = "ghost_room"
    CDN_FAULT = "cdn_fault"
    NETWORK_JITTER = "network_jitter"
    CONTENT_MISMATCH = "content_mismatch"
    UNKNOWN = "unknown"


class Finding(BaseModel):
    agent: str
    timestamp: datetime = Field(default_factory=datetime.now)
    category: str
    severity: str = "info"
    summary: str
    details: dict[str, Any] = Field(default_factory=dict)


class Decision(BaseModel):
    agent: str
    timestamp: datetime = Field(default_factory=datetime.now)
    action: str
    reasoning: str
    confidence: float = 0.0


class Recommendation(BaseModel):
    summary: str
    actions: list[str] = Field(default_factory=list)
    priority: str = "medium"


class OpsState(BaseModel):
    """LangGraph 共享状态，所有 Agent 读写同一实例。"""

    task: str = ""
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: TaskStatus = TaskStatus.PENDING
    focus_room: str | None = None

    # reducer: 追加合并
    findings: Annotated[list[Finding], operator.add] = Field(default_factory=list)
    decisions: Annotated[list[Decision], operator.add] = Field(default_factory=list)

    recommendation: Recommendation | None = None
    next: str = "supervisor"

    # 巡检 Agent 多轮调查步数控制
    inspection_steps: int = 0
    max_steps: int = 5

    # 根因分析 Agent 多轮假设验证步数控制
    analytics_steps: int = 0
    analytics_max_steps: int = 4
    analytics_hypotheses: list[dict[str, Any]] = Field(default_factory=list)
