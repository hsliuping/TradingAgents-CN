# 提示词模板变量系统

## 📋 概述

提示词模板中的变量（如 `{company_name}`, `{market_name}`）是由系统在运行时自动填充的，不是通过 Agent 的输入参数传递的。

---

## 🔄 变量来源和流程

### 1. 变量从哪里来？

**答案**：从工作流状态（Workflow State）中提取

```
用户输入 → 工作流状态 → Agent 提取变量 → 渲染提示词模板 → 发送给 LLM
```

### 2. 完整流程示例

#### 步骤 1: 用户发起分析请求

```python
# 用户输入
{
  "ticker": "000858.SZ",
  "analysis_date": "2026-01-09"
}
```

#### 步骤 2: 工作流初始化状态

```python
state = {
  "ticker": "000858.SZ",
  "analysis_date": "2026-01-09",
  "company_of_interest": "000858.SZ",
  "trade_date": "2026-01-09"
}
```

#### 步骤 3: Agent 提取和扩展变量

```python
# 在 fundamentals_analyst.py 中
def execute(state):
    ticker = state.get("company_of_interest")  # "000858.SZ"
    current_date = state.get("trade_date")     # "2026-01-09"
    
    # 获取市场信息
    market_info = StockUtils.get_market_info(ticker)
    # 返回: {
    #   "market_name": "中国A股",
    #   "currency_name": "人民币",
    #   "currency_symbol": "¥",
    #   "is_china": True
    # }
    
    # 获取公司名称
    company_name = get_company_name(ticker)  # "五粮液"
    
    # 准备模板变量
    template_variables = {
        "ticker": ticker,                           # "000858.SZ"
        "company_name": company_name,               # "五粮液"
        "market_name": market_info['market_name'],  # "中国A股"
        "current_date": current_date,               # "2026-01-09"
        "start_date": start_date,                   # "2025-01-09"
        "currency_name": market_info['currency_name'],    # "人民币"
        "currency_symbol": market_info['currency_symbol'], # "¥"
        "tool_names": "get_stock_fundamentals_unified"
    }
```

#### 步骤 4: 渲染提示词模板

```python
# 模板内容（来自数据库）
template = """
你是一位专业的基本面分析师 v2.0。

**分析目标**: {company_name}（{ticker}，{market_name}）
**分析日期**: {current_date}

请使用{currency_name}（{currency_symbol}）进行所有金额表述。
"""

# 渲染后的提示词
rendered_prompt = """
你是一位专业的基本面分析师 v2.0。

**分析目标**: 五粮液（000858.SZ，中国A股）
**分析日期**: 2026-01-09

请使用人民币（¥）进行所有金额表述。
"""
```

---

## 📝 标准模板变量列表

### 核心变量（所有 Agent 通用）

| 变量名 | 来源 | 示例值 | 说明 |
|--------|------|--------|------|
| `ticker` | 工作流状态 | `000858.SZ` | 股票代码 |
| `company_name` | 动态获取 | `五粮液` | 公司名称 |
| `market_name` | `StockUtils.get_market_info()` | `中国A股` | 市场名称 |
| `current_date` | 工作流状态 | `2026-01-09` | 当前分析日期 |
| `start_date` | 计算得出 | `2025-01-09` | 开始日期（通常是1年前） |
| `currency_name` | `StockUtils.get_market_info()` | `人民币` | 货币名称 |
| `currency_symbol` | `StockUtils.get_market_info()` | `¥` | 货币符号 |
| `tool_names` | Agent 绑定的工具列表 | `get_stock_fundamentals_unified` | 可用工具名称 |

### 特定场景变量

| 变量名 | 使用场景 | 示例值 | 说明 |
|--------|----------|--------|------|
| `analysis_date` | 研究员、管理员 | `2026-01-09` | 分析日期 |
| `bull_report` | 研究管理员 | `看涨分析报告内容` | 看涨报告 |
| `bear_report` | 研究管理员 | `看跌分析报告内容` | 看跌报告 |
| `debate_summary` | 研究管理员 | `辩论总结内容` | 辩论总结 |
| `position_info` | 持仓分析 | `{code, name, market}` | 持仓信息 |

---

## 🔍 变量提取逻辑

### 1. 股票代码（ticker）

```python
# 直接从工作流状态获取
ticker = state.get("company_of_interest") or state.get("ticker")
```

### 2. 公司名称（company_name）

```python
def get_company_name(ticker: str) -> str:
    market_info = StockUtils.get_market_info(ticker)
    
    if market_info['is_china']:
        # 中国股票：调用 get_china_stock_info_unified
        stock_info = get_china_stock_info_unified(ticker)
        # 解析返回的字符串，提取公司名称
        if "股票名称:" in stock_info:
            return stock_info.split("股票名称:")[1].split("\n")[0].strip()
    
    elif market_info['is_us']:
        # 美股：使用硬编码映射
        us_stock_names = {
            'AAPL': '苹果公司',
            'TSLA': '特斯拉',
            'NVDA': '英伟达',
            # ...
        }
        return us_stock_names.get(ticker.upper(), f"美股{ticker}")
    
    return f"股票{ticker}"
```

### 3. 市场信息（market_name, currency_name, currency_symbol）

```python
def get_market_info(ticker: str) -> Dict:
    market = identify_stock_market(ticker)  # 识别市场类型
    
    market_names = {
        StockMarket.CHINA_A: "中国A股",
        StockMarket.HONG_KONG: "港股",
        StockMarket.US: "美股",
    }
    
    currency_map = {
        StockMarket.CHINA_A: ("人民币", "¥"),
        StockMarket.HONG_KONG: ("港币", "HK$"),
        StockMarket.US: ("美元", "$"),
    }
    
    currency_name, currency_symbol = currency_map[market]
    
    return {
        "market_name": market_names[market],
        "currency_name": currency_name,
        "currency_symbol": currency_symbol,
        "is_china": market == StockMarket.CHINA_A,
        "is_hk": market == StockMarket.HONG_KONG,
        "is_us": market == StockMarket.US
    }
```

### 4. 日期（current_date, start_date）

```python
# 当前日期：从工作流状态获取
current_date = state.get("trade_date") or state.get("analysis_date")

# 开始日期：通常是1年前
from datetime import datetime, timedelta
start_date = (datetime.strptime(current_date, "%Y-%m-%d") - timedelta(days=365)).strftime("%Y-%m-%d")
```

---

## ⚠️ 重要说明

### 1. Agent 输入参数 ≠ 模板变量

**Agent 输入参数**（在界面上显示的）：
- `ticker` - 股票代码
- `analysis_date` - 分析日期

**模板变量**（提示词中使用的）：
- `ticker`, `company_name`, `market_name`, `current_date`, `currency_name`, `currency_symbol`, `tool_names`

**关系**：
- Agent 输入参数是工作流传递给 Agent 的数据
- 模板变量是 Agent 内部从状态中提取和计算出来的

### 2. 变量是自动填充的

用户**不需要**手动提供这些变量：
- ✅ `company_name` - 系统自动查询
- ✅ `market_name` - 系统自动识别
- ✅ `currency_name` - 系统自动匹配
- ✅ `tool_names` - 系统自动获取绑定的工具

用户**只需要**提供：
- ✅ `ticker` - 股票代码
- ✅ `analysis_date` - 分析日期（可选，默认今天）

---

## 💡 界面显示建议

### 问题：用户如何知道有哪些变量可用？

**解决方案**：在提示词编辑界面添加"可用变量"提示

#### 方案 1: 在提示词模板下方显示

```
┌─────────────────────────────────────────┐
│ 系统提示词                               │
│ ┌─────────────────────────────────────┐ │
│ │ 你是一位{company_name}的分析师...    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ ℹ️ 可用变量:                            │
│ • {ticker} - 股票代码                   │
│ • {company_name} - 公司名称（自动获取） │
│ • {market_name} - 市场名称（自动识别）  │
│ • {current_date} - 当前日期             │
│ • {currency_name} - 货币名称            │
│ • {currency_symbol} - 货币符号          │
│ • {tool_names} - 可用工具列表           │
└─────────────────────────────────────────┘
```

#### 方案 2: 使用折叠面板

```vue
<el-collapse>
  <el-collapse-item title="📝 可用变量说明" name="variables">
    <el-descriptions :column="2" border size="small">
      <el-descriptions-item label="ticker">
        股票代码（来自输入参数）
      </el-descriptions-item>
      <el-descriptions-item label="company_name">
        公司名称（系统自动获取）
      </el-descriptions-item>
      <el-descriptions-item label="market_name">
        市场名称（系统自动识别）
      </el-descriptions-item>
      <!-- ... 更多变量 -->
    </el-descriptions>
  </el-collapse-item>
</el-collapse>
```

#### 方案 3: 使用工具提示

在输入框旁边添加一个帮助图标：

```vue
<el-tooltip placement="right" width="300">
  <template #content>
    <div style="line-height: 1.8;">
      <strong>可用变量：</strong><br>
      • <code>{ticker}</code> - 股票代码<br>
      • <code>{company_name}</code> - 公司名称（自动获取）<br>
      • <code>{market_name}</code> - 市场名称（自动识别）<br>
      • <code>{current_date}</code> - 当前日期<br>
      • <code>{currency_name}</code> - 货币名称<br>
      • <code>{currency_symbol}</code> - 货币符号<br>
      • <code>{tool_names}</code> - 可用工具列表
    </div>
  </template>
  <el-icon><QuestionFilled /></el-icon>
</el-tooltip>
```

---

## 🔧 代码实现位置

### 变量提取逻辑

| Agent 类型 | 文件位置 | 函数 |
|-----------|---------|------|
| 基本面分析师 | `tradingagents/agents/analysts/fundamentals_analyst.py` | `execute()` |
| 市场分析师 | `tradingagents/agents/analysts/market_analyst.py` | `execute()` |
| 新闻分析师 | `tradingagents/agents/analysts/news_analyst.py` | `execute()` |
| 持仓分析 | `core/agents/adapters/position/fundamental_analyst_v2.py` | `_build_system_prompt()` |

### 工具函数

| 功能 | 文件位置 | 函数 |
|------|---------|------|
| 市场信息 | `tradingagents/utils/stock_utils.py` | `StockUtils.get_market_info()` |
| 公司名称 | `tradingagents/dataflows/interface.py` | `get_china_stock_info_unified()` |
| 模板渲染 | `tradingagents/utils/template_client.py` | `format_template()` |

---

## 📚 相关文档

- [工具名称 vs 工具 ID](./TOOL_NAME_VS_TOOL_ID.md)
- [多工具调用指导](./MULTI_TOOL_GUIDANCE.md)
- [Agent 工具配置显示](../frontend/AGENT_TOOL_CONFIG_DISPLAY.md)

---

**最后更新**: 2026-01-09
**版本**: v1.0.1

