"""巡检 Agent (S1) — 多轮自主调查：平台大盘 → 拉告警找可疑房间 → 下钻确认 → 收敛结论

LLM 模式：用 Claude 分析指标、判断异常、给出调查方向
Fake 模式：规则兜底，保证离线可跑
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from vcr_ops_agent.agents.base import BaseAgent
from vcr_ops_agent.llm import LLMClient
from vcr_ops_agent.state import Decision, Finding, OpsState
from vcr_ops_agent.tools.room_metrics import get_platform_overview, get_room_detail
from vcr_ops_agent.tools.alerts import get_active_alerts


class InspectionJudgment(BaseModel):
    """LLM 结构化输出：巡检判断结果"""
    is_anomaly: bool = False
    severity: str = "info"
    summary: str = ""
    next_action: str = "end"
    reasoning: str = ""


SYSTEM_PROMPT = """你是虚拟语聊房平台的巡检 Agent。你的任务是分析平台指标数据，判断是否存在异常。

规则：
1. 平台健康分 < 80 时需要深入排查
2. 用户流失率 > 10% 是异常
3. 互动分 < 50 是异常
4. 音频质量 < 60 是异常
5. 发现异常时确定最可疑的房间，准备移交根因分析

请基于提供的数据做出判断。"""


class InspectionAgent(BaseAgent):
    name = "inspection"
    domain = "monitoring"

    async def run(self, state: OpsState, **kwargs: Any) -> dict:
        findings: list[Finding] = []
        decisions: list[Decision] = []
        focus_room: str | None = state.focus_room
        steps = state.inspection_steps
        llm = LLMClient.get()

        if steps == 0:
            return await self._step_overview(state, findings, decisions, steps, llm)
        elif steps == 1:
            return await self._step_alerts(state, findings, decisions, steps, llm)
        elif steps == 2 and (focus_room or state.focus_room):
            return await self._step_drill_down(state, findings, decisions, steps, llm)
        else:
            decisions.append(Decision(
                agent=self.name,
                action="inspection_complete",
                reasoning="巡检流程结束或达到最大步数",
                confidence=1.0,
            ))
            return {
                "findings": findings,
                "decisions": decisions,
                "inspection_steps": steps + 1,
                "next": "supervisor",
            }

    async def _step_overview(
        self, state: OpsState, findings: list, decisions: list, steps: int, llm: LLMClient
    ) -> dict:
        overview = get_platform_overview()
        findings.append(Finding(
            agent=self.name,
            category="platform_overview",
            summary=f"平台总房间数: {overview['total_rooms']}, 活跃: {overview['active_rooms']}",
            details=overview,
        ))

        if llm.available:
            judgment = await llm.invoke_structured(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"平台大盘数据:\n{overview}\n\n请判断平台健康状况，是否需要进一步排查。"},
                ],
                output_schema=InspectionJudgment,
                trace_id=state.trace_id,
                span_name="inspection_overview_llm",
            )
            if judgment and judgment.is_anomaly:
                decisions.append(Decision(
                    agent=self.name,
                    action="escalate_to_alerts",
                    reasoning=judgment.reasoning or "LLM判断平台存在异常，需深入排查",
                    confidence=0.9,
                ))
                return {
                    "findings": findings,
                    "decisions": decisions,
                    "inspection_steps": steps + 1,
                    "next": "inspection",
                }
        else:
            if overview.get("health_score", 100) < 80:
                decisions.append(Decision(
                    agent=self.name,
                    action="escalate_to_alerts",
                    reasoning=f"平台健康分 {overview['health_score']} < 80，拉取告警定位可疑房间",
                    confidence=0.9,
                ))
                return {
                    "findings": findings,
                    "decisions": decisions,
                    "inspection_steps": steps + 1,
                    "next": "inspection",
                }

        decisions.append(Decision(
            agent=self.name,
            action="check_platform_overview",
            reasoning="平台状态正常，无需进一步排查",
            confidence=1.0,
        ))
        return {
            "findings": findings,
            "decisions": decisions,
            "inspection_steps": steps + 1,
            "next": "supervisor",
        }

    async def _step_alerts(
        self, state: OpsState, findings: list, decisions: list, steps: int, llm: LLMClient
    ) -> dict:
        alerts = get_active_alerts()
        if not alerts:
            findings.append(Finding(
                agent=self.name,
                category="no_alerts",
                summary="当前无活跃告警",
            ))
            return {
                "findings": findings,
                "decisions": decisions,
                "inspection_steps": steps + 1,
                "next": "supervisor",
            }

        if llm.available:
            judgment = await llm.invoke_structured(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"活跃告警列表:\n{alerts}\n\n请选出最需要关注的房间，并说明理由。"},
                ],
                output_schema=InspectionJudgment,
                trace_id=state.trace_id,
                span_name="inspection_alerts_llm",
            )
            target_room = alerts[0]["room_id"]
            reasoning = judgment.reasoning if judgment else f"告警指向房间 {target_room}"
        else:
            target_room = alerts[0]["room_id"]
            reasoning = f"告警 {alerts[0]['type']} 指向房间 {target_room}，下钻确认"

        findings.append(Finding(
            agent=self.name,
            category="alert_detected",
            severity="warning",
            summary=f"发现告警: {alerts[0]['type']} in room {target_room}",
            details=alerts[0],
        ))
        decisions.append(Decision(
            agent=self.name,
            action="focus_room_selected",
            reasoning=reasoning,
            confidence=0.85,
        ))
        return {
            "findings": findings,
            "decisions": decisions,
            "focus_room": target_room,
            "inspection_steps": steps + 1,
            "next": "inspection",
        }

    async def _step_drill_down(
        self, state: OpsState, findings: list, decisions: list, steps: int, llm: LLMClient
    ) -> dict:
        focus_room = state.focus_room
        detail = get_room_detail(focus_room)
        anomalies = [k for k, v in detail.get("metrics", {}).items() if v.get("anomaly")]

        if llm.available:
            judgment = await llm.invoke_structured(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": (
                        f"房间 {focus_room} 详细数据:\n{detail}\n\n"
                        f"检测到的异常指标: {anomalies}\n\n"
                        "请确认该房间是否确实存在异常，是否需要移交根因分析。"
                    )},
                ],
                output_schema=InspectionJudgment,
                trace_id=state.trace_id,
                span_name="inspection_drilldown_llm",
            )
            if judgment and judgment.is_anomaly:
                findings.append(Finding(
                    agent=self.name,
                    category="room_anomaly_confirmed",
                    severity=judgment.severity or "high",
                    summary=judgment.summary or f"房间 {focus_room} 确认异常",
                    details=detail,
                ))
                decisions.append(Decision(
                    agent=self.name,
                    action="anomaly_confirmed",
                    reasoning=judgment.reasoning or f"房间 {focus_room} 存在异常，移交根因分析",
                    confidence=0.9,
                ))
                return {
                    "findings": findings,
                    "decisions": decisions,
                    "inspection_steps": steps + 1,
                    "next": "analytics",
                }
        else:
            if anomalies:
                findings.append(Finding(
                    agent=self.name,
                    category="room_anomaly_confirmed",
                    severity="high",
                    summary=f"房间 {focus_room} 确认异常指标: {', '.join(anomalies)}",
                    details=detail,
                ))
                decisions.append(Decision(
                    agent=self.name,
                    action="anomaly_confirmed",
                    reasoning=f"房间 {focus_room} 存在 {len(anomalies)} 项异常，移交根因分析",
                    confidence=0.9,
                ))
                return {
                    "findings": findings,
                    "decisions": decisions,
                    "inspection_steps": steps + 1,
                    "next": "analytics",
                }

        findings.append(Finding(
            agent=self.name,
            category="room_normal",
            summary=f"房间 {focus_room} 指标正常，告警可能为误报",
        ))
        return {
            "findings": findings,
            "decisions": decisions,
            "inspection_steps": steps + 1,
            "next": "supervisor",
        }