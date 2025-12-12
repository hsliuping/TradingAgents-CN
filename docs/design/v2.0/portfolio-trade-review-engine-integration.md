# 持仓分析与复盘分析引擎集成设计

## 1. 背景与目标

### 1.1 现状分析

当前持仓分析（`portfolio_service.py`）和操作复盘（`trade_review_service.py`）功能存在以下问题：

| 问题 | 当前状态 | 目标状态 |
|------|---------|---------|
| 提示词管理 | 硬编码在代码中 | 使用统一的提示词模板系统 |
| 单股分析 | 调用旧版 `simple_analysis_service` | 调用 v2 版 `StockAnalysisEngine` |
| 输出格式 | 各服务自定义，口径不统一 | 统一的 JSON 输出规范 |
| 风格配置 | 不支持 | 支持保守/中性/激进三档风格 |
| 可运营性 | 改动需发版 | 模板可在线编辑、热更新 |

### 1.2 目标

1. **模板化提示词**：将持仓分析和复盘分析的提示词迁移到模板系统
2. **引擎集成**：持仓分析复用 v2 版 `StockAnalysisEngine` 的单股分析结果
3. **风格化支持**：支持根据用户偏好选择不同风格的分析模板
4. **灰度可控**：通过特性开关控制新旧逻辑切换，支持回退

---

## 2. 集成架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              用户请求                                        │
│                    (持仓分析 / 单股持仓分析 / 操作复盘)                        │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Portfolio/Review Service                           │
│  ┌─────────────────────────────────────────────────────────────────────────┐ │
│  │                        特性开关层                                        │ │
│  │  USE_TEMPLATE_PROMPTS=true/false    USE_STOCK_ENGINE=true/false        │ │
│  └─────────────────────────────────────────────────────────────────────────┘ │
│                                    │                                         │
│           ┌────────────────────────┼────────────────────────┐               │
│           ▼                        ▼                        ▼               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐         │
│  │ 模板化提示词生成 │    │  引擎调用适配层  │    │  旧版硬编码逻辑  │         │
│  │ (TemplateClient) │    │(StockAnalysisEngine)│  │   (降级兜底)    │         │
│  └─────────────────┘    └─────────────────┘    └─────────────────┘         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LLM 调用层                                      │
│                  (统一的 LLM 适配器，支持多模型提供商)                         │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           结果解析与存储                                     │
│              (JSON 优先解析 + 正则兜底，存储到 MongoDB)                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流设计

#### 持仓分析数据流

```
用户发起持仓分析
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ 阶段1: 获取单股分析报告                                        │
│  ├── USE_STOCK_ENGINE=true  → StockAnalysisEngine.analyze()  │
│  │   └── 返回: context.reports + final_decision              │
│  └── USE_STOCK_ENGINE=false → simple_analysis_service (旧版) │
│       └── 返回: 原有报告格式                                   │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ 阶段2: 构建持仓分析提示词                                      │
│  ├── USE_TEMPLATE_PROMPTS=true                               │
│  │   └── get_agent_prompt("trader", "position_advisor", ...) │
│  └── USE_TEMPLATE_PROMPTS=false                              │
│       └── _build_position_analysis_prompt_v2() (硬编码)       │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│ 阶段3: 调用 LLM 并解析结果                                    │
│  └── _parse_position_ai_response_v2() → PositionAnalysisResult│
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 模板系统集成

### 3.1 新增模板定义

需要在 MongoDB `prompt_templates` 集合中创建以下模板：

| agent_type | agent_name | 用途 | 风格变体 |
|------------|------------|------|----------|
| trader | position_advisor | 单股持仓分析建议 | neutral/conservative/aggressive |
| managers | trade_reviewer | 单笔/完整交易复盘 | neutral/conservative/aggressive |
| managers | periodic_reviewer | 阶段性复盘 | neutral/conservative/aggressive |
| managers | portfolio_analyst | 组合层分析（预留） | neutral/conservative/aggressive |

### 3.2 模板变量规范

#### position_advisor 模板变量

```python
{
    # 持仓信息
    "position": {
        "code": str,              # 股票代码
        "name": str,              # 股票名称
        "quantity": int,          # 持仓数量
        "cost_price": float,      # 成本价
        "current_price": float,   # 现价
        "market_value": float,    # 市值
        "holding_days": int,      # 持仓天数
        "unrealized_pnl": float,  # 浮动盈亏
        "unrealized_pnl_pct": float,  # 浮动盈亏%
        "industry": str           # 所属行业
    },
    
    # 账户与仓位
    "capital": {
        "total_assets": float,    # 总资产
        "position_pct": float,    # 该股占比%
        "position_risk_level": str  # 仓位风险等级
    },
    
    # 用户设置
    "goal": {
        "target_profit_pct": float,   # 目标收益率%
        "max_loss_pct": float,        # 最大亏损容忍%
        "include_add_position": bool  # 是否分析加仓
    },
    
    # 单股分析报告（来自 StockAnalysisEngine）
    "engine": {
        "market_report": str,         # 技术分析报告
        "fundamentals_report": str,   # 基本面报告
        "news_report": str,           # 新闻分析报告
        "sentiment_report": str,      # 情绪分析报告
        "sector_report": str,         # 板块分析报告
        "final_decision": {           # 最终决策
            "action": str,            # 建议操作
            "target_price": float,    # 目标价
            "reason": str             # 决策理由
        }
    },
    
    # 上下文
    "context": {
        "analysis_date": str,         # 分析日期
        "user_style": str             # 用户风格偏好
    }
}
```

#### trade_reviewer 模板变量

```python
{
    # 交易信息
    "trade": {
        "code": str,              # 股票代码
        "name": str,              # 股票名称
        "market": str,            # 市场 (CN/HK/US)
        "trades_table": str,      # 交易明细表（格式化文本）
        "first_buy_date": str,    # 首次买入日期
        "last_sell_date": str,    # 最后卖出日期
        "holding_days": int,      # 持仓天数
        "total_buy_amount": float,    # 总买入金额
        "total_sell_amount": float,   # 总卖出金额
        "realized_pnl": float,        # 实现盈亏
        "realized_pnl_pct": float     # 实现盈亏%
    },

    # 市场快照
    "market_snapshot": {
        "period_high": float,         # 期间最高价
        "period_high_date": str,      # 最高价日期
        "period_low": float,          # 期间最低价
        "period_low_date": str,       # 最低价日期
        "buy_day_ohlc": str,          # 买入当日OHLC
        "sell_day_ohlc": str,         # 卖出当日OHLC
        "recent_kline_table": str     # 近期K线表格
    },

    # 上下文
    "context": {
        "review_type": str,           # 复盘类型 (single/complete/periodic)
        "user_id": str,               # 用户ID
        "user_style": str             # 用户风格偏好
    }
}
```

### 3.3 输出格式规范

所有模板的输出必须符合统一的 JSON 结构：

```json
{
    "action": "add|reduce|hold|clear",
    "action_reason": "操作建议理由",
    "confidence": 75,
    "price_targets": {
        "take_profit_price": 180.0,
        "stop_loss_price": 150.0,
        "add_position_price": 155.0
    },
    "risk_assessment": {
        "level": "low|medium|high",
        "key_risks": ["风险点1", "风险点2"]
    },
    "evidence": ["支撑证据1", "支撑证据2"],
    "triggers": ["触发条件1", "触发条件2"]
}
```

---

## 4. 代码改造方案

### 4.1 portfolio_service.py 改造

#### 4.1.1 新增特性开关

```python
# app/services/portfolio_service.py

import os

# 特性开关
USE_TEMPLATE_PROMPTS = os.getenv("USE_TEMPLATE_PROMPTS", "false").lower() == "true"
USE_STOCK_ENGINE = os.getenv("USE_STOCK_ENGINE", "false").lower() == "true"
```

#### 4.1.2 单股分析调用改造

```python
async def _get_stock_analysis_report(
    self, user_id: str, stock_code: str, market: str
) -> dict:
    """获取单股分析报告，优先使用新引擎"""

    if USE_STOCK_ENGINE:
        try:
            from tradingagents.core.engine.stock_analysis_engine import StockAnalysisEngine

            engine = StockAnalysisEngine(use_stub=False)
            result = engine.analyze(
                ticker=stock_code,
                trade_date=datetime.now().strftime("%Y-%m-%d"),
                market_type="cn" if market == "CN" else market.lower()
            )

            if result and result.success:
                return {
                    "task_id": "engine",
                    "source": "stock_analysis_engine",
                    "reports": result.context.reports,
                    "decision": result.final_decision
                }
        except Exception as e:
            logger.warning(f"StockAnalysisEngine failed, fallback to legacy: {e}")

    # 降级到旧版服务
    return await self._get_stock_analysis_report_via_legacy(user_id, stock_code, market)
```

#### 4.1.3 提示词构建改造

```python
def _build_position_analysis_prompt_v2(
    self, snapshot: dict, params: dict, stock_analysis_report: dict
) -> str:
    """构建持仓分析提示词，优先使用模板系统"""

    # 构建硬编码版本作为降级兜底
    legacy_prompt = self._build_legacy_position_prompt(snapshot, params, stock_analysis_report)

    if not USE_TEMPLATE_PROMPTS:
        return legacy_prompt

    try:
        from tradingagents.utils.template_client import get_agent_prompt

        variables = self._build_position_vars(snapshot, params, stock_analysis_report)

        prompt = get_agent_prompt(
            agent_type="trader",
            agent_name="position_advisor",
            variables=variables,
            user_id=params.get("user_id"),
            preference_id=params.get("invest_style"),
            fallback_prompt=legacy_prompt
        )
        return prompt

    except Exception as e:
        logger.warning(f"Template prompt failed, fallback to legacy: {e}")
        return legacy_prompt
```

### 4.2 trade_review_service.py 改造

#### 4.2.1 提示词构建改造

```python
def _build_trade_review_prompt(
    self, trade_info: dict, market_snapshot: dict, user_id: str = None
) -> str:
    """构建交易复盘提示词，优先使用模板系统"""

    # 构建硬编码版本作为降级兜底
    legacy_prompt = self._build_legacy_review_prompt(trade_info, market_snapshot)

    if not USE_TEMPLATE_PROMPTS:
        return legacy_prompt

    try:
        from tradingagents.utils.template_client import get_agent_prompt

        variables = self._build_trade_review_vars(trade_info, market_snapshot)

        prompt = get_agent_prompt(
            agent_type="managers",
            agent_name="trade_reviewer",
            variables=variables,
            user_id=user_id,
            preference_id=None,  # 复盘暂不区分风格
            fallback_prompt=legacy_prompt
        )
        return prompt

    except Exception as e:
        logger.warning(f"Template prompt failed, fallback to legacy: {e}")
        return legacy_prompt
```

---

## 5. 模板内容示例

### 5.1 position_advisor (neutral 风格)

```markdown
# 单股持仓分析任务

## 持仓信息
- 股票: {{position.code}} {{position.name}}
- 持仓数量: {{position.quantity}} 股
- 成本价: {{position.cost_price}} 元
- 当前价: {{position.current_price}} 元
- 市值: {{position.market_value}} 元
- 浮动盈亏: {{position.unrealized_pnl}} 元 ({{position.unrealized_pnl_pct}}%)
- 持仓天数: {{position.holding_days}} 天
- 该股占组合比例: {{capital.position_pct}}%

## 用户目标
- 目标收益率: {{goal.target_profit_pct}}%
- 最大亏损容忍: {{goal.max_loss_pct}}%

## 单股分析报告摘要
### 技术面
{{engine.market_report}}

### 基本面
{{engine.fundamentals_report}}

### 新闻面
{{engine.news_report}}

### 综合决策
{{engine.final_decision.action}} - {{engine.final_decision.reason}}

## 分析要求
请基于用户的持仓成本和目标，结合以上分析报告，给出个性化的操作建议：

1. **操作建议** (四选一: add/reduce/hold/clear)
2. **价位建议** (止盈价/止损价/加仓价)
3. **风险评估** (当前持仓风险等级和关键风险点)
4. **触发条件** (何时执行建议操作)

请以 JSON 格式输出，结构如下：
```json
{
    "action": "hold",
    "action_reason": "...",
    "confidence": 75,
    "price_targets": {...},
    "risk_assessment": {...},
    "evidence": [...],
    "triggers": [...]
}
```
```

---

## 6. 实现计划

### Phase 1: P0 最小改造 (1-2 周)

| 任务 | 文件 | 说明 |
|------|------|------|
| 添加特性开关 | `portfolio_service.py`, `trade_review_service.py` | 环境变量控制 |
| 变量构建函数 | `portfolio_service.py` | `_build_position_vars()` |
| 变量构建函数 | `trade_review_service.py` | `_build_trade_review_vars()` |
| 模板调用适配 | `portfolio_service.py` | 调用 `get_agent_prompt` |
| 模板调用适配 | `trade_review_service.py` | 调用 `get_agent_prompt` |
| 引擎调用适配 | `portfolio_service.py` | 优先调用 `StockAnalysisEngine` |
| 创建系统模板 | MongoDB | position_advisor, trade_reviewer |

### Phase 2: P1 深化融合 (2-4 周)

| 任务 | 说明 |
|------|------|
| 三档风格模板 | 为每个 agent 创建 neutral/conservative/aggressive 变体 |
| 引擎输出直连 | 模板变量直接映射引擎的 reports/decisions 字段 |
| 埋点与指标 | 记录模板使用率、回退率、解析成功率 |
| 模板管理界面 | 支持在线编辑和预览模板 |

---

## 7. 验收标准

### 7.1 P0 验收标准

- [ ] 特性开关关闭时，行为与现网完全一致
- [ ] 特性开关开启但模板不存在时，自动降级到硬编码提示词
- [ ] 引擎调用失败时，自动降级到旧版 `simple_analysis_service`
- [ ] JSON 解析成功率 ≥ 95%
- [ ] 接口响应时间 ≤ 现有 + 20%

### 7.2 灰度策略

1. **内测阶段**: 仅开发/测试账户开启特性开关
2. **小流量阶段**: 5% 用户开启，观察埋点数据
3. **全量阶段**: 确认无问题后全量开启

---

## 8. 风险与规避

| 风险 | 规避措施 |
|------|---------|
| 引擎依赖环境未就绪 | `use_stub=True` 或旧服务兜底 |
| 模板未发布或变量缺失 | `get_agent_prompt` 内置降级 |
| 输出字段不一致 | JSON 优先 + 正则兜底解析 |
| 性能下降 | 复用现有缓存逻辑，引擎结果可缓存 |

---

## 9. 相关文档

- [持仓分析功能设计](../professional-edition/portfolio-analysis-design.md)
- [操作复盘功能设计](../professional-edition/trade-review-design.md)
- [股票分析专用引擎设计](./stock-analysis-engine-design.md)
- [提示词模板系统设计](../v1.0.1/) (待补充链接)

