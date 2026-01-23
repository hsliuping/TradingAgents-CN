# 股票数据批量导入 API 使用指南

## 📋 概述

本文档介绍如何使用股票数据批量导入 API 接口，允许用户通过自己编写的程序将数据导入到 TradingAgents-CN Pro 系统中。

---

## 🔑 认证和权限要求

### 认证要求

所有 API 接口都需要用户认证。请在请求头中包含认证 Token：

```http
Authorization: Bearer <your_token>
```

### 权限要求

**⚠️ 重要**: 批量导入功能为 **高级学员专属功能**。

- ✅ **高级学员**: 可以使用所有批量导入接口
- ❌ **初级学员**: 无法访问批量导入接口，会返回 403 错误

如果您是初级学员，尝试调用批量导入接口会收到以下错误：

```json
{
  "detail": {
    "code": "ADVANCED_REQUIRED",
    "message": "此功能为高级学员专属",
    "plan": "free",
    "upgrade_url": "/settings/license"
  }
}
```

---

## 📊 API 接口列表

### 1. 批量保存股票基本信息

**接口**: `POST /api/stock-data/save-basic-info`

**用途**: 批量导入股票基本信息（代码、名称、行业、市值等）

**请求体**:
```json
{
  "stocks": [
    {
      "symbol": "000001",
      "name": "平安银行",
      "full_symbol": "000001.SZ",
      "market": "CN",
      "industry": "银行",
      "area": "深圳",
      "list_date": "1991-04-03",
      "total_mv": 2500.0,
      "pe": 5.2,
      "pb": 0.8
    },
    {
      "symbol": "000002",
      "name": "万科A",
      "full_symbol": "000002.SZ",
      "market": "CN",
      "industry": "房地产",
      "area": "深圳"
    }
  ],
  "data_source": "custom",
  "overwrite": false
}
```

**参数说明**:
- `stocks`: 股票信息列表（必填）
- `data_source`: 数据来源标识（默认 "custom"）
- `overwrite`: 是否覆盖已存在的数据（默认 false）

**股票基本信息字段详细说明**:

| 字段名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| `symbol` | string | ✅ | 6位股票代码 | "000001" |
| `name` | string | ✅ | 股票名称 | "平安银行" |
| `full_symbol` | string | ❌ | 完整代码（含市场后缀） | "000001.SZ" |
| `market` | string | ❌ | 市场代码：CN/US/HK | "CN" |
| `exchange` | string | ❌ | 交易所：SZ/SH/BJ | "SZ" |
| `industry` | string | ❌ | 所属行业 | "银行" |
| `sector` | string | ❌ | 所属板块 | "金融" |
| `area` | string | ❌ | 所在地区 | "深圳" |
| `list_date` | string | ❌ | 上市日期，格式 YYYY-MM-DD | "1991-04-03" |
| `list_status` | string | ❌ | 上市状态：L/D/P（上市/退市/暂停） | "L" |
| `total_mv` | float | ❌ | 总市值（亿元） | 2500.0 |
| `circ_mv` | float | ❌ | 流通市值（亿元） | 2000.0 |
| `total_share` | float | ❌ | 总股本（万股） | 195000.0 |
| `float_share` | float | ❌ | 流通股本（万股） | 156000.0 |
| `pe` | float | ❌ | 市盈率 PE | 5.2 |
| `pb` | float | ❌ | 市净率 PB | 0.8 |
| `ps` | float | ❌ | 市销率 PS | 1.5 |
| `dv_ratio` | float | ❌ | 股息率（%） | 3.5 |
| `dv_ttm` | float | ❌ | 滚动股息率（%） | 3.2 |

**响应示例**:
```json
{
  "success": true,
  "data": {
    "saved": 2,
    "updated": 0,
    "skipped": 0,
    "failed": 0,
    "total": 2,
    "errors": []
  },
  "message": "批量保存完成: 成功2, 更新0, 跳过0, 失败0"
}
```

---

### 2. 批量保存实时行情数据

**接口**: `POST /api/stock-data/save-quotes`

**用途**: 批量导入实时行情数据（价格、涨跌幅、成交量等）

**请求体**:
```json
{
  "quotes": [
    {
      "symbol": "000001",
      "close": 12.65,
      "open": 12.50,
      "high": 12.80,
      "low": 12.30,
      "pct_chg": 1.61,
      "amount": 1580000000,
      "volume": 125000000,
      "trade_date": "2024-01-15",
      "current_price": 12.65,
      "change": 0.20
    }
  ],
  "data_source": "custom",
  "overwrite": true
}
```

**参数说明**:
- `quotes`: 行情数据列表（必填）
- `data_source`: 数据来源标识（默认 "custom"）
- `overwrite`: 是否覆盖已存在的数据（默认 true，行情数据通常需要更新）

**实时行情字段详细说明**:

| 字段名 | 类型 | 必填 | 说明 | 单位 | 示例 |
|--------|------|------|------|------|------|
| `symbol` | string | ✅ | 股票代码 | - | "000001" |
| `trade_date` | string | ❌ | 交易日期，格式 YYYY-MM-DD | - | "2024-01-15" |
| `close` | float | ❌ | 收盘价 | 元 | 12.65 |
| `open` | float | ❌ | 开盘价 | 元 | 12.50 |
| `high` | float | ❌ | 最高价 | 元 | 12.80 |
| `low` | float | ❌ | 最低价 | 元 | 12.30 |
| `pre_close` | float | ❌ | 昨收价 | 元 | 12.45 |
| `current_price` | float | ❌ | 当前价（实时） | 元 | 12.65 |
| `change` | float | ❌ | 涨跌额 | 元 | 0.20 |
| `pct_chg` | float | ❌ | 涨跌幅 | % | 1.61 |
| `volume` | float | ❌ | 成交量 | 股 | 125000000 |
| `amount` | float | ❌ | 成交额 | 元 | 1580000000 |
| `turnover_rate` | float | ❌ | 换手率 | % | 6.5 |
| `volume_ratio` | float | ❌ | 量比 | 倍 | 1.2 |
| `pe` | float | ❌ | 市盈率（动态） | 倍 | 5.2 |
| `pb` | float | ❌ | 市净率 | 倍 | 0.8 |
| `total_mv` | float | ❌ | 总市值 | 亿元 | 2500.0 |
| `circ_mv` | float | ❌ | 流通市值 | 亿元 | 2000.0 |
| `amplitude` | float | ❌ | 振幅 | % | 4.0 |
| `bid_price` | float | ❌ | 买一价 | 元 | 12.64 |
| `ask_price` | float | ❌ | 卖一价 | 元 | 12.65 |
| `bid_volume` | float | ❌ | 买一量 | 股 | 100000 |
| `ask_volume` | float | ❌ | 卖一量 | 股 | 80000 |

**响应示例**:
```json
{
  "success": true,
  "data": {
    "saved": 0,
    "updated": 1,
    "failed": 0,
    "total": 1,
    "errors": []
  },
  "message": "批量保存完成: 新增0, 更新1, 失败0"
}
```

---

### 3. 批量保存财务数据

**接口**: `POST /api/financial-data/save`

**用途**: 批量导入财务数据（资产负债表、利润表、现金流量表等）

**请求体**:
```json
{
  "symbol": "000001",
  "financial_data": [
    {
      "report_period": "20231231",
      "report_type": "annual",
      "ann_date": "2024-03-20",
      "total_assets": 5000000000,
      "total_liabilities": 4000000000,
      "total_equity": 1000000000,
      "revenue": 100000000,
      "net_profit": 20000000,
      "operating_profit": 25000000,
      "roe": 15.5,
      "roa": 3.2,
      "eps": 1.25,
      "bps": 8.50
    }
  ],
  "data_source": "custom",
  "overwrite": false
}
```

**参数说明**:
- `symbol`: 股票代码（必填）
- `financial_data`: 财务数据列表（必填）
  - `report_period`: 报告期，格式 YYYYMMDD（必填）
  - `report_type`: 报告类型（可选）
    - `annual` - 年报
    - `semi_annual` - 半年报
    - `quarterly` - 季报
  - `ann_date`: 公告日期，格式 YYYY-MM-DD（可选）
  - 其他字段见下方详细字段说明表
- `data_source`: 数据来源标识（默认 "custom"）
- `overwrite`: 是否覆盖已存在的数据（默认 false）

**财务数据字段详细说明**:

#### 基本信息字段

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| `report_period` | string | 报告期（必填），格式 YYYYMMDD | "20231231" |
| `report_type` | string | 报告类型：annual/semi_annual/quarterly | "annual" |
| `ann_date` | string | 公告日期，格式 YYYY-MM-DD | "2024-03-20" |
| `end_date` | string | 报告截止日期 | "2023-12-31" |
| `comp_type` | string | 公司类型 | "1" |
| `report_type_code` | string | 报告类型代码 | "1" |

#### 资产负债表字段

| 字段名 | 类型 | 说明 | 单位 | 示例 |
|--------|------|------|------|------|
| `total_assets` | float | 总资产 | 元 | 5000000000 |
| `total_liabilities` | float | 总负债 | 元 | 4000000000 |
| `total_equity` | float | 股东权益合计 | 元 | 1000000000 |
| `total_current_assets` | float | 流动资产合计 | 元 | 3000000000 |
| `total_non_current_assets` | float | 非流动资产合计 | 元 | 2000000000 |
| `total_current_liabilities` | float | 流动负债合计 | 元 | 2500000000 |
| `total_non_current_liabilities` | float | 非流动负债合计 | 元 | 1500000000 |
| `monetary_funds` | float | 货币资金 | 元 | 500000000 |
| `accounts_receivable` | float | 应收账款 | 元 | 300000000 |
| `inventories` | float | 存货 | 元 | 200000000 |
| `fixed_assets` | float | 固定资产 | 元 | 800000000 |
| `intangible_assets` | float | 无形资产 | 元 | 100000000 |
| `goodwill` | float | 商誉 | 元 | 50000000 |
| `accounts_payable` | float | 应付账款 | 元 | 400000000 |
| `short_term_borrowing` | float | 短期借款 | 元 | 600000000 |
| `long_term_borrowing` | float | 长期借款 | 元 | 800000000 |

#### 利润表字段

| 字段名 | 类型 | 说明 | 单位 | 示例 |
|--------|------|------|------|------|
| `revenue` | float | 营业收入 | 元 | 100000000 |
| `operating_revenue` | float | 营业总收入 | 元 | 100000000 |
| `total_revenue` | float | 营业总收入（同上） | 元 | 100000000 |
| `operating_cost` | float | 营业成本 | 元 | 60000000 |
| `operating_expense` | float | 营业费用 | 元 | 15000000 |
| `operating_profit` | float | 营业利润 | 元 | 25000000 |
| `total_profit` | float | 利润总额 | 元 | 24000000 |
| `net_profit` | float | 净利润 | 元 | 20000000 |
| `net_profit_after_nrgal` | float | 扣非净利润 | 元 | 18000000 |
| `gross_profit` | float | 毛利润 | 元 | 40000000 |
| `ebit` | float | 息税前利润 | 元 | 26000000 |
| `ebitda` | float | 息税折旧摊销前利润 | 元 | 30000000 |

#### 现金流量表字段

| 字段名 | 类型 | 说明 | 单位 | 示例 |
|--------|------|------|------|------|
| `operating_cash_flow` | float | 经营活动现金流量净额 | 元 | 30000000 |
| `investing_cash_flow` | float | 投资活动现金流量净额 | 元 | -10000000 |
| `financing_cash_flow` | float | 筹资活动现金流量净额 | 元 | -5000000 |
| `net_cash_flow` | float | 现金及现金等价物净增加额 | 元 | 15000000 |
| `free_cash_flow` | float | 自由现金流 | 元 | 20000000 |

#### 财务比率字段

| 字段名 | 类型 | 说明 | 单位 | 示例 |
|--------|------|------|------|------|
| `roe` | float | 净资产收益率 ROE | % | 15.5 |
| `roa` | float | 总资产收益率 ROA | % | 3.2 |
| `gross_profit_margin` | float | 毛利率 | % | 40.0 |
| `net_profit_margin` | float | 净利率 | % | 20.0 |
| `asset_liability_ratio` | float | 资产负债率 | % | 80.0 |
| `current_ratio` | float | 流动比率 | 倍 | 1.2 |
| `quick_ratio` | float | 速动比率 | 倍 | 1.0 |
| `debt_to_equity` | float | 产权比率 | % | 400.0 |

#### 每股指标字段

| 字段名 | 类型 | 说明 | 单位 | 示例 |
|--------|------|------|------|------|
| `eps` | float | 每股收益 EPS | 元/股 | 1.25 |
| `bps` | float | 每股净资产 BPS | 元/股 | 8.50 |
| `ocfps` | float | 每股经营现金流 | 元/股 | 1.80 |
| `capital_reserve_per_share` | float | 每股资本公积 | 元/股 | 3.50 |
| `undistributed_profit_per_share` | float | 每股未分配利润 | 元/股 | 2.00 |

#### 增长率字段

| 字段名 | 类型 | 说明 | 单位 | 示例 |
|--------|------|------|------|------|
| `revenue_yoy` | float | 营业收入同比增长率 | % | 12.5 |
| `net_profit_yoy` | float | 净利润同比增长率 | % | 8.3 |
| `total_assets_yoy` | float | 总资产同比增长率 | % | 5.2 |
| `equity_yoy` | float | 净资产同比增长率 | % | 6.8 |

#### 其他字段

| 字段名 | 类型 | 说明 | 单位 | 示例 |
|--------|------|------|------|------|
| `total_shares` | float | 总股本 | 股 | 1600000000 |
| `circulating_shares` | float | 流通股本 | 股 | 1200000000 |
| `market_cap` | float | 总市值 | 元 | 20000000000 |
| `circulating_market_cap` | float | 流通市值 | 元 | 15000000000 |

**响应示例**:
```json
{
  "success": true,
  "data": {
    "saved": 1,
    "updated": 0,
    "skipped": 0,
    "failed": 0,
    "total": 1,
    "errors": []
  },
  "message": "批量保存完成: 成功1, 更新0, 跳过0, 失败0"
}
```

**注意事项**:
1. 所有金额字段单位为**元**（不是万元或亿元）
2. 所有比率字段单位为**百分比**（如 15.5 表示 15.5%）
3. 只有 `report_period` 是必填字段，其他字段都是可选的
4. 建议至少填写核心字段：`revenue`（营业收入）、`net_profit`（净利润）、`total_assets`（总资产）、`total_equity`（股东权益）
5. 日期格式：`report_period` 使用 YYYYMMDD，`ann_date` 使用 YYYY-MM-DD

---

### 4. 批量保存新闻数据

**接口**: `POST /api/news-data/save`

**用途**: 批量导入新闻数据（标题、内容、发布时间、情绪分析等）

**请求体**:
```json
{
  "symbol": "000001",
  "news_list": [
    {
      "title": "平安银行发布2023年年报",
      "content": "平安银行股份有限公司今日发布2023年年度报告...",
      "summary": "平安银行2023年净利润同比增长2.6%",
      "url": "https://example.com/news/123",
      "source": "证券时报",
      "author": "张三",
      "publish_time": "2024-03-20T09:00:00Z",
      "category": "company_announcement",
      "sentiment": "positive",
      "sentiment_score": 0.75,
      "keywords": ["年报", "净利润", "增长"],
      "importance": "high"
    },
    {
      "title": "银行业监管政策调整",
      "url": "https://example.com/news/124",
      "source": "财经网",
      "publish_time": "2024-03-21T10:00:00Z",
      "symbols": ["000001", "600036"],
      "category": "industry_news"
    }
  ],
  "data_source": "custom",
  "overwrite": false
}
```

**参数说明**:
- `symbol`: 主要相关股票代码（可选）
- `news_list`: 新闻数据列表（必填）
- `data_source`: 数据来源标识（默认 "custom"）
- `overwrite`: 是否覆盖已存在的数据（默认 false）

**新闻数据字段详细说明**:

| 字段名 | 类型 | 必填 | 说明 | 示例 |
|--------|------|------|------|------|
| `title` | string | ✅ | 新闻标题 | "平安银行发布2023年年报" |
| `url` | string | ✅ | 新闻链接（用于去重） | "https://example.com/news/123" |
| `publish_time` | string | ✅ | 发布时间，ISO 8601 格式 | "2024-03-20T09:00:00Z" |
| `content` | string | ❌ | 新闻正文内容 | "平安银行股份有限公司..." |
| `summary` | string | ❌ | 新闻摘要 | "平安银行2023年净利润同比增长2.6%" |
| `source` | string | ❌ | 新闻来源 | "证券时报" |
| `author` | string | ❌ | 作者 | "张三" |
| `symbols` | array | ❌ | 相关股票代码列表 | ["000001", "600036"] |
| `category` | string | ❌ | 新闻分类 | "company_announcement" |
| `sentiment` | string | ❌ | 情绪：positive/neutral/negative | "positive" |
| `sentiment_score` | float | ❌ | 情绪得分（-1到1） | 0.75 |
| `keywords` | array | ❌ | 关键词列表 | ["年报", "净利润", "增长"] |
| `importance` | string | ❌ | 重要性：high/medium/low | "high" |
| `language` | string | ❌ | 语言代码 | "zh-CN" |
| `image_url` | string | ❌ | 配图链接 | "https://example.com/img.jpg" |
| `video_url` | string | ❌ | 视频链接 | "https://example.com/video.mp4" |

**新闻分类说明**:
- `company_announcement` - 公司公告
- `industry_news` - 行业新闻
- `market_news` - 市场新闻
- `product_news` - 产品新闻
- `financial_report` - 财报新闻
- `policy_news` - 政策新闻
- `research_report` - 研究报告
- `other` - 其他

**响应示例**:
```json
{
  "success": true,
  "data": {
    "saved": 2,
    "updated": 0,
    "skipped": 0,
    "failed": 0,
    "total": 2,
    "errors": []
  },
  "message": "批量保存完成: 成功2, 更新0, 跳过0, 失败0"
}
```

---

## 💻 Python 代码示例

### 示例 1: 批量导入股票基本信息

```python
import requests
import json

# API 配置
BASE_URL = "http://localhost:9706"
TOKEN = "your_auth_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 准备数据
stocks_data = {
    "stocks": [
        {
            "symbol": "000001",
            "name": "平安银行",
            "full_symbol": "000001.SZ",
            "market": "CN",
            "industry": "银行",
            "area": "深圳"
        },
        {
            "symbol": "000002",
            "name": "万科A",
            "full_symbol": "000002.SZ",
            "market": "CN",
            "industry": "房地产",
            "area": "深圳"
        }
    ],
    "data_source": "my_crawler",
    "overwrite": False
}

# 发送请求
response = requests.post(
    f"{BASE_URL}/api/stock-data/save-basic-info",
    headers=headers,
    json=stocks_data
)

# 处理响应
if response.status_code == 200:
    result = response.json()
    print(f"✅ 成功: {result['data']['saved']}")
    print(f"⚠️ 跳过: {result['data']['skipped']}")
    print(f"❌ 失败: {result['data']['failed']}")
else:
    print(f"❌ 请求失败: {response.status_code}")
    print(response.text)
```

### 示例 2: 批量导入实时行情

```python
import requests
from datetime import datetime

BASE_URL = "http://localhost:9706"
TOKEN = "your_auth_token_here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

# 准备行情数据
quotes_data = {
    "quotes": [
        {
            "symbol": "000001",
            "close": 12.65,
            "open": 12.50,
            "high": 12.80,
            "low": 12.30,
            "pct_chg": 1.61,
            "amount": 1580000000,
            "volume": 125000000,
            "trade_date": datetime.now().strftime("%Y-%m-%d")
        }
    ],
    "data_source": "realtime_api",
    "overwrite": True  # 行情数据通常需要覆盖
}

response = requests.post(
    f"{BASE_URL}/api/stock-data/save-quotes",
    headers=headers,
    json=quotes_data
)

if response.status_code == 200:
    result = response.json()
    print(f"✅ 导入成功: {result['message']}")
else:
    print(f"❌ 导入失败: {response.text}")
```

---

## 🔍 常见问题

### Q1: 如何获取认证 Token？

A: 使用登录接口获取 Token：

```python
response = requests.post(
    f"{BASE_URL}/api/auth/login",
    json={"username": "your_username", "password": "your_password"}
)
token = response.json()["data"]["token"]
```

### Q2: 我是初级学员，可以使用批量导入功能吗？

A: **不可以**。批量导入功能为高级学员专属功能。

如果您尝试使用批量导入接口，会收到 403 错误：

```json
{
  "detail": {
    "code": "ADVANCED_REQUIRED",
    "message": "此功能为高级学员专属",
    "plan": "free",
    "upgrade_url": "/settings/license"
  }
}
```

**如何成为高级学员**:
1. 登录系统
2. 进入 "设置" → "许可证管理"
3. 输入您的高级学员授权码
4. 激活后即可使用批量导入功能

**其他方式**:
- 通过完成学习任务获取积分
- 参与社区贡献获取积分
- 积分达到一定数量后可兑换高级学员权限

### Q3: 数据去重规则是什么？

A:
- **股票基本信息**: 按 `(symbol, source)` 去重
- **实时行情**: 按 `symbol` 去重（自动覆盖）
- **财务数据**: 按 `(symbol, report_period, data_source)` 去重
- **新闻数据**: 按 `url` 去重

### Q4: 如何处理大批量数据？

A: 建议分批导入，每批不超过 100-200 条记录，避免请求超时。

### Q5: 导入失败如何排查？

A: 检查响应中的 `errors` 字段，包含详细的错误信息和失败记录的索引。

---

## 📝 注意事项

1. **认证**: 所有接口都需要有效的认证 Token
2. **数据格式**: 确保必填字段完整，日期格式正确
3. **批量大小**: 建议每次不超过 200 条记录
4. **去重策略**: 了解各类数据的去重规则，避免重复导入
5. **错误处理**: 检查响应中的 `errors` 字段，处理失败记录
6. **数据源标识**: 使用有意义的 `data_source` 值，便于后续追溯

---

**最后更新**: 2026-01-23
**版本**: v1.0.0
