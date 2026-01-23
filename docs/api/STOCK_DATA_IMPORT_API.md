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
  - `symbol`: 6位股票代码（必填）
  - `name`: 股票名称（必填）
  - 其他字段可选
- `data_source`: 数据来源标识（默认 "custom"）
- `overwrite`: 是否覆盖已存在的数据（默认 false）

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
  - `symbol`: 股票代码（必填）
  - 其他字段可选
- `data_source`: 数据来源标识（默认 "custom"）
- `overwrite`: 是否覆盖已存在的数据（默认 true，行情数据通常需要更新）

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
      "revenue": 100000000,
      "net_profit": 20000000,
      "roe": 15.5,
      "eps": 1.25
    },
    {
      "report_period": "20230930",
      "report_type": "quarterly",
      "revenue": 75000000,
      "net_profit": 15000000
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
  - 其他字段可选
- `data_source`: 数据来源标识（默认 "custom"）
- `overwrite`: 是否覆盖已存在的数据（默认 false）

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
  - `title`: 新闻标题（必填）
  - `url`: 新闻链接（必填，用于去重）
  - `publish_time`: 发布时间（必填）
  - `symbols`: 相关股票列表（可选）
  - 其他字段可选
- `data_source`: 数据来源标识（默认 "custom"）
- `overwrite`: 是否覆盖已存在的数据（默认 false）

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
