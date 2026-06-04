# vcr-ops-agent 质量层 Eval 报告

- 运行时间: 2026-06-04 10:22–10:55 (约 33 min)
- 配置: 真实模式, N=3 次/case, Judge=Claude Opus + 温度 0
- 模型: claude-sonnet-4-20250514

## 分类指标

| 指标 | 值 |
|------|-----|
| Accuracy | 1.00 |
| Precision | 1.00 |
| Recall | 1.00 |
| 误报率 (FPR) | 0.00 |
| 根因命中率 (Judge) | 0.93 |

混淆矩阵: TP=7, FP=0, TN=3, FN=0

## 根因命中率分层

| 难度 | Judge 均分 | Case 数 |
|------|-----------|---------|
| easy | 1.00 | 4 |
| medium | 1.00 | 1 |
| hard | 0.75 | 2 |

## 逐 Case 明细

| Case | 名称 | 难度 | 分类结果 | Judge 均分 | 备注 |
|------|------|------|----------|-----------|------|
| q_insp_01 | 音频质量劣化 | easy | ✓ TP | 1.00 | 3/3 correct |
| q_insp_02 | 主播挂机 | easy | ✓ TP | 1.00 | 3/3 correct |
| q_insp_03 | 正常平台无异常 | easy | ✓ TN | — | 无需 judge |
| q_insp_04 | 假阳性陷阱：活动期礼物陡增 | hard | ✓ TN | — | 无需 judge |
| q_insp_05 | 多房间同时劣化 | medium | ✓ TN | — | 无需 judge |
| q_anly_01 | 音频编解码故障 | easy | ✓ TP | 1.00 | 3/3 correct |
| q_anly_02 | 主播状态低迷 | easy | ✓ TP | 1.00 | 3/3 correct |
| q_anly_03 | 刷量套利 | hard | ✓ TP | 1.00 | 3/3 correct |
| q_anly_04 | 挂机刷在线时长 | hard | ✓ TP | 0.50 | 3/3 partial |
| q_anly_05 | 网络抖动 | medium | ✓ TP | 1.00 | 3/3 correct |

## 区分度分析

hard case `q_anly_04`（挂机刷在线时长）3 次运行均被 Judge 判定为 partial (0.5)：

- Agent 输出: `host_inactive`（主播不活跃）
- 预期根因: `挂机刷在线`
- Judge 评语: 识别到高 occupancy 但无互动的现象，方向正确但未精确归因为用户故意挂机刷时长

说明 hard case 具备区分度，Agent 在复杂场景下仍有提升空间。

## 契约层 (CI)

```
tests/evals/contract/test_routing.py — 5/5 PASSED (0.13s, fake 模式)
```

## 结论

- 契约层 fake 模式 pytest 全绿，可进 CI（快、确定、免费）
- 质量层真实模式五项指标均已产出，hard case 未全过，有区分度
- 下一步优化方向: `q_anly_04` 根因识别需增强对"挂机刷在线"与"主播低迷"的区分能力
