# 语聊房运营哪些该上 Agent、哪些不该——附 LangGraph 多轮调查实现

> 本文以虚拟语聊房平台为例，从实际运营痛点出发，聊聊哪些场景值得用 AI Agent、哪些不该硬上，以及如何用 LangGraph 实现一个"会自己调查"的多轮 Agent 系统。文末附完整 eval 结果和判断清单。

---

## 一、痛点：语聊房运营为什么需要 Agent

做过语聊房运营的人都知道，日常巡检是个体力活：

- 每天扫几十个房间的指标：音频质量、互动分、用户流失率、主播活跃度……
- 发现异常后要跨系统取数：从指标平台拉数据、从告警系统查历史、从 SOP 里找处置方案
- 根因定位严重依赖个人经验，新人上手慢，一个"用户在跑"可能是音频卡了，也可能是主播挂机了，也可能是有人刷量
- 巡检动作高度重复，但判断逻辑不简单——不是简单的 if/else 能搞定的

这些特征叠在一起，就出现了一个问题：**这活该交给 AI Agent 吗？全交？还是有些不该？**

---

## 二、AI 适配性分级：不做伪 AI

不是所有运营场景都适合 Agent。核心判据就一条：**需不需要多轮推理 + 跨源整合 + 规划能力？**

| 分类 | 场景 | 适合方案 | 理由 |
|------|------|----------|------|
| A 类 · Agent 甜区 | 巡检决策、根因分析、策略建议 | LLM Agent | 需要多轮推理、跨源整合、规划 |
| B 类 · 规则/模型 | 内容合规初筛、异常检测触发 | 规则引擎/传统 ML | 分类/阈值/查表，确定性强 |

判断清单：

- ✅ 需要跨 2 个以上数据源才能下结论 → Agent
- ✅ 结论不是二分类，需要推理链 → Agent
- ✅ 上下文影响决策方向（同样的数据，活动期和非活动期结论不同）→ Agent
- ❌ 阈值判断就能搞定 → 规则
- ❌ 输入输出模式固定 → 传统模型
- ❌ 需要毫秒级响应 → 别用 LLM

**一句话原则：确定性问题用规则解，不确定性问题才请 Agent 出场。**

---

## 三、架构设计：Supervisor Loop + 专家 Agent

确定了哪些场景上 Agent 之后，下一步是怎么编排。我选的架构是 Supervisor Loop：一个 Supervisor 做规则路由，两个专家 Agent（巡检 + 根因分析）各管一摊。

```
                    ┌─────────────────────┐
                    │   Supervisor         │  规则路由（不调 LLM）
                    └──────────┬──────────┘
            ┌──────────────────┴──────────────────┐
            ▼                                     ▼
   ┌────────────────┐                    ┌────────────────┐
   │  Inspection     │  巡检               │   Analytics    │  根因分析
   │  取数→判断→移交  │                    │  假设→验证→收敛  │
   └───────┬────────┘                    └───────┬────────┘
           └──────────────────┬──────────────────┘
                              ▼
                    ┌──────────────────┐
                    │   Tool Layer      │  仿真数据后端
                    └──────────────────┘
```

几个关键设计决策：

**1. Supervisor 不调 LLM（ADR-004）**

Supervisor 只做路由决策，逻辑完全确定性——状态是 pending 就发给巡检，巡检发现异常就发给分析，分析完就结束。这种确定性编排用规则写，可靠、可测、便宜。

```python
class SupervisorAgent(BaseAgent):
    name = "supervisor"

    def _route(self, state: OpsState) -> str:
        if state.status == TaskStatus.PENDING:
            return "inspection"

        has_anomaly = any(
            f.severity in ("warning", "high", "critical")
            for f in state.findings
        )
        inspection_done = state.inspection_steps > 0

        if inspection_done and has_anomaly and not state.recommendation:
            return "analytics"

        return "end"
```

**2. 共享状态 OpsState（Pydantic v2）**

所有 Agent 读写同一个状态对象。`findings` 和 `decisions` 用 LangGraph 的 reducer 做追加合并，不会互相覆盖：

```python
class OpsState(BaseModel):
    findings: Annotated[list[Finding], operator.add] = Field(default_factory=list)
    decisions: Annotated[list[Decision], operator.add] = Field(default_factory=list)
    recommendation: Recommendation | None = None
    next: str = "supervisor"
    inspection_steps: int = 0
    analytics_steps: int = 0
    analytics_hypotheses: list[dict] = Field(default_factory=list)
```

**3. 分层就绪，不过度设计（ADR-001）**

只有一个域的时候不硬搭两层 Supervisor。当前两个专家 Agent 足够，未来扩展时再加层。

---

## 四、核心实现：LangGraph 多轮自主调查

这是本文的重点。两个 Agent 都不是"一次性 prompt → answer"，而是**多轮自主调查**——Agent 自己决定"还要不要继续查"。

### 4.1 巡检 Agent：3 步调查流程

```
Step 0: 拉平台大盘 → LLM 判断健康度
        ↓ (异常)
Step 1: 拉活跃告警 → 定位最可疑房间
        ↓ (有告警)
Step 2: 下钻房间指标 → 确认异常 or 判定误报
        ↓ (确认异常)
        设置 next="analytics"，移交根因分析
```

核心机制：**每步返回 `"next": "inspection"` 实现自循环**，图定义中 `inspection → inspection` 的 conditional edge 支持这个模式。

```python
async def run(self, state: OpsState, **kwargs) -> dict:
    steps = state.inspection_steps

    if steps == 0:
        return await self._step_overview(state, ...)    # 平台大盘
    elif steps == 1:
        return await self._step_alerts(state, ...)      # 拉告警
    elif steps == 2 and state.focus_room:
        return await self._step_drill_down(state, ...)  # 下钻确认
    else:
        return {..., "next": "supervisor"}              # 结束
```

每一步都用 LLM 结构化输出做判断：

```python
class InspectionJudgment(BaseModel):
    is_anomaly: bool = False
    severity: str = "info"
    summary: str = ""
    next_action: str = "end"
    reasoning: str = ""
```

LLM 输出结构化 schema，代码根据 `is_anomaly` 决定是继续调查还是收工。不是让 LLM 自由发挥，而是**约束输出空间，让 LLM 在框架内做判断**。

图定义支持自循环：

```python
graph.add_conditional_edges("inspection", _router, {
    "inspection": "inspection",  # 关键：支持自循环
    "supervisor": "supervisor",
    "analytics": "analytics",
    END: END,
})
```

### 4.2 根因分析 Agent：假设验证循环

巡检确认异常后移交给根因分析 Agent，这个 Agent 采用**假设驱动**的多轮分析模式：

```
Step 0: 基于异常指标生成假设列表
        ↓
Step 1..N: 逐个假设取证验证（每轮调工具 + LLM 评估）
        ↓ (高置信度 or 到达 max_steps)
收敛: 输出最终根因 + 可执行建议
```

假设生成基于异常指标的模式匹配：

```python
def _generate_hypotheses(self, anomaly_metrics, history):
    hypotheses = []
    if "host_speak_duration_min" in anomaly_metrics:
        hypotheses.append({"cause": "主播不活跃", "category": "host_inactive", ...})
    if "audio_error_rate" in anomaly_metrics:
        hypotheses.append({"cause": "音频系统故障", "category": "audio_failure", ...})
    if "gift_concentration" in anomaly_metrics:
        hypotheses.append({"cause": "刷量套利", "category": "fake_traffic", ...})
    # ...更多假设
    return hypotheses
```

验证环节用 LLM 做 structured output 评估：

```python
class HypothesisEvaluation(BaseModel):
    hypothesis: str = ""
    verified: bool = False
    confidence: float = 0.0
    evidence_summary: str = ""
    should_continue: bool = True
```

关键逻辑：**当某假设的置信度 ≥ 0.8 时提前收敛，不再浪费 token 验证剩余假设。**

```python
if (verified and confidence >= 0.8) or not should_continue:
    return await self._step_converge(state, findings, decisions, llm)
```

收敛阶段综合所有验证结果，输出最终根因和可执行建议：

```python
class RootCauseAnalysis(BaseModel):
    root_cause: str = ""
    confidence: float = 0.0
    evidence: list[str] = Field(default_factory=list)
    suggested_actions: list[str] = Field(default_factory=list)
    priority: str = "medium"
```

---

## 五、双模运行：Fake 模式 vs 真实模式

系统支持两种运行模式：

| 维度 | Fake 模式 | 真实模式 |
|------|-----------|---------|
| LLM 调用 | 无，规则兜底 | Claude Sonnet |
| 耗时 | <1ms | ~60-120s |
| 用途 | CI 回归、本地开发 | 质量评估、线上 |
| 确定性 | 完全确定 | 非确定性（N=3 投票） |

代码通过 `LLMClient.available` 属性做分支：

```python
if llm.available:
    judgment = await llm.invoke_structured(...)
    # 用 LLM 判断
else:
    if overview.get("health_score", 100) < 80:
        # 规则兜底
```

这意味着**契约层测试跑 fake 模式，快、确定、免费，可以进 CI**。质量评估跑真实模式，出指标。

---

## 六、Eval 体系：两层评估

### 6.1 契约层（CI 级别）

Fake 模式下的 pytest，验证路由逻辑和状态流转的正确性：

```
tests/evals/contract/test_routing.py — 5/5 PASSED (0.13s)
```

测什么：
- 健康平台不升级
- 异常+告警时升级到分析
- 异常但无告警时不升级
- 分析 Agent 无焦点房间时拒绝
- 多轮步骤递增

### 6.2 质量层（真实 LLM）

真实 Claude 跑全链路，N=3 次/case 抗非确定性，Opus + 温度 0 做 Judge：

```
分类指标: accuracy=1.00 precision=1.00 recall=1.00 误报率=0.00
根因命中率(Judge): 0.93
  easy cases 均分: 1.00
  hard cases 均分: 0.75
```

**hard case 区分度**：`q_anly_04`（挂机刷在线时长）Agent 3 次运行均输出 `host_inactive`，被 Judge 判为 partial (0.5)——识别到了"无互动"但没精确归因为"故意挂机刷时长"。说明 eval 不是走过场，hard case 确实在暴露 Agent 的短板。

### Judge 设计

```python
class JudgeVerdict(BaseModel):
    verdict: Literal["correct", "partial", "wrong"] = "wrong"
    score: float = Field(ge=0, le=1, default=0.0)
    reason: str = ""
```

评分标准简单粗暴：
- correct (1.0): 命中根因类别且证据合理
- partial (0.5): 方向对但不全/证据弱
- wrong (0.0): 方向错

---

## 七、可观测：自建轻量 Tracing

不用 LangSmith 也不用 Jaeger，自建了一个轻量 Tracing（ADR-002）——每任务一个 trace_id，逐 span 记录耗时和元数据：

```python
class Tracer:
    @classmethod
    @contextmanager
    def span(cls, trace_id: str, name: str) -> Generator[Span, None, None]:
        s = Span(name=name, trace_id=trace_id)
        try:
            yield s
        finally:
            s.finish()
            trace.add_span(s)
            logger.info("span_finished", span=s.to_dict())
```

输出效果：

```
span_finished  span={'name': 'inspection_overview_llm', 'duration_ms': 8818.51, 'metadata': {'model': 'claude-sonnet-4-20250514', 'schema': 'InspectionJudgment'}}
span_finished  span={'name': 'analytics_converge_llm', 'duration_ms': 19384.83, 'metadata': {'model': 'claude-sonnet-4-20250514', 'schema': 'RootCauseAnalysis'}}
```

每个 LLM 调用多少毫秒、用的什么 schema，一目了然。decisions 日志支持回放复盘——出了问题可以还原"Agent 当时为什么做了这个决定"。

---

## 八、关键 ADR 汇总

| ADR | 决策 | 不选另一个的理由 |
|-----|------|----------------|
| 001 | 分层就绪，不过度设计 | 一个域硬搭两层 Supervisor = 过度工程 |
| 002 | 可观测自建 | 数据可控、不依赖第三方、理解每个 span 在干嘛 |
| 003 | 仿真数据生成器（固定种子） | demo 靠数据真实感说服力，种子固定保证可复现 |
| 004 | Supervisor 规则路由不调 LLM | 确定性问题用规则：可靠、可测、便宜 |

---

## 九、总结

回到开头的问题：**语聊房运营哪些该上 Agent？**

用 Agent 的场景，核心特征是：**跨源取数 + 多轮推理 + 上下文相关的判断**。巡检决策和根因分析都符合这个特征——不是一条规则能搞定的，需要 Agent "自己决定还要不要继续查"。

不用 Agent 的场景：阈值触发、内容审核初筛、固定模式的分类任务。这些用规则引擎或传统 ML，快、确定、成本低。

最后一个工程建议：**Supervisor 不调 LLM**。编排逻辑是确定性的，用规则写就够了。把 LLM 的算力留给真正需要推理的地方。

---

## 判断清单（可直接拿走用）

你的场景该不该上 Agent？对着这个清单打勾：

| 信号 | 判断 |
|------|------|
| 需要跨 2+ 数据源才能下结论 | → Agent |
| 结论需要推理链，不是二分类 | → Agent |
| 同样的数据，上下文不同结论不同 | → Agent |
| 阈值判断就能搞定 | → 规则 |
| 输入输出模式固定 | → 传统模型 |
| 需要毫秒级响应 | → 别用 LLM |

3 个以上打了 Agent 的勾 → 上 Agent 有价值。否则老老实实写规则，别为了"AI"而 AI。

---

*项目使用 Python 3.12 + LangGraph + Claude Sonnet，全部数据为虚拟平台仿真，无任何真实业务数据。*
