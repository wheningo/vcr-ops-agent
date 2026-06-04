# vcr-ops-agent

虚拟语聊房运营 Agent — LangGraph Supervisor + 专家 Agent，自动化巡检→根因分析决策链。

## 架构

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

- **Supervisor**: 规则路由，不调 LLM，确定性编排
- **Inspection Agent**: 多轮自主巡检（平台大盘 → 拉告警 → 下钻确认）
- **Analytics Agent**: 假设驱动的根因分析（生成假设 → 逐个验证 → 收敛结论）

## 快速开始

```bash
# 克隆
git clone https://github.com/<your-username>/vcr-ops-agent.git
cd vcr-ops-agent

# 安装依赖（需要 Python 3.12+，推荐用 uv）
uv sync

# Fake 模式运行（无需 API Key）
VCR_OPS_FAKE_MODE=true uv run vcr-ops

# 真实模式运行（需要 Anthropic API Key）
cp .env.example .env
# 编辑 .env 填入你的 ANTHROPIC_API_KEY
uv run vcr-ops
```

## 双模运行

| 模式 | LLM 调用 | 耗时 | 用途 |
|------|----------|------|------|
| Fake | 无，规则兜底 | <1ms | CI 回归、本地开发 |
| 真实 | Claude Sonnet | ~60-120s | 质量评估、线上 |

通过环境变量 `VCR_OPS_FAKE_MODE=true` 切换。

## 测试

```bash
# 契约层 — fake 模式，快、确定、免费
uv run pytest tests/evals/contract/ -v

# 质量层 — 真实 LLM，需要 API Key
uv run python tests/evals/quality/run.py
```

## Eval 体系

两层评估设计：

**契约层** (CI): Fake 模式下 pytest，验证路由逻辑和状态流转。

**质量层** (真实 LLM): N=3 次/case 抗非确定性，Opus + 温度 0 做 Judge，输出五个指标：
- Accuracy / Precision / Recall / 误报率 / 根因命中率

## 项目结构

```
src/vcr_ops_agent/
├── agents/
│   ├── supervisor.py   # 规则路由
│   ├── inspection.py   # 巡检 Agent
│   └── analytics.py    # 根因分析 Agent
├── tools/              # 仿真数据工具
├── simulator/          # 场景仿真（固定种子可复现）
├── tracing/            # 自建轻量 Tracing
├── state.py            # OpsState 共享状态
├── graph.py            # LangGraph 图定义
├── llm.py              # LLM 客户端封装
└── config.py           # 配置管理
tests/evals/
├── contract/           # 契约层测试
└── quality/            # 质量层评估
```

## 设计决策

| ADR | 决策 | 理由 |
|-----|------|------|
| 001 | 分层就绪，不过度设计 | 一个域不硬搭两层 Supervisor |
| 002 | 可观测自建 | 数据可控、不依赖第三方 |
| 003 | 仿真数据生成器（固定种子） | 可复现，demo 有说服力 |
| 004 | Supervisor 规则路由 | 确定性问题用规则：可靠、可测、便宜 |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ANTHROPIC_API_KEY` | Anthropic API Key | (空，走 fake 模式) |
| `ANTHROPIC_BASE_URL` | API 代理地址 | (空，用官方) |
| `VCR_OPS_MODEL` | 模型名 | `claude-sonnet-4-20250514` |
| `VCR_OPS_FAKE_MODE` | 强制 fake 模式 | `false` |
| `VCR_OPS_MAX_TOKENS` | 最大输出 token | `2048` |
| `VCR_OPS_TEMPERATURE` | 温度 | `0.3` |

## License

[Apache License 2.0](LICENSE)
