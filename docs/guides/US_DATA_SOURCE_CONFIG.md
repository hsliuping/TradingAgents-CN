# 美股数据源配置指南

本文档说明如何配置美股数据源（yfinance、Alpha Vantage、Finnhub）。

## 📊 支持的数据源

### 1. **yfinance** (推荐，免费)
- **提供商**: Yahoo Finance
- **数据类型**: 股票价格、技术指标、基本面信息
- **费用**: 完全免费
- **API Key**: 不需要
- **限制**: 无严格限制
- **优势**: 
  - 完全免费，无需注册
  - 数据质量高，覆盖全球市场
  - 支持实时和历史数据
  - 支持13种技术指标计算

### 2. **Alpha Vantage** (推荐，基本面和新闻)
- **提供商**: Alpha Vantage
- **数据类型**: 基本面数据、新闻、内部人交易
- **费用**: 免费版 25 请求/天，付费版无限制
- **API Key**: 需要（免费申请）
- **限制**: 免费版有速率限制
- **优势**:
  - 新闻数据准确度高，带情感分析
  - 基本面数据详细（财务报表、估值指标）
  - 内部人交易数据
  - 官方支持，数据可靠

**获取 API Key**: https://www.alphavantage.co/support/#api-key

### 3. **Finnhub** (备用)
- **提供商**: Finnhub
- **数据类型**: 股票价格、基本面、新闻
- **费用**: 免费版 60 请求/分钟，付费版无限制
- **API Key**: 需要（免费申请）
- **限制**: 免费版有速率限制
- **优势**:
  - 数据覆盖广
  - 实时数据支持
  - 备用数据源

**获取 API Key**: https://finnhub.io/register

---

## 🔧 配置方式

### 方式一：Web 后台配置（推荐）

#### 1. 访问配置页面
打开浏览器访问：`http://localhost:3000/settings/data-sources`

#### 2. 添加数据源配置

**Alpha Vantage 配置**:
```json
{
  "type": "alpha_vantage",
  "api_key": "YOUR_ALPHA_VANTAGE_API_KEY",
  "enabled": true,
  "description": "Alpha Vantage - 基本面和新闻数据"
}
```

**Finnhub 配置**:
```json
{
  "type": "finnhub",
  "api_key": "YOUR_FINNHUB_API_KEY",
  "enabled": true,
  "description": "Finnhub - 备用数据源"
}
```

**yfinance 配置**:
```json
{
  "type": "yfinance",
  "enabled": true,
  "description": "yfinance - 免费股票数据"
}
```

#### 3. 设置数据源优先级

在 `datasource_groupings` 集合中配置优先级：

```json
[
  {
    "data_source_name": "yfinance",
    "market_category_id": "us_stocks",
    "priority": 100,
    "enabled": true,
    "description": "yfinance - 股票价格和技术指标"
  },
  {
    "data_source_name": "alpha_vantage",
    "market_category_id": "us_stocks",
    "priority": 90,
    "enabled": true,
    "description": "Alpha Vantage - 基本面和新闻"
  },
  {
    "data_source_name": "finnhub",
    "market_category_id": "us_stocks",
    "priority": 80,
    "enabled": true,
    "description": "Finnhub - 备用数据源"
  }
]
```

**优先级说明**:
- `priority` 数字越大，优先级越高
- 系统会按优先级从高到低尝试数据源
- 如果高优先级数据源失败，自动降级到下一个数据源

---

### 方式二：环境变量配置

在 `.env` 文件中添加：

```bash
# Alpha Vantage API Key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_api_key_here

# Finnhub API Key
FINNHUB_API_KEY=your_finnhub_api_key_here

# 默认美股数据源（可选）
DEFAULT_US_DATA_SOURCE=yfinance
```

---

### 方式三：直接操作数据库

#### 1. 连接到 MongoDB

```bash
mongosh mongodb://localhost:27017/tradingagents
```

#### 2. 插入配置到 `system_configs` 集合

```javascript
db.system_configs.updateOne(
  { is_active: true },
  {
    $set: {
      data_source_configs: [
        {
          type: "alpha_vantage",
          api_key: "YOUR_ALPHA_VANTAGE_API_KEY",
          enabled: true
        },
        {
          type: "finnhub",
          api_key: "YOUR_FINNHUB_API_KEY",
          enabled: true
        },
        {
          type: "yfinance",
          enabled: true
        }
      ]
    }
  }
)
```

#### 3. 配置数据源优先级

```javascript
db.datasource_groupings.insertMany([
  {
    data_source_name: "yfinance",
    market_category_id: "us_stocks",
    priority: 100,
    enabled: true,
    created_at: new Date(),
    updated_at: new Date()
  },
  {
    data_source_name: "alpha_vantage",
    market_category_id: "us_stocks",
    priority: 90,
    enabled: true,
    created_at: new Date(),
    updated_at: new Date()
  },
  {
    data_source_name: "finnhub",
    market_category_id: "us_stocks",
    priority: 80,
    enabled: true,
    created_at: new Date(),
    updated_at: new Date()
  }
])
```

---

## 📋 配置优先级

系统读取配置的优先级顺序：

1. **数据库配置** (`system_configs` 集合) - 最高优先级
2. **环境变量** (`.env` 文件)
3. **配置文件** (`~/.tradingagents/config.json`)

**推荐使用数据库配置**，因为：
- ✅ Web 后台修改后立即生效
- ✅ 无需重启服务
- ✅ 统一的配置管理
- ✅ 支持版本控制和回滚

---

## 🔄 数据源降级机制

系统会自动按优先级尝试数据源，如果失败则降级到下一个：

```
yfinance (优先级 100)
    ↓ 失败
Alpha Vantage (优先级 90)
    ↓ 失败
Finnhub (优先级 80)
    ↓ 失败
OpenAI (特殊处理，如果配置了)
    ↓ 失败
返回错误
```

**日志示例**:
```
📊 [美股基本面] 数据源优先级: ['yfinance', 'alpha_vantage', 'finnhub']
📊 [yfinance] 获取 AAPL 的基本面数据...
✅ [yfinance] 基本面数据获取成功: AAPL
```

---

## 🧪 测试配置

### 测试 Alpha Vantage 配置

```python
from tradingagents.dataflows.providers.us.alpha_vantage_common import get_api_key

try:
    api_key = get_api_key()
    print(f"✅ Alpha Vantage API Key 配置成功 (长度: {len(api_key)})")
except ValueError as e:
    print(f"❌ Alpha Vantage API Key 未配置: {e}")
```

### 测试数据源管理器

```python
from tradingagents.dataflows.data_source_manager import get_us_data_source_manager

us_manager = get_us_data_source_manager()
print(f"📊 可用数据源: {[s.value for s in us_manager.available_sources]}")
print(f"📊 默认数据源: {us_manager.default_source.value}")

# 获取优先级顺序
priority_order = us_manager._get_data_source_priority_order("AAPL")
print(f"📊 数据源优先级: {[s.value for s in priority_order]}")
```

### 测试基本面数据获取

```python
from tradingagents.dataflows.interface import get_fundamentals_openai

result = get_fundamentals_openai("AAPL", "2024-01-15")
print(result)
```

---

## ❓ 常见问题

### Q1: 为什么推荐使用 yfinance？
**A**: yfinance 完全免费，无需 API Key，数据质量高，覆盖全球市场，非常适合个人用户和小型项目。

### Q2: Alpha Vantage 免费版够用吗？
**A**: 免费版每天 25 次请求，对于个人用户基本够用。如果需要更高频率，可以升级到付费版。

### Q3: 如何切换数据源？
**A**: 
1. Web 后台修改优先级
2. 或者在数据库中修改 `datasource_groupings` 集合的 `priority` 字段
3. 修改后立即生效，无需重启

### Q4: 数据源失败会怎样？
**A**: 系统会自动降级到下一个数据源，并在日志中记录失败原因。

### Q5: 可以禁用某个数据源吗？
**A**: 可以，在 `datasource_groupings` 集合中设置 `enabled: false`。

---

## 📚 相关文档

- [数据源架构设计](../development/architecture/data_source_architecture.md)
- [美股数据源升级计划](../development/US_DATA_SOURCE_UPGRADE_PLAN.md)
- [API 参考文档](../reference/api/data_sources.md)

---

## 🔗 外部链接

- [Alpha Vantage 官网](https://www.alphavantage.co/)
- [Alpha Vantage API 文档](https://www.alphavantage.co/documentation/)
- [Finnhub 官网](https://finnhub.io/)
- [yfinance GitHub](https://github.com/ranaroussi/yfinance)

