# 新增 Agent v2.0

## 📝 概述

本文档说明新增的两个后处理 Agent：
1. **ReportGeneratorV2** - 报告生成器 v2
2. **DataPreparerV2** - 数据准备器 v2

---

## 1. ReportGeneratorV2 - 报告生成器 v2

### 📋 基本信息

- **ID**: `report_generator_v2`
- **名称**: 报告生成器 v2
- **类别**: POST_PROCESSOR
- **版本**: 2.0.0
- **图标**: 📝
- **颜色**: #9b59b6

### 🎯 功能

从各分析师输出中提取关键信息，生成结构化的综合分析报告。

**特点**:
- ✅ 不调用LLM，纯数据处理
- ✅ 自动提取所有报告字段
- ✅ 生成结构化报告
- ✅ 支持JSON和Markdown格式
- ✅ 生成摘要信息

### 📥 输入

从工作流状态中提取以下报告字段：

**宏观分析**:
- `index_report` - 大盘分析报告
- `sector_report` - 板块分析报告

**个股分析**:
- `market_report` - 市场分析报告
- `sentiment_report` - 情绪分析报告
- `news_report` - 新闻分析报告
- `fundamentals_report` - 基本面分析报告

**研究员报告**:
- `bull_report` - 看涨观点
- `bear_report` - 看跌观点

**投资计划**:
- `investment_plan` - 投资计划
- `trader_investment_plan` - 交易计划
- `final_trade_decision` - 最终决策

**风险评估**:
- `risk_assessment` - 风险评估

### 📤 输出

- `generated_reports` - 提取的报告字典
- `structured_reports` - 结构化报告字典
- `report_summary` - 摘要信息

### 💻 使用示例

```python
from core.agents import create_agent

# 创建报告生成器
agent = create_agent("report_generator_v2")

# 执行
result = agent.execute({
    "ticker": "000001",
    "market_report": "市场分析报告内容...",
    "fundamentals_report": "基本面分析报告内容...",
    "bull_report": "看涨观点...",
    "bear_report": "看跌观点...",
})

# 查看结果
print(f"提取报告数: {len(result['generated_reports'])}")
print(f"结构化报告数: {len(result['structured_reports'])}")
print(f"摘要信息: {result['report_summary']}")
```

### 🔧 工作流程

1. 从状态中提取所有报告字段
2. 提取文本内容（支持字符串、字典等格式）
3. 生成结构化报告（JSON → Markdown）
4. 生成摘要信息
5. 更新状态并返回

---

## 2. DataPreparerV2 - 数据准备器 v2

### 📋 基本信息

- **ID**: `data_preparer_v2`
- **名称**: 数据准备器 v2
- **类别**: ANALYST（智能分析师）
- **版本**: 2.0.0
- **图标**: 🔧
- **颜色**: #3498db

### 🎯 功能

**智能数据准备 Agent**，通过 LLM 理解需求并调用工具获取数据。

**核心特点**:
- 🤖 **调用 LLM** - 理解数据准备需求
- 🔧 **绑定工具** - 使用所有技能化的工具（market, fundamentals, news, social）
- 🎯 **智能选择** - 根据提示词决定调用哪些工具
- 📦 **存储上下文** - 将数据放在 `context` 中供后续 Agent 使用
- 🔗 **灵活性高** - 后续 Agent 可以从 `context` 读取数据

### 📥 输入

- `ticker` (必需) - 股票代码
- `analysis_date` (可选) - 分析日期
- `data_requirements` (可选) - 数据需求描述

### 📤 输出

- `context` - 准备好的数据上下文（Markdown 格式）
- `data_summary` - 数据摘要
- `tools_used` - 使用的工具列表

### 💻 使用示例

```python
from core.agents import create_agent
from core.llm import UnifiedLLMClient

# 创建 LLM 客户端
llm = UnifiedLLMClient(provider="openai", model="gpt-4")

# 创建数据准备器
agent = create_agent("data_preparer_v2", llm=llm)

# 执行 - 方式 1：指定数据需求
result = agent.execute({
    "ticker": "000001",
    "analysis_date": "2026-02-19",
    "data_requirements": """
    需要准备：
    1. 股票基本信息
    2. 最近30天行情
    3. 最新财务数据
    4. 近期新闻
    """
})

# 执行 - 方式 2：使用默认需求
result = agent.execute({
    "ticker": "000001",
    "analysis_date": "2026-02-19"
})

# 查看结果
print(f"数据上下文:\n{result['context']}")
print(f"数据摘要: {result['data_summary']}")
print(f"使用的工具: {result['tools_used']}")
```

### 🔧 工作流程

1. **理解需求** - LLM 分析 `data_requirements` 或使用默认需求
2. **选择工具** - 智能决定需要调用哪些工具
3. **调用工具** - 依次调用 market、fundamentals、news、social 等工具
4. **整理数据** - 将工具返回的数据整理成结构化格式
5. **生成上下文** - 以 Markdown 格式生成数据上下文
6. **存储结果** - 将上下文存储在 `context` 字段中

### 🛠️ 可用工具

- **market** - 获取市场行情数据（价格、成交量、涨跌幅等）
- **fundamentals** - 获取财务数据（财报、估值指标等）
- **news** - 获取新闻资讯
- **social** - 获取社交媒体情绪

### 📊 输出格式示例

```markdown
# 数据准备报告

## 基本信息
- 股票代码: 000001
- 公司名称: 平安银行
- 所属行业: 银行

## 市场数据
- 当前价格: 12.50元
- 涨跌幅: +2.5%
- 成交量: 1000万股

## 财务数据
- 市盈率: 5.2
- 市净率: 0.8
- ROE: 12%

## 近期新闻
- [2026-02-19] 平安银行发布年报...
- [2026-02-18] 平安银行获评...
```

---

## 🚀 在工作流中使用

### 示例 1: 完整分析流程

```
start → data_preparer_v2 → market_analyst_v2 → fundamentals_analyst_v2 → report_generator_v2 → end
```

**说明**:
1. `data_preparer_v2` 准备股票基础数据
2. 分析师使用准备好的数据进行分析
3. `report_generator_v2` 汇总所有分析报告
4. 返回结构化的综合报告

### 示例 2: 简化流程（只有分析师）

```
start → market_analyst_v2 → fundamentals_analyst_v2 → report_generator_v2 → end
```

**说明**:
- 不使用 `data_preparer_v2`，分析师自行获取数据
- `report_generator_v2` 提取分析师报告
- 适合快速分析场景

---

## 📁 文件位置

- **ReportGeneratorV2**: `core/agents/post_processors/report_generator_v2.py`
- **DataPreparerV2**: `core/agents/post_processors/data_preparer_v2.py`
- **配置**: `core/agents/config.py` (BUILTIN_AGENTS)
- **导出**: `core/agents/post_processors/__init__.py`
- **注册**: `core/agents/__init__.py`

---

## ✅ 测试

运行测试脚本验证 Agent 是否正常工作：

```bash
python tests/test_new_agents.py
```

---

**创建日期**: 2026-02-19  
**版本**: 1.0.0  
**作者**: TradingAgents-CN Pro Team

