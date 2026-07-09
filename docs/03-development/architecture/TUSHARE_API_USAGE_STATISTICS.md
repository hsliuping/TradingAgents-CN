# Tushare API 接口使用统计

> 统计时间：2026-01-24  
> 统计范围：项目中所有 Tushare API 接口调用

## 📊 接口使用汇总表

| 序号 | 接口名称 | Tushare API | 用途 | 调用位置 | 使用频率 |
|------|---------|-------------|------|----------|----------|
| 1 | 股票基础信息 | `stock_basic` | 获取股票列表、基础信息（代码、名称、行业、上市日期等） | `tushare.py`, `utils.py`, `tushare_adapter.py` | ⭐⭐⭐⭐⭐ |
| 2 | 日线行情 | `daily` | 获取股票日线K线数据（开高低收、成交量等） | `tushare.py`, `tushare_adapter.py` | ⭐⭐⭐⭐⭐ |
| 3 | 每日基础指标 | `daily_basic` | 获取每日估值指标（PE、PB、PS、市值、换手率等） | `tushare.py`, `tushare_adapter.py`, `utils.py` | ⭐⭐⭐⭐⭐ |
| 4 | K线数据（复权） | `pro_bar` | 获取前复权/后复权K线数据（通过 `tushare.pro.data_pro.pro_bar`） | `tushare.py`, `tushare_adapter.py` | ⭐⭐⭐⭐ |
| 5 | 实时行情 | `rt_k` | 批量获取全市场实时行情（支持通配符） | `tushare.py`, `tushare_adapter.py`, `quotes_ingestion_service.py` | ⭐⭐⭐⭐ |
| 6 | 利润表 | `income` | 获取财务报表-利润表数据 | `tushare.py` | ⭐⭐⭐ |
| 7 | 资产负债表 | `balancesheet` | 获取财务报表-资产负债表数据 | `tushare.py` | ⭐⭐⭐ |
| 8 | 现金流量表 | `cashflow` | 获取财务报表-现金流量表数据 | `tushare.py` | ⭐⭐⭐ |
| 9 | 财务指标 | `fina_indicator` | 获取财务指标（ROE、ROA、毛利率、净利率等） | `tushare.py`, `utils.py` | ⭐⭐⭐ |
| 10 | 主营业务构成 | `fina_mainbz` | 获取主营业务收入构成数据 | `tushare.py` | ⭐⭐ |
| 11 | 新闻数据 | `news` | 获取股票相关新闻（需要付费权限） | `tushare.py`, `tushare_adapter.py` | ⭐⭐ |
| 12 | 公告数据 | `anns` | 获取股票公告（在 `tushare_adapter.py` 中） | `tushare_adapter.py` | ⭐ |
| 13 | 同花顺板块列表 | `ths_index` | 获取同花顺板块列表（行业/概念/地域板块） | `tushare.py` | ⭐⭐ |
| 14 | 同花顺板块日线 | `ths_daily` | 获取同花顺板块日线行情 | `tushare.py` | ⭐⭐ |
| 15 | 同花顺板块成分股 | `ths_member` | 获取板块成分股或股票所属板块 | `tushare.py` | ⭐⭐ |
| 16 | 同花顺板块资金流向 | `moneyflow_ths` | 获取板块资金流向数据 | `tushare.py` | ⭐ |
| 17 | 指数基本信息 | `index_basic` | 获取指数基本信息（代码、名称、基准日期等） | `tushare.py` | ⭐⭐ |
| 18 | 指数日线行情 | `index_daily` | 获取指数日线行情数据 | `tushare.py` | ⭐⭐ |
| 19 | 指数每日指标 | `index_dailybasic` | 获取指数每日估值指标 | `tushare.py` | ⭐⭐ |
| 20 | 每日市场交易统计 | `daily_info` | 获取每日市场交易统计（涨跌家数等） | `tushare.py` | ⭐ |
| 21 | 指数成分和权重 | `index_weight` | 获取指数成分股及权重 | `tushare.py` | ⭐ |
| 22 | 沪深港通资金流向 | `moneyflow_hsgt` | 获取北向/南向资金流向数据 | `tushare.py` | ⭐⭐ |
| 23 | 融资融券交易汇总 | `margin` | 获取两融余额数据 | `tushare.py` | ⭐ |
| 24 | 涨跌停统计 | `limit_list_d` | 获取每日涨跌停股票统计 | `tushare.py` | ⭐ |
| 25 | 每日涨跌停价格 | `stk_limit` | 获取每日涨跌停价格 | `tushare.py` | ⭐ |

## 📈 表格一：接口分类汇总表

| 接口分类 | 接口数量 | 接口列表 | 使用频率 | 权限要求 |
|---------|---------|---------|----------|----------|
| **基础数据接口** | 5个 | `stock_basic`, `daily`, `daily_basic`, `pro_bar`, `rt_k` | ⭐⭐⭐⭐⭐ | 免费版可用 |
| **财务数据接口** | 5个 | `income`, `balancesheet`, `cashflow`, `fina_indicator`, `fina_mainbz` | ⭐⭐⭐ | 基础版及以上 |
| **新闻公告接口** | 2个 | `news`, `anns` | ⭐⭐ | 高级版及以上 |
| **板块行业接口** | 4个 | `ths_index`, `ths_daily`, `ths_member`, `moneyflow_ths` | ⭐⭐ | 标准版及以上 |
| **指数数据接口** | 4个 | `index_basic`, `index_daily`, `index_dailybasic`, `index_weight` | ⭐⭐ | 基础版及以上 |
| **市场分析接口** | 5个 | `daily_info`, `moneyflow_hsgt`, `margin`, `limit_list_d`, `stk_limit` | ⭐ | 标准版及以上 |
| **总计** | **25个** | - | - | - |

## 📍 表格二：调用位置统计表

| 文件路径 | 接口数量 | 使用的接口列表 | 主要用途 |
|---------|---------|---------------|----------|
| `tradingagents/dataflows/providers/china/tushare.py` | 24个 | `stock_basic`, `daily`, `daily_basic`, `pro_bar`, `rt_k`, `income`, `balancesheet`, `cashflow`, `fina_indicator`, `fina_mainbz`, `news`, `ths_index`, `ths_daily`, `ths_member`, `moneyflow_ths`, `index_basic`, `index_daily`, `index_dailybasic`, `daily_info`, `index_weight`, `moneyflow_hsgt`, `margin`, `limit_list_d`, `stk_limit` | 核心实现，包含所有接口封装 |
| `app/services/data_sources/tushare_adapter.py` | 5个 | `stock_basic`, `daily_basic`, `rt_k`, `pro_bar`, `anns` | 适配器层，统一数据源接口 |
| `app/services/basics_sync/utils.py` | 3个 | `stock_basic`, `daily_basic`, `fina_indicator` | 基础数据同步工具 |
| `app/worker/tushare_sync_service.py` | 间接调用 | 通过 `TushareProvider` 调用所有接口 | 数据同步服务 |
| `app/services/quotes_ingestion_service.py` | 1个 | `rt_k` | 行情数据接入服务 |
| **总计** | **25个** | - | - |

## 📈 接口分类详情

### 基础数据接口（5个）
- `stock_basic` - 股票基础信息
- `daily` - 日线行情
- `daily_basic` - 每日基础指标
- `pro_bar` - K线数据（复权）
- `rt_k` - 实时行情

### 财务数据接口（5个）
- `income` - 利润表
- `balancesheet` - 资产负债表
- `cashflow` - 现金流量表
- `fina_indicator` - 财务指标
- `fina_mainbz` - 主营业务构成

### 新闻公告接口（2个）
- `news` - 新闻数据
- `anns` - 公告数据

### 板块行业接口（4个）
- `ths_index` - 同花顺板块列表
- `ths_daily` - 同花顺板块日线
- `ths_member` - 同花顺板块成分股
- `moneyflow_ths` - 同花顺板块资金流向

### 指数数据接口（4个）
- `index_basic` - 指数基本信息
- `index_daily` - 指数日线行情
- `index_dailybasic` - 指数每日指标
- `index_weight` - 指数成分和权重

### 市场分析接口（5个）
- `daily_info` - 每日市场交易统计
- `moneyflow_hsgt` - 沪深港通资金流向
- `margin` - 融资融券交易汇总
- `limit_list_d` - 涨跌停统计
- `stk_limit` - 每日涨跌停价格

## 📍 主要调用位置

### 核心实现文件
1. **`tradingagents/dataflows/providers/china/tushare.py`** - 主要实现文件
   - 包含所有接口的封装方法
   - 提供异步和同步两种调用方式
   - 数据标准化处理

2. **`app/services/data_sources/tushare_adapter.py`** - 适配器层
   - 提供统一的数据源接口
   - 封装常用方法（`get_stock_list`, `get_daily_basic`, `get_realtime_quotes`, `get_kline`）

3. **`app/services/basics_sync/utils.py`** - 基础数据同步工具
   - `fetch_stock_basic_df()` - 使用 `stock_basic`
   - `find_latest_trade_date()` - 使用 `daily_basic`
   - `fetch_daily_basic_mv_map()` - 使用 `daily_basic`
   - `fetch_latest_roe_map()` - 使用 `fina_indicator`

4. **`app/worker/tushare_sync_service.py`** - 数据同步服务
   - 调用 `TushareProvider` 的各种方法进行数据同步
   - 支持基础信息、实时行情、历史数据、财务数据、新闻数据的同步

## 💡 使用说明

### 接口调用方式

#### 1. 通过 TushareProvider（推荐）
```python
from tradingagents.dataflows.providers.china.tushare import TushareProvider

provider = TushareProvider()
await provider.connect()

# 获取股票列表
stock_list = await provider.get_stock_list()

# 获取历史数据
df = await provider.get_historical_data("000001", "2024-01-01", "2024-12-31")
```

#### 2. 直接调用 API（不推荐，除非特殊需求）
```python
from tradingagents.dataflows.providers.china.tushare import get_tushare_provider

provider = get_tushare_provider()
df = provider.api.stock_basic(list_status='L')
```

### 接口权限要求

| 接口类型 | 免费版 | 基础版 | 标准版 | 高级版 | VIP版 |
|---------|--------|--------|--------|--------|-------|
| 基础数据接口 | ✅ | ✅ | ✅ | ✅ | ✅ |
| 财务数据接口 | ❌ | ✅ | ✅ | ✅ | ✅ |
| 新闻公告接口 | ❌ | ❌ | ❌ | ✅ | ✅ |
| 板块行业接口 | ❌ | ❌ | ✅ | ✅ | ✅ |
| 指数数据接口 | ❌ | ✅ | ✅ | ✅ | ✅ |
| 市场分析接口 | ❌ | ❌ | ✅ | ✅ | ✅ |

### 接口调用频率限制

根据 Tushare 官方文档，不同版本有不同的调用频率限制：

- **免费版**：每分钟 120 次
- **基础版**：每分钟 200 次
- **标准版**：每分钟 500 次
- **高级版**：每分钟 1000 次
- **VIP版**：每分钟 2000 次

**特殊限制**：
- `rt_k` 接口：每小时最多调用 2 次（全市场批量接口）
- 建议使用速率限制器（`app.core.rate_limiter`）控制调用频率

## 🔍 接口详细说明

### 1. stock_basic（股票基础信息）
**用途**：获取股票列表和基础信息  
**调用位置**：
- `tushare.py:301` - `get_stock_list_sync()`
- `tushare.py:337` - `get_stock_list()`
- `tushare.py:1857` - `get_stock_industry_sync()`
- `utils.py:58` - `fetch_stock_basic_df()`

**主要字段**：
- `ts_code` - TS代码
- `symbol` - 股票代码
- `name` - 股票名称
- `area` - 地域
- `industry` - 所属行业
- `market` - 市场类型
- `list_date` - 上市日期

### 2. daily（日线行情）
**用途**：获取股票日线K线数据  
**调用位置**：
- `tushare.py:406` - `get_stock_quotes()`（获取最新一天数据）
- `tushare.py:2457` - `get_daily_stats()`（统计涨跌家数）

**主要字段**：
- `trade_date` - 交易日期
- `open` - 开盘价
- `high` - 最高价
- `low` - 最低价
- `close` - 收盘价
- `pre_close` - 昨收价
- `change` - 涨跌额
- `pct_chg` - 涨跌幅
- `vol` - 成交量（手）
- `amount` - 成交额（千元）

### 3. daily_basic（每日基础指标）
**用途**：获取每日估值和交易指标  
**调用位置**：
- `tushare.py:707` - `get_daily_basic()`
- `tushare.py:734` - `find_latest_trade_date()`
- `tushare.py:1937` - `get_sector_stocks_daily_basic()`
- `tushare_adapter.py:89` - `get_daily_basic()`
- `utils.py:105` - `find_latest_trade_date()`
- `utils.py:127` - `fetch_daily_basic_mv_map()`

**主要字段**：
- `ts_code` - TS代码
- `trade_date` - 交易日期
- `total_mv` - 总市值（万元）
- `circ_mv` - 流通市值（万元）
- `pe` - 市盈率
- `pb` - 市净率
- `ps` - 市销率
- `pe_ttm` - 市盈率TTM
- `pb_mrq` - 市净率MRQ
- `ps_ttm` - 市销率TTM
- `turnover_rate` - 换手率
- `volume_ratio` - 量比

### 4. pro_bar（K线数据-复权）
**用途**：获取前复权/后复权K线数据  
**调用位置**：
- `tushare.py:626` - `get_historical_data()`（通过 `ts.pro_bar`）
- `tushare_adapter.py:208` - `get_kline()`（通过 `tushare.pro.data_pro.pro_bar`）

**特点**：
- 支持前复权（qfq）、后复权（hfq）
- 支持日线、周线、月线、分钟线
- 必须使用 `ts.pro_bar()` 函数，不是 `api.pro_bar()` 方法

### 5. rt_k（实时行情）
**用途**：批量获取全市场实时行情  
**调用位置**：
- `tushare.py:461` - `get_realtime_quotes_batch()`（使用通配符）
- `tushare_adapter.py:107` - `get_realtime_quotes()`（使用通配符）
- `quotes_ingestion_service.py:230` - 测试调用

**特点**：
- 支持通配符：`3*.SZ,6*.SH,0*.SZ,9*.BJ`
- 每小时最多调用 2 次（全市场批量接口）
- 少量股票（≤10只）建议切换到 AKShare 接口

### 6-10. 财务数据接口
**用途**：获取财务报表数据  
**调用位置**：
- `tushare.py:790` - `get_financial_data()` - `income`
- `tushare.py:804` - `get_financial_data()` - `balancesheet`
- `tushare.py:818` - `get_financial_data()` - `cashflow`
- `tushare.py:832` - `get_financial_data()` - `fina_indicator`
- `tushare.py:846` - `get_financial_data()` - `fina_mainbz`
- `utils.py:201` - `fetch_latest_roe_map()` - `fina_indicator`

### 11-12. 新闻公告接口
**用途**：获取股票相关新闻和公告  
**调用位置**：
- `tushare.py:926` - `get_stock_news()` - `news`
- `tushare_adapter.py:266` - `get_news()` - `anns`（公告）

**注意**：需要付费权限

### 13-16. 板块行业接口
**用途**：获取板块和行业相关数据  
**调用位置**：
- `tushare.py:1714` - `get_ths_index_list()` - `ths_index`
- `tushare.py:1750` - `get_ths_daily()` - `ths_daily`
- `tushare.py:1788` - `get_ths_member()` - `ths_member`
- `tushare.py:1831` - `get_moneyflow_ths()` - `moneyflow_ths`

### 17-21. 指数数据接口
**用途**：获取指数相关数据  
**调用位置**：
- `tushare.py:1990` - `get_index_basic()` - `index_basic`
- `tushare.py:2048` - `get_index_daily()` - `index_daily`
- `tushare.py:2121` - `get_index_dailybasic()` - `index_dailybasic`
- `tushare.py:2238` - `get_index_weight()` - `index_weight`
- `tushare.py:2192` - `get_daily_info()` - `daily_info`

### 22-25. 市场分析接口
**用途**：获取市场分析数据  
**调用位置**：
- `tushare.py:2284` - `get_hsgt_moneyflow()` - `moneyflow_hsgt`
- `tushare.py:2343` - `get_margin_detail()` - `margin`
- `tushare.py:2390` - `get_limit_list()` - `limit_list_d`
- `tushare.py:2421` - `get_stk_limit()` - `stk_limit`

## 📝 总结

### 接口总数
**共使用 25 个 Tushare API 接口**

### 使用频率分布
- ⭐⭐⭐⭐⭐（5个）：基础数据接口，使用最频繁
- ⭐⭐⭐⭐（1个）：实时行情接口，使用频繁但有限制
- ⭐⭐⭐（5个）：财务数据接口，定期同步使用
- ⭐⭐（6个）：板块、指数、新闻接口，按需使用
- ⭐（8个）：市场分析接口，特殊场景使用

### 建议
1. **优先使用封装方法**：通过 `TushareProvider` 调用，而不是直接调用 API
2. **注意调用频率**：使用速率限制器控制调用频率，避免触发限流
3. **合理使用批量接口**：少量股票时切换到 AKShare，避免浪费 `rt_k` 配额
4. **数据缓存**：部分接口支持缓存，合理使用缓存减少 API 调用
5. **错误处理**：注意处理限流错误和权限错误

---

**最后更新**：2026-01-24  
**统计版本**：v1.0
