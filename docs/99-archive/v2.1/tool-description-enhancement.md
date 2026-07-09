# 工具描述增强规范

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 需求设计 |
| 日期 | 2026-02-07 |
| 优先级 | 高（智能助手的前置依赖） |

---

## 🎯 背景

### 为什么需要增强工具描述

要实现 Agent 自主编排（Function Calling），LLM 必须能准确理解每个工具的用途、输入输出。目前 `tool_configs` 集合中的工具描述过于简单，无法支撑 LLM 做出准确的工具选择。

### 现状 vs 目标

```
现在的 tool_configs：
┌─────────────────────────────┐
│ name: "get_financial_data"  │
│ description: "获取财务数据"  │  ← 太简单，LLM 不知道什么时候该用
│ parameters: { code: str }   │
└─────────────────────────────┘

需要增强为：
┌──────────────────────────────────────────────┐
│ name: "get_financial_data"                   │
│                                              │
│ description: "获取股票的核心财务指标，包括     │
│   PE、PB、ROE、营收增长率、净利润增长率等。   │
│   适用于基本面分析、估值判断、选股筛选。      │
│   返回最近 4 个季度的数据。"                  │
│                                              │
│ when_to_use: "当用户询问股票的估值是否合理、  │
│   财务状况如何、基本面好不好时使用"            │
│                                              │
│ parameters:                                  │
│   code: "股票代码，如 600519"                 │
│   period: "可选，quarterly/annual"            │
│                                              │
│ returns: "包含 PE、PB、ROE 等字段的字典"      │
│                                              │
│ example: "get_financial_data('600519')"       │
└──────────────────────────────────────────────┘
```

---

## 📝 增强字段规范

### 必填字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 工具名称（已有） |
| `description` | string | **详细描述**：功能说明 + 适用场景 + 返回数据概述 |
| `when_to_use` | string | **使用时机**：什么情况下 Agent 应该选择这个工具 |
| `parameters` | object | **参数规范**：每个参数的名称、类型、描述、是否必填 |
| `returns` | string | **返回值描述**：返回数据的结构和字段说明 |

### 可选字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `example` | string | 调用示例 |
| `when_not_to_use` | string | 不应使用的场景（避免误用） |
| `limitations` | string | 限制说明（数据范围、频率限制等） |
| `related_tools` | list | 相关工具（经常一起使用的工具） |

---

## 📊 工具描述模板

### 数据查询类工具

```json
{
    "name": "get_financial_summary",
    "description": "获取股票的核心财务指标摘要，包括：市盈率(PE)、市净率(PB)、净资产收益率(ROE)、营收增长率、净利润增长率、毛利率、资产负债率等。数据来源为最近公布的财报，覆盖最近4个季度。适用于评估股票的基本面质量和估值水平。",
    "when_to_use": "当需要判断一只股票的基本面好不好、估值贵不贵、财务是否健康时使用。常见用户问题：'这只股票估值合理吗'、'基本面怎么样'、'财务状况如何'。",
    "when_not_to_use": "不适用于判断短期走势（应使用 get_technical_summary）；不包含实时价格（应使用 get_market_quotes）。",
    "parameters": {
        "code": {
            "type": "string",
            "required": true,
            "description": "股票代码，6位数字，如 '600519'（贵州茅台）、'000858'（五粮液）"
        }
    },
    "returns": "返回字典，包含字段：pe(市盈率)、pb(市净率)、roe(净资产收益率%)、revenue_growth(营收增长率%)、profit_growth(净利润增长率%)、gross_margin(毛利率%)、debt_ratio(资产负债率%)",
    "example": "get_financial_summary('600519') → {'pe': 28.5, 'pb': 8.2, 'roe': 31.5, ...}",
    "related_tools": ["get_market_quotes", "compare_stocks"]
}
```

### 分析类工具

```json
{
    "name": "compare_stocks",
    "description": "对多只股票进行多维度对比分析，支持的维度包括：基本面(PE/PB/ROE)、技术面(趋势/动量)、估值(相对估值水平)、成长性(营收/利润增速)。适合同行业或同板块的股票横向对比。",
    "when_to_use": "当用户要在多只股票中做选择、对比优劣、或了解同行业股票差异时使用。常见问题：'茅台和五粮液哪个好'、'半导体板块里选几只'。",
    "parameters": {
        "codes": {
            "type": "array",
            "required": true,
            "description": "股票代码列表，至少2只，建议不超过10只"
        },
        "dimensions": {
            "type": "array",
            "required": false,
            "description": "对比维度，可选：'fundamental'(基本面)、'technical'(技术面)、'valuation'(估值)、'growth'(成长性)。默认全部维度。"
        }
    },
    "returns": "返回对比结果表格，包含各股票在各维度的评分和排名",
    "example": "compare_stocks(['600519','000858','000568'], ['fundamental','valuation'])"
}
```

### 触发工作流类工具

```json
{
    "name": "trigger_full_analysis",
    "description": "触发完整的多Agent深度分析工作流，包含市场分析、基本面分析、技术分析、新闻分析、综合研判等多个步骤，生成结构化的深度分析报告。这是最全面但也最耗时的分析方式，通常需要3-5分钟完成。",
    "when_to_use": "当用户明确要求'详细分析'、'深度分析'某只股票时使用。或者当快速查询的结果不够详细，需要更深入的分析时使用。",
    "when_not_to_use": "用户只是随便问问、想快速了解概况时不要触发。初步筛选时不需要。",
    "parameters": {
        "code": {
            "type": "string",
            "required": true,
            "description": "要分析的股票代码"
        },
        "workflow_id": {
            "type": "string",
            "required": false,
            "description": "工作流ID，不指定则使用默认的深度分析工作流"
        }
    },
    "returns": "返回任务ID，可通过任务ID查询分析进度和结果",
    "example": "trigger_full_analysis('600519') → {'task_id': 'xxx', 'estimated_time': '5min'}"
}
```

---

## 🔧 迁移计划

### 第一步：梳理现有工具

从 `tool_configs` 集合中导出所有工具，按类别整理：

| 类别 | 预估数量 | 说明 |
|------|---------|------|
| 数据查询类 | 8-12 个 | 行情、财务、新闻、技术指标等 |
| 分析计算类 | 3-5 个 | 对比、筛选、排名等 |
| 工作流触发类 | 2-3 个 | 深度分析、定时任务等 |
| 报告类 | 2-3 个 | 报告查询、报告解读等 |

### 第二步：逐个补全描述

对每个工具补全 `description`、`when_to_use`、`parameters`、`returns` 字段。

**优先级**：先补全智能助手最常用的工具（数据查询类），再补全分析类和工作流触发类。

### 第三步：验证 Function Calling 效果

1. 准备一组测试问题（覆盖各种场景）
2. 将增强后的工具描述提交给 LLM
3. 验证 LLM 能否正确选择工具
4. 根据结果调整描述

### 数据库字段变更

在 `tool_configs` 集合中新增以下字段（向后兼容，都是可选字段）：

```javascript
// tool_configs 集合新增字段
{
    // 已有字段
    "tool_id": "...",
    "name": "...",
    "description": "...",     // 增强为详细描述
    "parameters": {...},

    // 新增字段
    "when_to_use": "...",     // 使用时机
    "when_not_to_use": "...", // 不应使用的场景
    "returns": "...",         // 返回值描述
    "example": "...",         // 调用示例
    "related_tools": [...],   // 相关工具
    "limitations": "...",     // 限制说明
    "fc_enabled": true        // 是否启用 Function Calling
}
```

---

## 📊 工作量评估

| 步骤 | 工作量 | 说明 |
|------|--------|------|
| 梳理现有工具 | 0.5 天 | 从数据库导出，分类整理 |
| 补全描述（15-20个工具） | 2-3 天 | 每个工具需要测试验证 |
| 数据库字段迁移 | 0.5 天 | 新增字段，向后兼容 |
| Function Calling 验证 | 1-2 天 | 测试 + 调优 |
| **合计** | **4-6 天** | |

---

## 🔗 相关文档

- [智能助手设计](./intelligent-assistant-design.md)（工具描述的消费方）
- [v2.0 工具系统](../v2.0/tools/)（现有工具设计）
- [v2.1 插件平台概念](../v2.1/plugin-platform-concept.md)

---

**创建日期**: 2026-02-07
**最后更新**: 2026-02-07