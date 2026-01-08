# 股票数据模型设计方案

## 📋 设计目标

1. **数据标准化**: 统一不同数据源的数据格式
2. **解耦架构**: 数据获取服务与数据使用服务分离
3. **易于扩展**: 新增数据源只需实现标准接口
4. **高性能**: 优化的索引和查询结构
5. **数据完整性**: 完整的数据验证和约束

## 🏗️ 架构设计

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   数据获取服务   │    │   MongoDB数据库  │    │   数据使用服务   │
│                │    │                │    │                │
│ • Tushare SDK  │───▶│ • 标准化数据模型 │◀───│ • 分析服务      │
│ • AKShare SDK  │    │ • 统一数据接口  │    │ • API服务       │
│ • Yahoo SDK    │    │ • 索引优化      │    │ • Web界面       │
│ • Finnhub SDK  │    │ • 数据验证      │    │ • CLI工具       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 📊 数据模型设计

### 1. 股票基础信息 (stock_basic_info)

```javascript
{
  "_id": ObjectId("..."),
  "symbol": "000001",           // 原始股票代码 (A股6位/港股4位/美股字母)
  "full_symbol": "000001.SZ",   // 完整标准化代码
  "name": "平安银行",            // 股票名称
  "name_en": "Ping An Bank",    // 英文名称

  // 市场信息 (统一市场区分设计)
  "market_info": {
    "market": "CN",             // 市场标识 (CN-A股/HK-港股/US-美股)
    "exchange": "SZSE",         // 交易所代码 (SZSE/SSE/SEHK/NYSE/NASDAQ)
    "exchange_name": "深圳证券交易所", // 交易所名称
    "currency": "CNY",          // 交易货币 (CNY/HKD/USD)
    "timezone": "Asia/Shanghai", // 时区
    "trading_hours": {          // 交易时间
      "open": "09:30",
      "close": "15:00",
      "lunch_break": ["11:30", "13:00"]
    }
  },

  "board": "主板",              // 板块 (主板/中小板/创业板/科创板/纳斯达克/纽交所)
  "industry": "银行",           // 行业
  "industry_code": "J66",       // 行业代码
  "sector": "金融业",           // 所属板块
  "list_date": "1991-04-03",    // 上市日期
  "delist_date": null,          // 退市日期
  "area": "深圳",               // 所在地区
  "market_cap": 2500000000000,  // 总市值 (基础货币)
  "float_cap": 1800000000000,   // 流通市值 (基础货币)
  "total_shares": 19405918198,  // 总股本
  "float_shares": 19405918198,  // 流通股本
  "status": "L",                // 上市状态 (L-上市 D-退市 P-暂停)
  "is_hs": true,                // 是否沪深港通标的 (仅A股)
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z"),
  "data_source": "tushare",     // 数据来源
  "version": 1                  // 数据版本
}
```

### 2. 历史行情数据 (stock_daily_quotes)

```javascript
{
  "_id": ObjectId("..."),
  "symbol": "000001",           // 原始股票代码
  "full_symbol": "000001.SZ",   // 完整标准化代码
  "market": "CN",               // 市场标识
  "trade_date": "2024-01-15",   // 交易日期
  "open": 12.50,                // 开盘价
  "high": 12.80,                // 最高价
  "low": 12.30,                 // 最低价
  "close": 12.65,               // 收盘价
  "pre_close": 12.45,           // 前收盘价
  "change": 0.20,               // 涨跌额
  "pct_chg": 1.61,              // 涨跌幅 (%)
  "volume": 125000000,          // 成交量 (股/手，根据市场而定)
  "amount": 1580000000,         // 成交额 (基础货币)
  "turnover_rate": 0.64,        // 换手率 (%)
  "volume_ratio": 1.2,          // 量比
  "pe": 5.2,                    // 市盈率
  "pb": 0.8,                    // 市净率
  "ps": 1.1,                    // 市销率
  "dv_ratio": 0.05,             // 股息率
  "dv_ttm": 0.6,                // 滚动股息率
  "total_mv": 2450000000000,    // 总市值 (基础货币)
  "circ_mv": 2450000000000,     // 流通市值 (基础货币)
  "adj_factor": 1.0,            // 复权因子
  "created_at": ISODate("2024-01-15T16:00:00Z"),
  "data_source": "tushare",
  "version": 1
}
```

### 3. 实时行情数据 (stock_realtime_quotes)

```javascript
{
  "_id": ObjectId("..."),
  "symbol": "000001",           // 原始股票代码
  "full_symbol": "000001.SZ",   // 完整标准化代码
  "market": "CN",               // 市场标识
  "name": "平安银行",
  "current_price": 12.65,       // 当前价格
  "pre_close": 12.45,           // 前收盘价
  "open": 12.50,                // 今开
  "high": 12.80,                // 今高
  "low": 12.30,                 // 今低
  "change": 0.20,               // 涨跌额
  "pct_chg": 1.61,              // 涨跌幅
  "volume": 125000000,          // 成交量
  "amount": 1580000000,         // 成交额 (基础货币)
  "turnover_rate": 0.64,        // 换手率
  "bid_prices": [12.64, 12.63, 12.62, 12.61, 12.60], // 买1-5价
  "bid_volumes": [100, 200, 300, 400, 500],           // 买1-5量
  "ask_prices": [12.65, 12.66, 12.67, 12.68, 12.69], // 卖1-5价
  "ask_volumes": [150, 250, 350, 450, 550],           // 卖1-5量
  "timestamp": ISODate("2024-01-15T14:30:00Z"),       // 行情时间 (市场时区)
  "created_at": ISODate("2024-01-15T14:30:05Z"),
  "data_source": "akshare",
  "version": 1
}
```

### 4. 财务数据 (stock_financial_data)

```javascript
{
  "_id": ObjectId("..."),
  "symbol": "000001",           // 原始股票代码
  "full_symbol": "000001.SZ",   // 完整标准化代码
  "market": "CN",               // 市场标识
  "report_period": "20231231",  // 报告期
  "report_type": "annual",      // 报告类型 (annual/quarterly)
  "ann_date": "2024-03-20",     // 公告日期
  "f_ann_date": "2024-03-20",   // 实际公告日期
  
  // 资产负债表数据
  "balance_sheet": {
    "total_assets": 4500000000000,      // 资产总计
    "total_liab": 4200000000000,        // 负债合计
    "total_hldr_eqy_exc_min_int": 280000000000, // 股东权益合计
    "total_cur_assets": 2800000000000,  // 流动资产合计
    "total_nca": 1700000000000,         // 非流动资产合计
    "total_cur_liab": 3800000000000,    // 流动负债合计
    "total_ncl": 400000000000,          // 非流动负债合计
    "cash_and_equivalents": 180000000000 // 货币资金
  },
  
  // 利润表数据
  "income_statement": {
    "total_revenue": 180000000000,      // 营业总收入
    "revenue": 180000000000,            // 营业收入
    "oper_cost": 45000000000,           // 营业总成本
    "gross_profit": 135000000000,       // 毛利润
    "oper_profit": 85000000000,         // 营业利润
    "total_profit": 86000000000,        // 利润总额
    "n_income": 65000000000,            // 净利润
    "n_income_attr_p": 65000000000,     // 归母净利润
    "basic_eps": 3.35,                  // 基本每股收益
    "diluted_eps": 3.35                 // 稀释每股收益
  },
  
  // 现金流量表数据
  "cashflow_statement": {
    "n_cashflow_act": 120000000000,     // 经营活动现金流量净额
    "n_cashflow_inv_act": -25000000000, // 投资活动现金流量净额
    "n_cashflow_fin_act": -15000000000, // 筹资活动现金流量净额
    "c_cash_equ_end_period": 180000000000, // 期末现金及现金等价物余额
    "c_cash_equ_beg_period": 100000000000  // 期初现金及现金等价物余额
  },
  
  // 财务指标
  "financial_indicators": {
    "roe": 23.21,                       // 净资产收益率
    "roa": 1.44,                        // 总资产收益率
    "gross_margin": 75.0,               // 毛利率
    "net_margin": 36.11,                // 净利率
    "debt_to_assets": 93.33,            // 资产负债率
    "current_ratio": 0.74,              // 流动比率
    "quick_ratio": 0.74,                // 速动比率
    "eps": 3.35,                        // 每股收益
    "bvps": 14.44,                      // 每股净资产
    "pe": 3.78,                         // 市盈率
    "pb": 0.88,                         // 市净率
    "dividend_yield": 4.73              // 股息率
  },
  
  "created_at": ISODate("2024-03-20T00:00:00Z"),
  "updated_at": ISODate("2024-03-20T00:00:00Z"),
  "data_source": "tushare",
  "version": 1
}
```

### 5. 新闻数据 (stock_news)

```javascript
{
  "_id": ObjectId("..."),
  "symbol": "000001",           // 主要相关股票代码
  "full_symbol": "000001.SZ",   // 完整标准化代码
  "market": "CN",               // 市场标识
  "symbols": ["000001", "000002"], // 相关股票列表
  "title": "平安银行发布2023年年报",
  "content": "平安银行股份有限公司今日发布2023年年度报告...",
  "summary": "平安银行2023年净利润同比增长2.6%",
  "url": "https://example.com/news/123",
  "source": "证券时报",
  "author": "张三",
  "publish_time": ISODate("2024-03-20T09:00:00Z"),
  "category": "company_announcement", // 新闻类别
  "sentiment": "positive",      // 情绪分析 (positive/negative/neutral)
  "sentiment_score": 0.75,      // 情绪得分 (-1到1)
  "keywords": ["年报", "净利润", "增长"],
  "importance": "high",         // 重要性 (high/medium/low)
  "language": "zh-CN",
  "created_at": ISODate("2024-03-20T09:05:00Z"),
  "data_source": "finnhub",
  "version": 1
}
```

### 6. 社媒消息数据 (social_media_messages)

```javascript
{
  "_id": ObjectId("..."),
  "symbol": "000001",           // 主要相关股票代码
  "full_symbol": "000001.SZ",   // 完整标准化代码
  "market": "CN",               // 市场标识
  "symbols": ["000001", "000002"], // 相关股票列表

  // 消息基本信息
  "message_id": "weibo_123456789",  // 原始消息ID
  "platform": "weibo",         // 平台类型 (weibo/wechat/douyin/xiaohongshu/zhihu/twitter/reddit)
  "message_type": "post",      // 消息类型 (post/comment/repost/reply)
  "content": "平安银行今天涨停了，基本面确实不错...",
  "media_urls": ["https://example.com/image1.jpg"], // 媒体文件URL
  "hashtags": ["#平安银行", "#涨停"],

  // 作者信息
  "author": {
    "user_id": "user_123",
    "username": "股市小散",
    "display_name": "投资达人",
    "verified": false,          // 是否认证用户
    "follower_count": 10000,    // 粉丝数
    "influence_score": 0.75     // 影响力评分 (0-1)
  },

  // 互动数据
  "engagement": {
    "likes": 150,
    "shares": 25,
    "comments": 30,
    "views": 5000,
    "engagement_rate": 0.041    // 互动率
  },

  // 时间信息
  "publish_time": ISODate("2024-03-20T14:30:00Z"),
  "crawl_time": ISODate("2024-03-20T15:00:00Z"),

  // 分析结果
  "sentiment": "positive",      // 情绪分析 (positive/negative/neutral)
  "sentiment_score": 0.8,       // 情绪得分 (-1到1)
  "confidence": 0.85,           // 分析置信度
  "keywords": ["涨停", "基本面", "不错"],
  "topics": ["股价表现", "基本面分析"],
  "importance": "medium",       // 重要性 (high/medium/low)
  "credibility": "medium",      // 可信度 (high/medium/low)

  // 地理位置
  "location": {
    "country": "CN",
    "province": "广东",
    "city": "深圳"
  },

  // 元数据
  "language": "zh-CN",
  "created_at": ISODate("2024-03-20T15:00:00Z"),
  "updated_at": ISODate("2024-03-20T15:00:00Z"),
  "data_source": "crawler_weibo",
  "crawler_version": "1.0",
  "version": 1
}
```

### 7. 内部消息数据 (internal_messages)

```javascript
{
  "_id": ObjectId("..."),
  "symbol": "000001",           // 主要相关股票代码
  "full_symbol": "000001.SZ",   // 完整标准化代码
  "market": "CN",               // 市场标识
  "symbols": ["000001", "000002"], // 相关股票列表

  // 消息基本信息
  "message_id": "internal_20240320_001",
  "message_type": "research_report", // 消息类型 (research_report/insider_info/analyst_note/meeting_minutes/internal_analysis)
  "title": "平安银行Q1业绩预期分析",
  "content": "根据内部分析，平安银行Q1业绩预期...",
  "summary": "Q1净利润预期增长5-8%",

  // 来源信息
  "source": {
    "type": "internal_research",  // 来源类型 (internal_research/insider/analyst/meeting/system_analysis)
    "department": "研究部",
    "author": "张分析师",
    "author_id": "analyst_001",
    "reliability": "high"        // 可靠性 (high/medium/low)
  },

  // 分类信息
  "category": "fundamental_analysis", // 类别 (fundamental_analysis/technical_analysis/market_sentiment/risk_assessment)
  "subcategory": "earnings_forecast",
  "tags": ["业绩预期", "财务分析", "Q1"],

  // 重要性和影响
  "importance": "high",         // 重要性 (high/medium/low)
  "impact_scope": "stock_specific", // 影响范围 (stock_specific/sector/market_wide)
  "time_sensitivity": "short_term", // 时效性 (immediate/short_term/medium_term/long_term)
  "confidence_level": 0.85,     // 置信度 (0-1)

  // 分析结果
  "sentiment": "positive",      // 情绪倾向
  "sentiment_score": 0.7,       // 情绪得分
  "keywords": ["业绩", "增长", "预期"],
  "risk_factors": ["监管政策", "市场环境"],
  "opportunities": ["业务扩张", "成本控制"],

  // 相关数据
  "related_data": {
    "financial_metrics": ["roe", "roa", "net_profit"],
    "price_targets": [15.5, 16.0, 16.8],
    "rating": "buy"             // 评级 (strong_buy/buy/hold/sell/strong_sell)
  },

  // 访问控制
  "access_level": "internal",   // 访问级别 (public/internal/restricted/confidential)
  "permissions": ["research_team", "portfolio_managers"],

  // 时间信息
  "created_time": ISODate("2024-03-20T10:00:00Z"),
  "effective_time": ISODate("2024-03-20T10:00:00Z"),
  "expiry_time": ISODate("2024-06-20T10:00:00Z"),

  // 元数据
  "language": "zh-CN",
  "created_at": ISODate("2024-03-20T10:00:00Z"),
  "updated_at": ISODate("2024-03-20T10:00:00Z"),
  "data_source": "internal_system",
  "version": 1
}
```

### 8. 技术指标数据 (stock_technical_indicators)

```javascript
{
  "_id": ObjectId("..."),
  "symbol": "000001",           // 原始股票代码
  "full_symbol": "000001.SZ",   // 完整标准化代码
  "market": "CN",               // 市场标识
  "trade_date": "2024-01-15",   // 交易日期
  "period": "daily",            // 周期 (daily/weekly/monthly/5min/15min/30min/60min)

  // 基础移动平均线 (固定字段，常用指标)
  "ma": {
    "ma5": 12.45,
    "ma10": 12.38,
    "ma20": 12.25,
    "ma60": 12.10,
    "ma120": 12.05,
    "ma250": 11.95
  },

  // 动态技术指标 (分类扩展设计)
  "indicators": {
    // 趋势指标
    "trend": {
      "macd": 0.15,             // MACD
      "macd_signal": 0.12,      // MACD信号线
      "macd_hist": 0.03,        // MACD柱状图
      "ema12": 12.55,           // 12日指数移动平均
      "ema26": 12.35,           // 26日指数移动平均
      "dmi_pdi": 25.8,          // DMI正向指标
      "dmi_mdi": 18.2,          // DMI负向指标
      "dmi_adx": 32.5,          // DMI平均趋向指标
      "aroon_up": 75.0,         // 阿隆上线
      "aroon_down": 25.0        // 阿隆下线
    },

    // 震荡指标
    "oscillator": {
      "rsi": 65.5,              // RSI相对强弱指标
      "rsi_6": 68.2,            // 6日RSI
      "rsi_14": 65.5,           // 14日RSI
      "kdj_k": 75.2,            // KDJ-K值
      "kdj_d": 68.8,            // KDJ-D值
      "kdj_j": 88.0,            // KDJ-J值
      "williams_r": -25.8,      // 威廉指标
      "cci": 120.5,             // CCI顺势指标
      "stoch_k": 78.5,          // 随机指标K值
      "stoch_d": 72.3,          // 随机指标D值
      "roc": 1.8,               // 变动率指标
      "momentum": 0.25          // 动量指标
    },

    // 通道指标
    "channel": {
      "boll_upper": 13.20,      // 布林带上轨
      "boll_mid": 12.65,        // 布林带中轨
      "boll_lower": 12.10,      // 布林带下轨
      "boll_width": 0.087,      // 布林带宽度
      "donchian_upper": 13.50,  // 唐奇安通道上轨
      "donchian_lower": 12.00,  // 唐奇安通道下轨
      "keltner_upper": 13.15,   // 肯特纳通道上轨
      "keltner_lower": 12.15,   // 肯特纳通道下轨
      "sar": 12.35              // 抛物线SAR
    },

    // 成交量指标
    "volume": {
      "obv": 1250000000,        // 能量潮指标
      "ad_line": 850000000,     // 累积/派发线
      "cmf": 0.15,              // 蔡金资金流量
      "vwap": 12.58,            // 成交量加权平均价
      "mfi": 45.2,              // 资金流量指标
      "ease_of_movement": 0.08, // 简易波动指标
      "volume_sma": 98000000,   // 成交量移动平均
      "price_volume_trend": 125000000 // 价量趋势指标
    },

    // 波动率指标
    "volatility": {
      "atr": 0.45,              // 真实波动幅度
      "natr": 3.56,             // 标准化ATR
      "trange": 0.50,           // 真实范围
      "stddev": 0.38,           // 标准差
      "variance": 0.14          // 方差
    },

    // 自定义指标 (用户可扩展)
    "custom": {
      "my_strategy_signal": "buy", // 自定义策略信号
      "risk_score": 0.3,        // 风险评分
      "strength_index": 0.75,   // 强度指数
      "market_sentiment": "bullish" // 市场情绪
    }
  },

  // 指标元数据 (计算参数和版本信息)
  "indicator_metadata": {
    "calculation_time": ISODate("2024-01-15T16:30:00Z"),
    "calculation_version": "v2.1",
    "parameters": {
      "rsi_period": 14,
      "macd_fast": 12,
      "macd_slow": 26,
      "macd_signal": 9,
      "boll_period": 20,
      "boll_std": 2,
      "kdj_period": 9,
      "williams_period": 14,
      "cci_period": 14
    },
    "data_quality": {
      "completeness": 1.0,      // 数据完整性 (0-1)
      "accuracy": 0.98,         // 数据准确性 (0-1)
      "timeliness": 0.95        // 数据及时性 (0-1)
    }
  },

  "created_at": ISODate("2024-01-15T16:30:00Z"),
  "data_source": "calculated",
  "version": 1
}
```

### 7. 数据源配置 (data_source_config)

```javascript
{
  "_id": ObjectId("..."),
  "source_name": "tushare",
  "source_type": "api",         // api/file/database
  "priority": 1,                // 优先级 (数字越小优先级越高)
  "status": "active",           // active/inactive/maintenance
  "config": {
    "api_url": "http://api.tushare.pro",
    "token": "your_token_here",
    "rate_limit": 200,          // 每分钟请求限制
    "timeout": 30,              // 超时时间(秒)
    "retry_times": 3            // 重试次数
  },
  "supported_data_types": [
    "stock_basic_info",
    "stock_daily_quotes", 
    "stock_financial_data"
  ],
  "supported_markets": ["CN"],  // CN/US/HK
  "last_sync_time": ISODate("2024-01-15T16:00:00Z"),
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-15T16:00:00Z")
}
```

### 8. 数据同步日志 (data_sync_logs)

```javascript
{
  "_id": ObjectId("..."),
  "task_id": "sync_daily_quotes_20240115",
  "data_type": "stock_daily_quotes",
  "data_source": "tushare",
  "symbols": ["000001", "000002", "000858"], // 同步的股票列表
  "sync_date": "2024-01-15",
  "start_time": ISODate("2024-01-15T16:00:00Z"),
  "end_time": ISODate("2024-01-15T16:05:30Z"),
  "status": "completed",        // pending/running/completed/failed
  "total_records": 4500,        // 总记录数
  "success_records": 4500,      // 成功记录数
  "failed_records": 0,          // 失败记录数
  "error_message": null,
  "performance": {
    "duration_seconds": 330,
    "records_per_second": 13.6,
    "api_calls": 45,
    "cache_hits": 120
  },
  "created_at": ISODate("2024-01-15T16:00:00Z"),
  "updated_at": ISODate("2024-01-15T16:05:30Z")
}
```

## 📚 索引设计

### 主要索引

```javascript
// stock_basic_info 索引
db.stock_basic_info.createIndex({ "symbol": 1, "market": 1 }, { unique: true })
db.stock_basic_info.createIndex({ "full_symbol": 1 }, { unique: true })
db.stock_basic_info.createIndex({ "market_info.market": 1, "status": 1 })
db.stock_basic_info.createIndex({ "industry": 1 })
db.stock_basic_info.createIndex({ "market_info.exchange": 1 })

// stock_daily_quotes 索引
db.stock_daily_quotes.createIndex({ "symbol": 1, "market": 1, "trade_date": -1 }, { unique: true })
db.stock_daily_quotes.createIndex({ "full_symbol": 1, "trade_date": -1 })
db.stock_daily_quotes.createIndex({ "market": 1, "trade_date": -1 })
db.stock_daily_quotes.createIndex({ "trade_date": -1 })
db.stock_daily_quotes.createIndex({ "symbol": 1, "trade_date": -1, "volume": -1 })

// stock_realtime_quotes 索引
db.stock_realtime_quotes.createIndex({ "symbol": 1, "market": 1 }, { unique: true })
db.stock_realtime_quotes.createIndex({ "full_symbol": 1 }, { unique: true })
db.stock_realtime_quotes.createIndex({ "market": 1, "timestamp": -1 })
db.stock_realtime_quotes.createIndex({ "timestamp": -1 })
db.stock_realtime_quotes.createIndex({ "pct_chg": -1 })

// stock_financial_data 索引
db.stock_financial_data.createIndex({ "symbol": 1, "market": 1, "report_period": -1 }, { unique: true })
db.stock_financial_data.createIndex({ "full_symbol": 1, "report_period": -1 })
db.stock_financial_data.createIndex({ "market": 1, "report_period": -1 })
db.stock_financial_data.createIndex({ "report_period": -1 })
db.stock_financial_data.createIndex({ "ann_date": -1 })

// stock_news 索引
db.stock_news.createIndex({ "symbol": 1, "market": 1, "publish_time": -1 })
db.stock_news.createIndex({ "symbols": 1, "publish_time": -1 })
db.stock_news.createIndex({ "market": 1, "publish_time": -1 })
db.stock_news.createIndex({ "publish_time": -1 })
db.stock_news.createIndex({ "sentiment": 1, "importance": 1 })
db.stock_news.createIndex({ "keywords": 1 })

// stock_technical_indicators 索引
db.stock_technical_indicators.createIndex({ "symbol": 1, "market": 1, "trade_date": -1, "period": 1 }, { unique: true })
db.stock_technical_indicators.createIndex({ "full_symbol": 1, "trade_date": -1, "period": 1 })
db.stock_technical_indicators.createIndex({ "market": 1, "trade_date": -1 })
db.stock_technical_indicators.createIndex({ "trade_date": -1 })
```

## 🔧 技术指标扩展机制

### 1. 分类扩展设计

技术指标按功能分为5大类，每类可独立扩展：

```javascript
"indicators": {
  "trend": {        // 趋势指标 - 判断价格趋势方向
    // MACD, EMA, DMI, Aroon等
  },
  "oscillator": {   // 震荡指标 - 判断超买超卖
    // RSI, KDJ, Williams%R, CCI等
  },
  "channel": {      // 通道指标 - 判断支撑阻力
    // 布林带, 唐奇安通道, 肯特纳通道等
  },
  "volume": {       // 成交量指标 - 分析量价关系
    // OBV, VWAP, MFI, CMF等
  },
  "volatility": {   // 波动率指标 - 衡量价格波动
    // ATR, 标准差, 方差等
  },
  "custom": {       // 自定义指标 - 用户扩展
    // 策略信号, 风险评分等
  }
}
```

### 2. 新增指标的标准流程

**步骤1: 确定指标分类**
```javascript
// 例如：新增TRIX指标 (趋势指标)
"trend": {
  "trix": 0.0025,           // TRIX值
  "trix_signal": 0.0020,    // TRIX信号线
  "trix_hist": 0.0005       // TRIX柱状图
}
```

**步骤2: 更新指标元数据**
```javascript
"indicator_metadata": {
  "parameters": {
    "trix_period": 14,      // TRIX周期参数
    "trix_signal_period": 9 // 信号线周期参数
  }
}
```

**步骤3: 创建指标配置 (可选)**
```javascript
// 在 technical_indicator_configs 集合中添加
{
  "indicator_name": "trix",
  "indicator_category": "trend",
  "display_name": "TRIX三重指数平滑移动平均",
  "description": "TRIX指标用于判断长期趋势",
  "parameters": {
    "period": 14,
    "signal_period": 9
  },
  "calculation_formula": "TRIX = (EMA3 - EMA3_prev) / EMA3_prev * 10000",
  "data_type": "float",
  "enabled": true
}
```

### 3. 市场差异化支持

不同市场可能有特定的技术指标：

```javascript
// A股特有指标
"indicators": {
  "custom": {
    "a_share_specific": {
      "limit_up_days": 3,     // 连续涨停天数
      "turnover_anomaly": 0.8, // 换手率异常指标
      "institutional_flow": 0.6 // 机构资金流向
    }
  }
}

// 美股特有指标
"indicators": {
  "custom": {
    "us_specific": {
      "after_hours_change": 0.02, // 盘后涨跌幅
      "options_put_call_ratio": 0.85, // 期权看跌看涨比
      "insider_trading_score": 0.3 // 内部交易评分
    }
  }
}
```

### 4. 动态指标计算配置

```javascript
// 技术指标计算配置表: technical_indicator_configs
{
  "_id": ObjectId("..."),
  "indicator_name": "custom_momentum",
  "indicator_category": "oscillator",
  "display_name": "自定义动量指标",
  "description": "结合价格和成交量的动量指标",
  "markets": ["CN", "HK", "US"],    // 适用市场
  "periods": ["daily", "weekly"],   // 适用周期
  "parameters": {
    "price_weight": 0.7,
    "volume_weight": 0.3,
    "lookback_period": 20
  },
  "calculation_method": "python_function", // 计算方法
  "calculation_code": "def calculate_custom_momentum(prices, volumes, params): ...",
  "dependencies": ["close", "volume"],     // 依赖数据
  "output_fields": {
    "momentum_value": "float",
    "momentum_signal": "string"
  },
  "validation_rules": {
    "min_value": -100,
    "max_value": 100,
    "required": true
  },
  "enabled": true,
  "created_at": ISODate("2024-01-01T00:00:00Z"),
  "updated_at": ISODate("2024-01-01T00:00:00Z")
}
```

### 5. 指标版本管理

```javascript
"indicator_metadata": {
  "calculation_version": "v2.1",
  "version_history": [
    {
      "version": "v2.0",
      "changes": "优化MACD计算精度",
      "date": "2024-01-01"
    },
    {
      "version": "v2.1",
      "changes": "新增TRIX指标支持",
      "date": "2024-01-15"
    }
  ],
  "deprecated_indicators": ["old_rsi", "legacy_macd"]
}
```

## 🌍 多市场支持设计

### 1. 市场标识统一

| 市场代码 | 市场名称 | 交易所代码 | 货币 | 时区 |
|---------|----------|-----------|------|------|
| CN | 中国A股 | SZSE/SSE | CNY | Asia/Shanghai |
| HK | 港股 | SEHK | HKD | Asia/Hong_Kong |
| US | 美股 | NYSE/NASDAQ | USD | America/New_York |

### 2. 股票代码标准化

```javascript
// A股示例
{
  "symbol": "000001",           // 6位原始代码
  "full_symbol": "000001.SZ",   // 标准化完整代码
  "market_info": {
    "market": "CN",
    "exchange": "SZSE"
  }
}

// 港股示例
{
  "symbol": "0700",             // 4位原始代码
  "full_symbol": "0700.HK",     // 标准化完整代码
  "market_info": {
    "market": "HK",
    "exchange": "SEHK"
  }
}

// 美股示例
{
  "symbol": "AAPL",             // 字母代码
  "full_symbol": "AAPL.US",     // 标准化完整代码
  "market_info": {
    "market": "US",
    "exchange": "NASDAQ"
  }
}
```

### 3. 查询优化策略

```javascript
// 单市场查询 (最优性能)
db.stock_daily_quotes.find({
  "market": "CN",
  "trade_date": "2024-01-15"
})

// 跨市场查询
db.stock_daily_quotes.find({
  "market": {"$in": ["CN", "HK"]},
  "trade_date": "2024-01-15"
})

// 特定股票查询
db.stock_daily_quotes.find({
  "full_symbol": "000001.SZ"
})
```

---

*数据模型设计 - 最后更新: 2025-09-28*
