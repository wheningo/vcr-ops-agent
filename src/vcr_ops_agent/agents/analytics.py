"""根因分析 Agent (S4) — 多轮假设验证：生成假设 → 逐个取证 → 收敛结论

LLM 模式：每轮用 Claude 评估一个假设的证据
Fake 模式：规则兜底
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from vcr_ops_agent.agents.base import BaseAgent
from vcr_ops_agent.llm import LLMClient
from vcr_ops_agent.state import Decision, Finding, OpsState, Recommendation
from vcr_ops_agent.tools.room_metrics import get_room_detail
from vcr_ops_agent.tools.alerts import get_alert_history


class HypothesisEvaluation(BaseModel):
    """LLM 结构化输出：单假设验证结果"""
    hypothesis: str = ""
    verified: bool = False
    confidence: float = 0.0
    evidence_summary: str = ""
    should_continue: bool = True
    next_action: str = ""


class RootCauseAnalysis(BaseModel):
    """LLM 结构化输出：最终根因结论"""
    root_cause: str = ""
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    priority: str = "medium"
    reasoning: str = ""


SYSTEM_PROMPT = """你是虚拟语聊房平台的根因分析 Agent。收到巡检 Agent 移交的异常房间后，你的任务是：

1. 基于房间指标和告警历史，识别关键区分信号
2. 按照下面的"信号→根因"对照表定位根因类别
3. 给出具体、可执行的修复建议

## 信号→根因 对照表（按优先级匹配）

| 根因类别 | 独有区分信号 |
|---------|------------|
| host_inactive 主播低迷 | host_speak_duration_min↓ + host_active_ratio↓，音频质量正常 |
| audio_failure 音频故障 | audio_error_rate↑ + audio_quality↓，主播活跃度正常 |
| fake_traffic 刷量套利 | gift_concentration↑ + new_device_ratio↑ + recharge_ip_concentration↑，真实互动正常 |
| ghost_room 挂机刷在线 | occupancy高 + msg_rate_per_user≈0 + interaction_rate≈0 + voice_active_ratio≈0 |
| cdn_fault CDN/区域故障 | latency_ms↑↑ + first_frame_ms↑↑ + affected_region存在，全局音质分未必差 |
| network_jitter 网络抖动 | latency_variance_ms↑ + packet_loss_rate↑ + jitter_burst_count存在，短时波动 |
| content_mismatch 内容不匹配 | early_leave_rate↑ + avg_stay_duration_min↓，技术指标全部正常 |

## 分析流程

1. 先看主播活跃度指标（host_speak_duration_min, host_active_ratio）→ 若异常且音频正常 → host_inactive
2. 再看音频指标（audio_error_rate, audio_quality）→ 若 audio_error_rate 高 → audio_failure
3. 看送礼/设备指标（gift_concentration, new_device_ratio, recharge_ip_concentration）→ 若集中度高 → fake_traffic
4. 看在线/互动比（occupancy高 vs msg_rate≈0, interaction_rate≈0）→ ghost_room
5. 看延迟/首帧（latency_ms, first_frame_ms, affected_region）→ cdn_fault
6. 看延迟方差/丢包（latency_variance_ms, packet_loss_rate, jitter_burst_count）→ network_jitter
7. 看早退/停留（early_leave_rate, avg_stay_duration_min，技术正常）→ content_mismatch

关键原则：不要默认归因为"音频故障"！只有当 audio_error_rate 明确异常时才判定音频问题。
互动低不等于音频差，主播不活跃也会导致互动低。
送礼异常不等于技术故障，要看 gift_concentration 和 new_device_ratio。

输出要具体，不要泛泛而谈。建议要可执行，不要"建议关注"这种空话。"""

VERIFY_PROMPT = """你正在逐个验证根因假设。当前正在验证以下假设：

假设: {hypothesis}
需要的证据: {evidence_needed}

已收集的数据:
- 房间详情: {detail}
- 告警历史: {history}
- 异常指标: {anomaly_metrics}

请严格按照信号→根因对照表判断。关键原则：
- 只有 audio_error_rate 明确异常才能判定音频故障
- host_speak_duration_min/host_active_ratio 低 → 主播问题，不是音频问题
- gift_concentration/new_device_ratio 高 → 刷量，不是技术故障
- msg_rate≈0 + interaction_rate≈0 + 高 occupancy → 挂机刷在线
- latency_variance_ms↑ + packet_loss_rate↑ → 网络抖动

请评估这条假设是否成立，给出置信度和证据总结。
如果已经足够确定根因，设置 should_continue = false。"""


class AnalyticsAgent(BaseAgent):
    name = "analytics"
    domain = "monitoring"

    async def run(self, state: OpsState, **kwargs: Any) -> dict:
        findings: list[Finding] = []
        decisions: list[Decision] = []
        llm = LLMClient.get()
        steps = state.analytics_steps

        room_id = state.focus_room
        if not room_id:
            decisions.append(Decision(
                agent=self.name,
                action="no_target",
                reasoning="没有指定分析房间，无法执行根因分析",
                confidence=1.0,
            ))
            return {"findings": findings, "decisions": decisions, "next": "supervisor"}

        # Step 0: 生成假设
        if steps == 0:
            return await self._step_generate_hypotheses(state, findings, decisions, llm)

        # Step 1..N-1: 逐假设验证
        if steps <= state.analytics_max_steps and state.analytics_hypotheses:
            return await self._step_verify_hypothesis(state, findings, decisions, llm)

        # 兜底：收敛
        return await self._step_converge(state, findings, decisions, llm)

    async def _step_generate_hypotheses(
        self, state: OpsState, findings: list, decisions: list, llm: LLMClient
    ) -> dict:
        room_id = state.focus_room
        detail = get_room_detail(room_id)
        history = get_alert_history(room_id)
        anomaly_metrics = {k: v for k, v in detail.get("metrics", {}).items() if v.get("anomaly")}

        hypotheses = self._generate_hypotheses(anomaly_metrics, history)

        findings.append(Finding(
            agent=self.name,
            category="hypotheses_generated",
            summary=f"针对房间 {room_id} 生成 {len(hypotheses)} 条根因假设",
            details={"hypotheses": hypotheses},
        ))
        decisions.append(Decision(
            agent=self.name,
            action="hypotheses_generated",
            reasoning=f"生成 {len(hypotheses)} 条假设，开始逐个取证验证",
            confidence=0.5,
        ))

        return {
            "findings": findings,
            "decisions": decisions,
            "analytics_hypotheses": hypotheses,
            "analytics_steps": 1,
            "next": "analytics",
        }

    async def _step_verify_hypothesis(
        self, state: OpsState, findings: list, decisions: list, llm: LLMClient
    ) -> dict:
        steps = state.analytics_steps
        hypotheses = state.analytics_hypotheses
        room_id = state.focus_room

        idx = steps - 1
        if idx >= len(hypotheses):
            return await self._step_converge(state, findings, decisions, llm)

        current_h = hypotheses[idx]
        detail = get_room_detail(room_id)
        history = get_alert_history(room_id)
        anomaly_metrics = {k: v for k, v in detail.get("metrics", {}).items() if v.get("anomaly")}

        if llm.available:
            evaluation = await llm.invoke_structured(
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": VERIFY_PROMPT.format(
                        hypothesis=current_h["cause"],
                        evidence_needed=current_h.get("evidence_needed", []),
                        detail=detail,
                        history=history,
                        anomaly_metrics=anomaly_metrics,
                    )},
                ],
                output_schema=HypothesisEvaluation,
                trace_id=state.trace_id,
                span_name=f"analytics_verify_h{idx}",
            )
            if evaluation:
                verified = evaluation.verified
                confidence = evaluation.confidence
                evidence_summary = evaluation.evidence_summary
                should_continue = evaluation.should_continue
            else:
                verified, confidence, evidence_summary, should_continue = (
                    self._rule_verify(current_h, anomaly_metrics, history)
                )
        else:
            verified, confidence, evidence_summary, should_continue = (
                self._rule_verify(current_h, anomaly_metrics, history)
            )

        findings.append(Finding(
            agent=self.name,
            category="hypothesis_verified",
            severity="high" if verified else "info",
            summary=f"假设 [{current_h['id']}] '{current_h['cause']}' → {'成立' if verified else '排除'} (置信度 {confidence:.0%})",
            details={"hypothesis": current_h, "verified": verified, "evidence": evidence_summary},
        ))

        decisions.append(Decision(
            agent=self.name,
            action="hypothesis_evaluated",
            reasoning=f"验证假设 {current_h['id']}: {evidence_summary}",
            confidence=confidence,
        ))

        # 如果足够确定或者到最后一个假设，进入收敛
        if (verified and confidence >= 0.8) or not should_continue:
            return await self._step_converge(state, findings, decisions, llm)

        # 还有假设需要验证
        next_step = steps + 1
        if next_step - 1 >= len(hypotheses) or next_step > state.analytics_max_steps:
            return await self._step_converge(state, findings, decisions, llm)

        return {
            "findings": findings,
            "decisions": decisions,
            "analytics_steps": next_step,
            "next": "analytics",
        }

    async def _step_converge(
        self, state: OpsState, findings: list, decisions: list, llm: LLMClient
    ) -> dict:
        room_id = state.focus_room
        detail = get_room_detail(room_id)
        history = get_alert_history(room_id)

        if llm.available:
            result = await self._converge_with_llm(state, detail, history, llm)
        else:
            result = self._converge_with_rules(state, detail, history)

        findings.append(Finding(
            agent=self.name,
            category="root_cause_analysis",
            severity="high",
            summary=f"房间 {room_id} 根因: {result.root_cause}",
            details={"evidence": result.evidence, "confidence": result.confidence},
        ))

        decisions.append(Decision(
            agent=self.name,
            action="root_cause_identified",
            reasoning=result.reasoning or f"根因定位: {result.root_cause}，置信度 {result.confidence:.0%}",
            confidence=result.confidence,
        ))

        recommendation = Recommendation(
            summary=f"房间 {room_id} 异常根因: {result.root_cause}",
            actions=result.suggested_actions,
            priority=result.priority,
        )

        return {
            "findings": findings,
            "decisions": decisions,
            "recommendation": recommendation,
            "analytics_steps": state.analytics_steps + 1,
            "next": "supervisor",
        }

    async def _converge_with_llm(
        self, state: OpsState, detail: dict, history: list, llm: LLMClient
    ) -> RootCauseAnalysis:
        verified_findings = [
            f for f in state.findings
            if f.agent == self.name and f.category == "hypothesis_verified"
        ]
        context = "\n".join(
            f"- {f.summary}" for f in verified_findings
        ) or "无前序验证结果"

        anomaly_metrics = {k: v for k, v in detail.get("metrics", {}).items() if v.get("anomaly")}

        result = await llm.invoke_structured(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": (
                    f"房间 {state.focus_room} 根因分析收敛阶段。\n\n"
                    f"前序假设验证结果:\n{context}\n\n"
                    f"房间详情: {detail}\n"
                    f"异常指标: {anomaly_metrics}\n"
                    f"告警历史: {history}\n\n"
                    "请给出最终根因结论和可执行建议。"
                )},
            ],
            output_schema=RootCauseAnalysis,
            trace_id=state.trace_id,
            span_name="analytics_converge_llm",
        )

        if result:
            return result
        return self._converge_with_rules(state, detail, history)

    def _converge_with_rules(
        self, state: OpsState, detail: dict, history: list
    ) -> RootCauseAnalysis:
        metrics = detail.get("metrics", {})
        anomaly_metrics = {k: v for k, v in metrics.items() if v.get("anomaly")}
        hypotheses = state.analytics_hypotheses or self._generate_hypotheses(anomaly_metrics, history)

        best = hypotheses[0] if hypotheses else {"cause": "数据不足", "category": "unknown"}
        category = best.get("category", "unknown")

        actions_map = {
            "host_inactive": ["查看主播最近活跃时间和开麦时长", "检查互动率趋势", "通知运营介入"],
            "audio_failure": ["检查音频编解码链路", "查看该房间音频流错误率", "联系技术团队排查"],
            "fake_traffic": ["核查送礼 top 账号充值来源", "分析新设备注册 IP 分布", "提交反作弊审核"],
            "ghost_room": ["检查挂机账号列表", "核实在线时长奖励机制", "限制异常账号"],
            "cdn_fault": ["检查受影响区域 CDN 节点状态", "查看首帧时长分布", "联系 CDN 厂商"],
            "network_jitter": ["检查网络链路丢包情况", "查看抖动时间段分布", "联系运营商排查"],
            "content_mismatch": ["分析用户早退时段和内容类型", "对比房间标签与用户偏好", "调整推荐策略"],
        }
        actions = actions_map.get(category, ["收集更多数据", "观察下一周期是否复现"])
        confidence = 0.8 if category != "unknown" else 0.5

        return RootCauseAnalysis(
            root_cause=best["cause"],
            confidence=confidence,
            evidence=[k for k in anomaly_metrics.keys()],
            suggested_actions=actions,
            priority="high" if confidence > 0.7 else "medium",
            reasoning=f"基于 {len(anomaly_metrics)} 项异常指标判定根因类别: {category}",
        )

    def _rule_verify(
        self, hypothesis: dict, anomaly_metrics: dict, history: list
    ) -> tuple[bool, float, str, bool]:
        category = hypothesis.get("category", "")

        if category == "audio_failure":
            verified = "audio_error_rate" in anomaly_metrics and "audio_quality" in anomaly_metrics
            confidence = 0.85 if verified else 0.3
            evidence = "音频错误率高且音频质量低，支持音频故障假设" if verified else "音频指标不支持"
            return verified, confidence, evidence, not verified

        if category == "host_inactive":
            verified = ("host_speak_duration_min" in anomaly_metrics or "host_active_ratio" in anomaly_metrics)
            confidence = 0.8 if verified else 0.3
            evidence = "主播开麦时长/活跃度低，支持主播低迷假设" if verified else "主播数据正常"
            return verified, confidence, evidence, not verified

        if category == "fake_traffic":
            verified = "gift_concentration" in anomaly_metrics and "new_device_ratio" in anomaly_metrics
            confidence = 0.85 if verified else 0.3
            evidence = "送礼集中度和新设备占比异常，支持刷量假设" if verified else "送礼数据正常"
            return verified, confidence, evidence, not verified

        if category == "ghost_room":
            verified = "msg_rate_per_user" in anomaly_metrics and "interaction_rate" in anomaly_metrics
            confidence = 0.85 if verified else 0.3
            evidence = "消息率和互动率极低但在线高，支持挂机假设" if verified else "互动数据正常"
            return verified, confidence, evidence, not verified

        if category == "cdn_fault":
            verified = "first_frame_ms" in anomaly_metrics or "affected_region" in anomaly_metrics
            confidence = 0.85 if verified else 0.3
            evidence = "首帧超时/区域集中，支持CDN故障假设" if verified else "延迟数据正常"
            return verified, confidence, evidence, not verified

        if category == "network_jitter":
            verified = "latency_variance_ms" in anomaly_metrics and "packet_loss_rate" in anomaly_metrics
            confidence = 0.8 if verified else 0.3
            evidence = "延迟方差和丢包率异常，支持网络抖动假设" if verified else "网络数据正常"
            return verified, confidence, evidence, not verified

        if category == "content_mismatch":
            verified = "early_leave_rate" in anomaly_metrics and "avg_stay_duration_min" in anomaly_metrics
            confidence = 0.8 if verified else 0.3
            evidence = "早退率高+停留短，支持内容不匹配假设" if verified else "用户停留正常"
            return verified, confidence, evidence, not verified

        return False, 0.2, "无法验证", True

    def _generate_hypotheses(self, anomaly_metrics: dict, history: list) -> list[dict]:
        hypotheses = []

        # 主播低迷
        if "host_speak_duration_min" in anomaly_metrics or "host_active_ratio" in anomaly_metrics:
            hypotheses.append({
                "id": "h_host",
                "cause": "主播不活跃/低迷导致互动下降",
                "category": "host_inactive",
                "evidence_needed": ["host_speak_duration_min", "host_active_ratio", "audio_quality"],
            })

        # 音频故障
        if "audio_error_rate" in anomaly_metrics or "audio_quality" in anomaly_metrics:
            hypotheses.append({
                "id": "h_audio",
                "cause": "音频系统故障导致质量劣化",
                "category": "audio_failure",
                "evidence_needed": ["audio_error_rate", "audio_quality", "host_active_ratio"],
            })

        # 刷量套利
        if "gift_concentration" in anomaly_metrics or "new_device_ratio" in anomaly_metrics:
            hypotheses.append({
                "id": "h_fake",
                "cause": "刷量套利：送礼集中度和新设备占比异常",
                "category": "fake_traffic",
                "evidence_needed": ["gift_concentration", "new_device_ratio", "recharge_ip_concentration"],
            })

        # 挂机刷在线
        if "msg_rate_per_user" in anomaly_metrics or "interaction_rate" in anomaly_metrics:
            if "voice_active_ratio" in anomaly_metrics or ("engagement_score" in anomaly_metrics):
                hypotheses.append({
                    "id": "h_ghost",
                    "cause": "挂机刷在线：高在线但零互动",
                    "category": "ghost_room",
                    "evidence_needed": ["msg_rate_per_user", "interaction_rate", "voice_active_ratio", "occupancy"],
                })

        # CDN/区域故障
        if "first_frame_ms" in anomaly_metrics or "affected_region" in anomaly_metrics:
            hypotheses.append({
                "id": "h_cdn",
                "cause": "CDN/区域故障：特定区域延迟和首帧超时",
                "category": "cdn_fault",
                "evidence_needed": ["latency_ms", "first_frame_ms", "affected_region", "packet_loss_rate"],
            })

        # 网络抖动
        if "latency_variance_ms" in anomaly_metrics or "packet_loss_rate" in anomaly_metrics:
            if "jitter_burst_count" in anomaly_metrics or "latency_ms" in anomaly_metrics:
                hypotheses.append({
                    "id": "h_jitter",
                    "cause": "网络抖动：延迟方差和丢包率异常",
                    "category": "network_jitter",
                    "evidence_needed": ["latency_variance_ms", "packet_loss_rate", "jitter_burst_count"],
                })

        # 内容不匹配
        if "early_leave_rate" in anomaly_metrics or "avg_stay_duration_min" in anomaly_metrics:
            hypotheses.append({
                "id": "h_content",
                "cause": "内容不匹配：用户早退率高、停留时长短",
                "category": "content_mismatch",
                "evidence_needed": ["early_leave_rate", "avg_stay_duration_min", "audio_quality"],
            })

        # 通用流失
        if "user_drop_rate" in anomaly_metrics and not hypotheses:
            hypotheses.append({
                "id": "h_drop",
                "cause": "用户流失原因待定",
                "category": "unknown",
                "evidence_needed": ["全部指标"],
            })

        if not hypotheses:
            hypotheses.append({
                "id": "h0",
                "cause": "未知原因，需进一步数据",
                "category": "unknown",
                "evidence_needed": ["full_trace"],
            })
        return hypotheses
