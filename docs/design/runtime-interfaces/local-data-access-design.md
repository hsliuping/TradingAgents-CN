# 本地数据库访问接口设计

## 1. 目标

`core.skill_runtime.data_access` 的定位是：

为生成 Skill 暴露一组面向股票分析场景的同步高频 helper，让代码生成优先走“已有业务语义”的接口，而不是自己拼装 MongoDB 查询。

当前优先范围只覆盖 A 股本地数据场景，多市场 helper 暂不纳入本轮运行时接口收口。

这层接口优先服务以下场景：

1. 个股基础信息查询
2. 历史行情读取
3. 实时价格读取
4. 新闻读取
5. 财务数据读取
6. 估值上下文拼装
7. 行业同行样本与行业估值统计

## 2. 当前公开 helper

当前 `data_access` 已公开的核心 helper 包括：

1. `get_stock_basic_info(symbol, source=None)`
2. `get_stock_daily_quotes(symbol, start_date, end_date, period="daily", source=None, limit=1000)`
3. `get_stock_news(symbol, start_date=None, end_date=None, limit=20)`
4. `get_stock_news_by_date_range(symbol, start_date, end_date, limit=20)`
5. `get_market_quotes(symbol)`
6. `get_latest_stock_price(symbol)`
7. `get_stock_financial_data(symbol, start_date=None, end_date=None, limit=20, source=None)`
8. `get_stock_financial_periods(symbol, source=None, limit=20)`
9. `get_industry_peer_basic_info(industry, exclude_symbol=None, limit=200, source=None)`
10. `summarize_industry_valuation(industry, metric="pb", exclude_symbol=None, limit=200, source=None, min_value=0.0, max_value=1000.0)`
11. `get_stock_valuation_context(symbol, financial_limit=8)`

这些 helper 已经足够支撑一批典型 Skill：

1. 估值分析 Skill
2. 基本面摘要 Skill
3. 行业对比 Skill
4. 新闻摘要 Skill
5. 财务同比 / 多期质量因子 Skill

## 3. 为什么优先暴露 helper，而不是直接暴露集合

直接开放集合查询看似更灵活，但会带来三个问题：

1. 生成代码容易重复实现同一套业务语义。
2. 口径不稳定，不同 Skill 会对同一字段做出不同解释。
3. 一旦底层表结构变化，需要修改大量生成 Skill，而不是只修一个 helper。

因此 `data_access` 的设计原则是：

1. 高频场景优先 helper 化。
2. helper 的返回结构尽量带业务语义，而不是裸文档。
3. 复杂口径统一在 helper 内部处理，例如财务 period 展开、最新价格回退、行业估值样本过滤。

## 4. 与本地 MongoDB 的关系

`data_access` 底层通过同步 MongoDB 客户端读取项目数据库，但这一细节对生成 Skill 不透明。

对生成代码来说，正确用法是：

```python
from core.skill_runtime.data_access import get_stock_valuation_context

ctx = get_stock_valuation_context("600519")
current_price = ctx["current_price"]
financial_data = ctx["financial_data"]
```

而不是：

```python
from pymongo import MongoClient

client = MongoClient(...)
db = client["tradingagents"]
```

后者属于明确禁止的实现方式。

## 5. 当前覆盖范围与已知边界

当前 `data_access` 已经覆盖：

1. A 股个股基础信息
2. 实时行情
3. 历史日线
4. 新闻
5. 财务快照
6. 财务按期展开记录
7. 估值场景统一上下文

其中，`get_stock_financial_periods(...)` 是当前 A 股基本面分析的 canonical period 入口，优先级高于直接读取混合结构的 `get_stock_financial_data(...)`。

当前仍未形成完整公开能力的方向包括：

1. ETF 专用本地数据 helper
2. 技术指标便捷 helper
3. 组合/持仓/账户维度 helper
4. 板块、资金流、公告等更广义的交易辅助数据 helper

这意味着它当前更适合“分析型股票机器人”，而不是完整交易执行机器人。

## 6. 新增 helper 的准入规则

当某个股票场景重复出现，且多个 Skill 都需要相同口径时，应优先新增 `data_access` helper，而不是让 Skill 各自实现。

推荐准入标准：

1. 该逻辑至少被两个以上 Skill 或工坊场景重复需要。
2. 裸集合查询不足以稳定表达业务语义。
3. 底层字段存在回退链、清洗口径或 source 优先级差异。
4. 该能力是“炒股机器人核心能力”的一部分，例如价格、财务、估值、新闻、行业对比。

## 7. 文档同步要求

每次新增 `data_access` helper 时，至少要同步更新：

1. 本文件
2. `LOCAL_DATA_API_DOC`
3. CodeGenerator 中相关使用提示
4. 如涉及新集合或新口径，更新本专题下的治理文档
