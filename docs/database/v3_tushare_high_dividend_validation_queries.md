# v3.0 Tushare 高分红筛选复核查询

## 说明

- 这份文档只包含可直接在 MongoDB 中执行的原生查询语句。
- 适用环境：v3.0 MongoDB，端口 `27019`。
- 适用数据源：`tushare`。
- 适用场景：复核“高分红前 50 只候选中，为什么有 45 只被盈利稳定性验证判为无数据”。
- 这里不是标准 SQL，而是 MongoDB 原生查询/聚合语法，可直接在 `mongosh` 或 MongoDB Compass Playground 中运行。

## 连接数据库

```javascript
use tradingagents
```

如果你是从 `mongosh` 命令行连接：

```javascript
mongosh "mongodb://admin:tradingagents123@127.0.0.1:27019/tradingagents?authSource=admin"
```

## 1. 查本次筛选的前 50 只候选

筛选条件：

- `source = tushare`
- `dividend_yield >= 4`
- `net_profit_ttm > 0`
- `debt_to_assets <= 70`
- 按 `dividend_yield` 降序取前 50 只

```javascript
db.stock_screening_view.aggregate([
  {
    $match: {
      source: "tushare",
      dividend_yield: { $gte: 4 },
      net_profit_ttm: { $gt: 0 },
      debt_to_assets: { $lte: 70 }
    }
  },
  { $sort: { dividend_yield: -1 } },
  { $limit: 50 },
  {
    $project: {
      _id: 0,
      code: 1,
      name: 1,
      industry: 1,
      dividend_yield: 1,
      net_profit_ttm: 1,
      debt_to_assets: 1,
      report_period: 1,
      roe: 1
    }
  }
])
```

## 2. 查这前 50 只里，哪些在 stock_financial_data 顶层没有 tushare 年报

这里的“年报”定义为 `report_period` 以 `1231` 结尾。

这条语句会直接返回那 45 只名单。

```javascript
db.stock_screening_view.aggregate([
  {
    $match: {
      source: "tushare",
      dividend_yield: { $gte: 4 },
      net_profit_ttm: { $gt: 0 },
      debt_to_assets: { $lte: 70 }
    }
  },
  { $sort: { dividend_yield: -1 } },
  { $limit: 50 },
  {
    $lookup: {
      from: "stock_financial_data",
      let: { code: "$code" },
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $eq: ["$code", "$$code"] },
                { $eq: ["$data_source", "tushare"] },
                { $regexMatch: { input: "$report_period", regex: "1231$" } }
              ]
            }
          }
        },
        {
          $project: {
            _id: 0,
            report_period: 1,
            ann_date: 1,
            roe: 1
          }
        }
      ],
      as: "annual_docs"
    }
  },
  {
    $addFields: {
      annual_doc_count: { $size: "$annual_docs" }
    }
  },
  {
    $match: {
      annual_doc_count: 0
    }
  },
  {
    $project: {
      _id: 0,
      code: 1,
      name: 1,
      industry: 1,
      dividend_yield: 1,
      screen_report_period: "$report_period",
      annual_doc_count: 1
    }
  }
])
```

如果你只想先看数量：

```javascript
db.stock_screening_view.aggregate([
  {
    $match: {
      source: "tushare",
      dividend_yield: { $gte: 4 },
      net_profit_ttm: { $gt: 0 },
      debt_to_assets: { $lte: 70 }
    }
  },
  { $sort: { dividend_yield: -1 } },
  { $limit: 50 },
  {
    $lookup: {
      from: "stock_financial_data",
      let: { code: "$code" },
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $eq: ["$code", "$$code"] },
                { $eq: ["$data_source", "tushare"] },
                { $regexMatch: { input: "$report_period", regex: "1231$" } }
              ]
            }
          }
        }
      ],
      as: "annual_docs"
    }
  },
  {
    $addFields: {
      annual_doc_count: { $size: "$annual_docs" }
    }
  },
  {
    $match: {
      annual_doc_count: 0
    }
  },
  { $count: "missing_count" }
])
```

## 3. 查这 45 只在 raw_data 里是否内嵌了 20251231 年报

这条语句用于回答：

- 顶层 `stock_financial_data.report_period` 没有 `20251231`
- 但 `raw_data` 的各个子表里，是否其实还藏着 `end_date = 20251231`

这条语句会返回前 50 只候选里，每只股票在 raw_data 内嵌年报命中的数量。

```javascript
db.stock_screening_view.aggregate([
  {
    $match: {
      source: "tushare",
      dividend_yield: { $gte: 4 },
      net_profit_ttm: { $gt: 0 },
      debt_to_assets: { $lte: 70 }
    }
  },
  { $sort: { dividend_yield: -1 } },
  { $limit: 50 },
  {
    $lookup: {
      from: "stock_financial_data",
      let: { code: "$code" },
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $eq: ["$code", "$$code"] },
                { $eq: ["$data_source", "tushare"] }
              ]
            },
            $or: [
              { "raw_data.income_statement.end_date": "20251231" },
              { "raw_data.balance_sheet.end_date": "20251231" },
              { "raw_data.cashflow_statement.end_date": "20251231" },
              { "raw_data.financial_indicators.end_date": "20251231" },
              { "raw_data.main_business.end_date": "20251231" }
            ]
          }
        },
        {
          $project: {
            _id: 0,
            report_period: 1
          }
        }
      ],
      as: "embedded_annual_docs"
    }
  },
  {
    $addFields: {
      embedded_annual_doc_count: { $size: "$embedded_annual_docs" }
    }
  },
  {
    $project: {
      _id: 0,
      code: 1,
      name: 1,
      embedded_annual_doc_count: 1
    }
  },
  {
    $match: {
      embedded_annual_doc_count: { $gt: 0 }
    }
  }
])
```

如果你只想先看有多少只命中了 raw_data 内嵌的 `20251231`：

```javascript
db.stock_screening_view.aggregate([
  {
    $match: {
      source: "tushare",
      dividend_yield: { $gte: 4 },
      net_profit_ttm: { $gt: 0 },
      debt_to_assets: { $lte: 70 }
    }
  },
  { $sort: { dividend_yield: -1 } },
  { $limit: 50 },
  {
    $lookup: {
      from: "stock_financial_data",
      let: { code: "$code" },
      pipeline: [
        {
          $match: {
            $expr: {
              $and: [
                { $eq: ["$code", "$$code"] },
                { $eq: ["$data_source", "tushare"] }
              ]
            },
            $or: [
              { "raw_data.income_statement.end_date": "20251231" },
              { "raw_data.balance_sheet.end_date": "20251231" },
              { "raw_data.cashflow_statement.end_date": "20251231" },
              { "raw_data.financial_indicators.end_date": "20251231" },
              { "raw_data.main_business.end_date": "20251231" }
            ]
          }
        }
      ],
      as: "embedded_annual_docs"
    }
  },
  {
    $addFields: {
      embedded_annual_doc_count: { $size: "$embedded_annual_docs" }
    }
  },
  {
    $match: {
      embedded_annual_doc_count: { $gt: 0 }
    }
  },
  { $count: "embedded_positive_count" }
])
```

## 4. 单只股票直接查 stock_financial_data 顶层年报

把 `603508` 替换成任意股票代码。

```javascript
db.stock_financial_data.find(
  {
    code: "603508",
    data_source: "tushare",
    report_period: /1231$/
  },
  {
    _id: 0,
    code: 1,
    name: 1,
    report_period: 1,
    ann_date: 1,
    report_type: 1,
    roe: 1,
    roe_waa: 1,
    roe_dt: 1,
    total_equity: 1,
    net_profit: 1,
    revenue: 1
  }
).sort({ report_period: -1 })
```

如果返回空结果，就说明这只股票在 `stock_financial_data` 顶层并没有 tushare 年报行。

## 5. 单只股票直接查最新 tushare 财务文档的 raw_data 结构

```javascript
db.stock_financial_data.find(
  {
    code: "603508",
    data_source: "tushare"
  },
  {
    _id: 0,
    code: 1,
    report_period: 1,
    "raw_data.income_statement": 1,
    "raw_data.balance_sheet": 1,
    "raw_data.cashflow_statement": 1,
    "raw_data.financial_indicators": 1,
    "raw_data.main_business": 1
  }
).sort({ report_period: -1 }).limit(1)
```

## 6. 单只股票直接查 raw_data 中是否存在 20251231

下面这条语句会直接命中“这只股票的 raw_data 里有没有内嵌 20251231”。

```javascript
db.stock_financial_data.find(
  {
    code: "603508",
    data_source: "tushare",
    $or: [
      { "raw_data.income_statement.end_date": "20251231" },
      { "raw_data.balance_sheet.end_date": "20251231" },
      { "raw_data.cashflow_statement.end_date": "20251231" },
      { "raw_data.financial_indicators.end_date": "20251231" },
      { "raw_data.main_business.end_date": "20251231" }
    ]
  },
  {
    _id: 0,
    code: 1,
    report_period: 1,
    "raw_data.income_statement.end_date": 1,
    "raw_data.balance_sheet.end_date": 1,
    "raw_data.cashflow_statement.end_date": 1,
    "raw_data.financial_indicators.end_date": 1,
    "raw_data.main_business.end_date": 1
  }
).sort({ report_period: -1 })
```

## 7. 只看这次排查的核心结论

### 结论 A：45 只无数据是怎么来的

- 这 45 只是前 50 只高分红候选里，在 `stock_financial_data` 顶层没有 tushare 年报行的股票。
- 也就是：`
  code + data_source=tushare + report_period 以 1231 结尾
  ` 这个条件查不到。

### 结论 B：原始 raw_data 里是否完全没有年报

- 不一定完全没有。
- 当前已验证样本 `603508`：
  - 顶层 `report_period = 20260331`
  - `raw_data.income_statement/balance_sheet/cashflow_statement/financial_indicators` 都是 `end_date = 20260331`
  - 但 `raw_data.main_business` 里出现了 `end_date = 20251231`
- 也就是说，部分股票可能存在“顶层没有年报文档，但 raw_data 某个子表里残留了 20251231”的情况。

### 结论 C：为什么会被稳定性验证判成无数据

- 因为稳定性验证工具当前只认顶层年报文档：
  - `data_source = tushare`
  - `report_period` 以 `1231` 结尾
  - 再读取顶层 `roe`
- 它不会把 `raw_data` 各个子表里零散残留的 `20251231` 自动当成一条完整年报来参与复核。

## 8. 股息率口径说明

这里需要特别注意：当前高分红筛选里的 `dividend_yield`，不是“按年报查询”，也不是“按季报查询”，而是一个**基础快照指标**。

### 8.1 当前字段来源

- `dividend_yield` 来源于 Tushare `daily_basic` 的 `dv_ratio`
- `dividend_yield_ttm` 来源于 Tushare `daily_basic` 的 `dv_ttm`

项目中的字段映射代码如下：

- `dv_ratio -> dividend_yield`
- `dv_ttm -> dividend_yield_ttm`

也就是说：

- `dividend_yield` 更接近“静态股息率/当前快照股息率”
- `dividend_yield_ttm` 才更接近“近 12 个月滚动股息率”

### 8.2 当前筛选结果为什么容易让人误解

当前筛选链路会把不同时间语义的字段放到同一条结果里：

- `dividend_yield`：来自 `stock_basic_info` / `daily_basic` 的基础快照指标
- `close`、`pct_chg`：来自 `market_quotes` 的行情快照指标
- `roe`、`debt_to_assets`、`report_period`：来自最新财务快照（通常是最新季报）

因此，结果里虽然会显示：

- `股息率 = xx%`
- `财报期 = 20260331`

但这并不表示“这条股息率是 20260331 季报口径算出来的”。

更准确地说：

- `report_period` 只是在说明当前配套展示的财务指标对应哪一期财报
- `dividend_yield` 本身并不属于这个财报期，它是另一套基础快照口径

### 8.3 对“高分红筛选”更合理的业务解释

如果业务上问的是“高分红股票”，应先明确要查哪种口径：

1. **静态股息率口径**
  - 用 `dividend_yield`
  - 更像当前快照的股息率展示

2. **近 12 个月滚动股息率口径**
  - 用 `dividend_yield_ttm`
  - 更适合“高分红策略”默认口径

3. **年报分红口径**
  - 不能只看当前 `dividend_yield`
  - 应该显式限定 `report_period` 为 `1231` 年报，并使用单独的“年报分红/派息金额/年报口径股息率”字段来筛

### 8.4 当前设计上的问题

当前问题不只是视图字段少了一个列，而是**时间口径混用**：

- 一个结果对象里同时承载了基础快照、行情快照、财报快照三种时间语义
- 但界面只显示了一个 `report_period`
- 用户很容易自然理解成“所有指标都属于这个财报期”，这会误导

### 8.5 现在这次查询的真实口径

本次查询：

- `source = tushare`
- `dividend_yield >= 4`
- `net_profit_ttm > 0`
- `debt_to_assets <= 70`

其真实含义是：

- 先按 **Tushare 基础快照股息率** 做高分红筛选
- 再叠加 **最新财务快照** 的滚动净利润和资产负债率约束
- 最后再用 **年报 ROE** 做盈利稳定性复核

所以它不是单一“年报口径查询”，也不是单一“季报口径查询”，而是三种口径混合后的筛选链路。
