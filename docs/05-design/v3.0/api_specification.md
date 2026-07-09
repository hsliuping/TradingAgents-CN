# TradingAgents-CN API接口规范

## 📋 概述

本文档详细描述了TradingAgents-CN系统中各个模块的API接口规范，包括输入参数、输出格式、错误处理等。

---

## 🔧 核心API接口

### 1. 统一基本面分析工具

#### 接口定义
```python
def get_stock_fundamentals_unified(
    ticker: str,
    start_date: str,
    end_date: str,
    curr_date: str
) -> str
```

#### 输入参数
```json
{
    "ticker": "002027",           // 股票代码 (必填)
    "start_date": "2025-06-01",   // 开始日期 (必填)
    "end_date": "2025-07-15",     // 结束日期 (必填)
    "curr_date": "2025-07-15"     // 当前日期 (必填)
}
```

#### 输出格式
```markdown
# 中国A股基本面分析报告 - 002027

## 📊 股票基本信息
- **股票代码**: 002027
- **股票名称**: 分众传媒
- **所属行业**: 广告包装
- **当前股价**: ¥7.67
- **涨跌幅**: -1.41%

## 💰 财务数据分析
### 估值指标
- **PE比率**: 18.5倍
- **PB比率**: 1.8倍
- **股息收益率**: 2.5%

### 盈利能力
- **ROE**: 12.8%
- **ROA**: 6.2%
- **毛利率**: 25.5%

## 📈 投资建议
综合评分: 6.5/10
建议: 谨慎持有
```

### 2. 市场技术分析工具

#### 接口定义
```python
def get_stock_market_analysis(
    ticker: str,
    period: str = "1y",
    indicators: List[str] = None
) -> str
```

#### 输入参数
```json
{
    "ticker": "002027",
    "period": "1y",
    "indicators": ["SMA", "EMA", "RSI", "MACD", "BOLL"]
}
```

#### 输出格式
```markdown
# 市场技术分析报告 - 002027

## 📈 价格趋势分析
- **当前趋势**: 震荡下行
- **支撑位**: ¥7.12
- **阻力位**: ¥7.87

## 📊 技术指标
- **RSI(14)**: 45.2 (中性)
- **MACD**: -0.05 (看跌)
- **布林带**: 价格接近下轨

## 🎯 技术面建议
短期: 观望
中期: 谨慎
```

### 3. 新闻情绪分析工具

#### 接口定义
```python
def get_stock_news_analysis(
    ticker: str,
    company_name: str,
    date_range: str = "7d"
) -> str
```

#### 输入参数
```json
{
    "ticker": "002027",
    "company_name": "分众传媒",
    "date_range": "7d"
}
```

#### 输出格式
```markdown
# 新闻分析报告 - 002027

## 📰 新闻概览
- **新闻总数**: 15条
- **正面新闻**: 8条 (53%)
- **负面新闻**: 3条 (20%)
- **中性新闻**: 4条 (27%)

## 🔥 热点事件
1. Q2财报发布，业绩超预期
2. 新增重要客户合作
3. 行业政策调整影响

## 📊 情绪指数
- **整体情绪**: 偏正面 (65%)
- **关注热度**: 中等
- **影响评估**: 短期正面
```

---

## 🤖 智能体API接口

### 1. 基本面分析师

#### 接口定义
```python
def fundamentals_analyst(state: Dict[str, Any]) -> Dict[str, Any]
```

#### 输入状态
```json
{
    "company_of_interest": "002027",
    "trade_date": "2025-07-15",
    "messages": [],
    "fundamentals_report": ""
}
```

#### 输出状态
```json
{
    "company_of_interest": "002027",
    "trade_date": "2025-07-15",
    "messages": [...],
    "fundamentals_report": "详细的基本面分析报告..."
}
```

### 2. 市场分析师

#### 接口定义
```python
def market_analyst(state: Dict[str, Any]) -> Dict[str, Any]
```

#### 输入状态
```json
{
    "company_of_interest": "002027",
    "trade_date": "2025-07-15",
    "messages": [],
    "market_report": ""
}
```

#### 输出状态
```json
{
    "company_of_interest": "002027",
    "trade_date": "2025-07-15",
    "messages": [...],
    "market_report": "详细的市场分析报告..."
}
```

### 3. 看涨/看跌研究员

#### 接口定义
```python
def bull_researcher(state: Dict[str, Any]) -> Dict[str, Any]
def bear_researcher(state: Dict[str, Any]) -> Dict[str, Any]
```

#### 输入状态
```json
{
    "company_of_interest": "002027",
    "trade_date": "2025-07-15",
    "fundamentals_report": "基本面分析报告...",
    "market_report": "市场分析报告...",
    "investment_debate_state": {
        "history": "",
        "current_response": "",
        "count": 0
    }
}
```

#### 输出状态
```json
{
    "investment_debate_state": {
        "history": "辩论历史...",
        "current_response": "当前回应...",
        "count": 1
    }
}
```

### 4. 交易员

#### 接口定义
```python
def trader(state: Dict[str, Any]) -> Dict[str, Any]
```

#### 输入状态
```json
{
    "company_of_interest": "002027",
    "trade_date": "2025-07-15",
    "fundamentals_report": "基本面分析...",
    "market_report": "市场分析...",
    "news_report": "新闻分析...",
    "sentiment_report": "情绪分析...",
    "investment_debate_state": {
        "history": "研究员辩论历史..."
    }
}
```

#### 输出状态
```json
{
    "trader_signal": "详细的交易决策信号...",
    "final_decision": {
        "action": "买入",
        "target_price": 8.50,
        "confidence": 0.75,
        "risk_score": 0.4,
        "reasoning": "基于综合分析的投资理由..."
    }
}
```

---

## 📊 数据源API接口

### 1. Tushare数据接口

#### 股票基本数据
```python
def get_china_stock_data_tushare(
    ticker: str,
    start_date: str,
    end_date: str
) -> str
```

#### 股票信息
```python
def get_china_stock_info_tushare(ticker: str) -> Dict[str, Any]
```

### 2. 统一数据接口

#### 中国股票数据
```python
def get_china_stock_data_unified(
    symbol: str,
    start_date: str,
    end_date: str
) -> str
```

#### 数据源切换
```python
def switch_china_data_source(source: str) -> bool
```

---

## 🔧 工具API接口

### 1. 股票工具类

#### 市场信息获取
```python
def get_market_info(ticker: str) -> Dict[str, Any]
```

#### 返回格式
```json
{
    "ticker": "002027",
    "market": "china_a",
    "market_name": "中国A股",
    "currency_name": "人民币",
    "currency_symbol": "¥",
    "is_china": true,
    "is_hk": false,
    "is_us": false
}
```

### 2. 缓存管理API

#### 缓存操作
```python
def get_cache(key: str) -> Any
def set_cache(key: str, value: Any, ttl: int = 3600) -> bool
def clear_cache(pattern: str = "*") -> int
```

---

## ⚠️ 错误处理

### 错误代码规范

| 错误代码 | 错误类型 | 描述 |
|---------|---------|------|
| 1001 | 参数错误 | 必填参数缺失或格式错误 |
| 1002 | 股票代码错误 | 股票代码不存在或格式错误 |
| 2001 | 数据源错误 | 外部API调用失败 |
| 2002 | 缓存错误 | 缓存系统异常 |
| 3001 | LLM错误 | 语言模型调用失败 |
| 3002 | 分析错误 | 分析过程异常 |
| 4001 | 系统错误 | 系统内部错误 |

### 错误响应格式
```json
{
    "success": false,
    "error_code": 1002,
    "error_message": "股票代码格式错误",
    "error_details": "股票代码应为6位数字",
    "timestamp": "2025-07-16T01:30:00Z"
}
```

---

## 🔒 安全规范

### 1. API密钥管理
- 所有API密钥通过环境变量配置
- 支持密钥轮换和失效检测
- 密钥格式验证和安全存储

### 2. 访问控制
- 基于角色的访问控制 (RBAC)
- API调用频率限制
- 请求来源验证

### 3. 数据安全
- 传输数据加密 (HTTPS)
- 敏感数据脱敏处理
- 审计日志记录

---

## 📈 性能规范

### 1. 响应时间要求
- 数据获取: < 5秒
- 单个分析师: < 30秒
- 完整分析流程: < 3分钟

### 2. 并发处理
- 支持最多10个并发分析请求
- 智能队列管理
- 资源使用监控

### 3. 缓存策略
- 热数据缓存: 1小时
- 温数据缓存: 24小时
- 冷数据缓存: 7天

---

## 🧪 测试规范

### 1. 单元测试
- 每个API接口都有对应的单元测试
- 测试覆盖率要求 > 80%
- 包含正常和异常情况测试

### 2. 集成测试
- 端到端流程测试
- 数据源集成测试
- LLM集成测试

### 3. 性能测试
- 负载测试
- 压力测试
- 稳定性测试
