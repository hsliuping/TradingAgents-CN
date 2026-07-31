# 阶段 1:发现——从 6000 只股票里找到值得研究的

> **5 课** | **总课时**: 约 2 小时 | **难度**: ⭐ 入门

## 🎯 阶段目标

完成本阶段后,你能从 6000 只 A 股里,**系统化**地筛出 10 只值得深度研究的股票。

## 📍 阶段路线图

```
6000 只 A 股
   │
   │  第 1 课: 自然语言筛选 / 条件筛选
   ↓
500-1000 只
   │
   │  第 2 课: 批量分析(单次 ≤ 10 只,分批跑)
   ↓
50-100 只
   │
   │  第 3 课: 单股研究(3 档标准深度)
   ↓
10-20 只
   │
   │  第 4 课: 多角色辩论(4-5 档深度)
   ↓
2-3 只核心标的
   │
   │  第 5 课: 避雷清单(经验沉淀)
   ↓
[阶段 2:跟踪] 或 [阶段 3:建仓]
```

## 📚 课程列表

| 课 | 主题 | 时长 | 关键产出 |
|----|------|------|---------|
| [第 1 课](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/phase-01-discover/lesson-01-stock-screening.md) | 股票筛选(自然语言 + 条件) | 20 分钟 | 500-1000 只股票池 |
| [第 2 课](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/phase-01-discover/lesson-02-batch-analysis.md) | 批量分析(单次 ≤ 10 只) | 25 分钟 | 50 只窄选 |
| [第 3 课](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/phase-01-discover/lesson-03-single-analysis-basic.md) | 单股研究入门(5 档深度) | 30 分钟 | 10-20 只深度研究 |
| [第 4 课](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/phase-01-discover/lesson-04-single-analysis-multi-scenario.md) | 多角色辩论(3 角色) | 30 分钟 | 2-3 只核心标的 |
| [第 5 课](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/phase-01-discover/lesson-05-discover-pitfalls.md) | 发现阶段常见错误 | 25 分钟 | 个人避雷清单 |

## 🔑 阶段关键概念(基于真实功能)

- **自然语言筛选**: `/screening` 默认 Tab,基于 LLM 意图理解,支持多轮对话
- **条件筛选**: `/screening` "高级模式" Tab,精确字段构建
- **批量分析**: `/analysis/batch`,单次最多 10 只,5 档深度
- **单股研究**: `/analysis/single`,5 档深度,12 个子报告
- **3 角色辩论**: bull_researcher / bear_researcher / neutral_analyst(4-5 档)
- **3 风险视角**: risky_analyst / safe_analyst / neutral_analyst(4-5 档)
- **合规术语**: 决策 action ∈ {乐观, 审慎, 中性}(不是 买入/卖出/持有)

## ⚠️ 阶段限制(基于实际代码)

- ⚠️ **平台仅支持 A 股和 ETF 基金**(港美股前端入口已下线)
- ⚠️ **批量分析单次 ≤ 10 只**(后端硬限制)
- ⚠️ **京东云版单并发**,批量任务串行执行
- ⚠️ **1-3 档深度无辩论角色**,4-5 档才有

## 🎓 学完后能做什么

完成本阶段后,你可以:
- 用一句话告诉 AI"我要什么股票"
- 一次性分析 10 只股票
- 读懂 12 个子报告的含义
- 识别 AI 报告的合规术语
- 避开新手最常见的 7 个错误

## ⏭️ 下一步

完成本阶段后,进入 [**阶段 2:跟踪**](file:///c:/TradingAgentsCN/docs/07-courses/v3.0/phase-02-track/README.md)——研究完后,怎么持续跟踪?

也可以根据实际情况**提前进入阶段 3**(持仓)或**阶段 4**(复盘)。
