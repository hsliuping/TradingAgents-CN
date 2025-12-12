# 新闻分析工具链和提示词系统

本文档详细介绍了TradingAgentsCN系统中的新闻分析工具链架构、提示词设计和实现机制。

## 1. 新闻分析工具链架构

### 1.1 整体架构图

```
新闻分析师 (NewsAnalyst)
    ↓
工具选择器 (根据股票类型和模式)
    ↓
┌─────────────────┬─────────────────┬─────────────────┐
│   A股工具链     │   非A股工具链   │   离线工具链    │
└─────────────────┴─────────────────┴─────────────────┘
    ↓                   ↓                   ↓
实时新闻聚合器 (RealtimeNewsAggregator)
    ↓
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  FinnHub    │ Alpha       │  NewsAPI    │  中文财经   │
│  实时新闻   │ Vantage     │  新闻源     │  新闻源     │
└─────────────┴─────────────┴─────────────┴─────────────┘
    ↓
新闻处理流水线
    ↓
┌─────────────┬─────────────┬─────────────┬─────────────┐
│  去重处理   │  时效性     │  紧急程度   │  相关性     │
│            │  评估       │  评估       │  评分       │
└─────────────┴─────────────┴─────────────┴─────────────┘
    ↓
格式化新闻报告
    ↓
LLM分析 (基于提示词模板)
    ↓
结构化分析报告
```

### 1.2 工具链组件详解

#### 1.2.1 新闻分析师 (NewsAnalyst)

**位置**: `tradingagents/agents/analysts/news_analyst.py`

**核心功能**:
- 智能工具选择（根据股票类型和运行模式）
- 提示词模板管理
- LLM调用和结果处理
- 分析报告生成

**工具选择逻辑**:
```python
# A股工具链
if is_china:
    tools = [
        toolkit.get_realtime_stock_news,  # 实时新闻（包含东方财富）
        toolkit.get_google_news,         # Google新闻（中文搜索）
        toolkit.get_global_news_openai   # OpenAI全球新闻（作为补充）
    ]

# 非A股工具链
else:
    tools = [
        toolkit.get_realtime_stock_news,  # 实时新闻
        toolkit.get_global_news_openai,
        toolkit.get_google_news
    ]

# 离线模式工具链
if not online_tools:
    tools = [
        toolkit.get_realtime_stock_news,  # 尝试实时新闻
        toolkit.get_finnhub_news,
        toolkit.get_reddit_news,
        toolkit.get_google_news,
    ]
```

#### 1.2.2 实时新闻聚合器 (RealtimeNewsAggregator)

**位置**: `tradingagents/dataflows/realtime_news_utils.py`

**核心功能**:
- 多源新闻聚合
- 新闻去重和排序
- 紧急程度评估
- 相关性评分
- 时效性分析

**数据源优先级**:
1. **FinnHub实时新闻** (最高优先级)
2. **Alpha Vantage新闻**
3. **NewsAPI新闻源**
4. **中文财经新闻源**

**新闻项目数据结构**:
```python
@dataclass
class NewsItem:
    title: str              # 新闻标题
    content: str           # 新闻内容
    source: str            # 新闻来源
    publish_time: datetime # 发布时间
    url: str              # 新闻链接
    urgency: str          # 紧急程度 (high, medium, low)
    relevance_score: float # 相关性评分
```

#### 1.2.3 新闻处理流水线

**去重处理**:
- 基于标题相似度的去重算法
- 时间窗口内的重复新闻过滤

**紧急程度评估**:
```python
# 高紧急程度关键词
high_urgency_keywords = [
    "破产", "诉讼", "收购", "合并", "FDA批准", "盈利警告",
    "停牌", "重组", "违规", "调查", "制裁"
]

# 中等紧急程度关键词
medium_urgency_keywords = [
    "财报", "业绩", "合作", "新产品", "市场份额",
    "分红", "回购", "增持", "减持"
]
```

**相关性评分算法**:
- 股票代码匹配度
- 公司名称匹配度
- 行业关键词匹配度
- 内容相关性分析

## 2. 提示词系统设计

### 2.1 系统提示词模板

```python
system_message = """您是一位专业的财经新闻分析师，负责分析最新的市场新闻和事件对股票价格的潜在影响。

您的主要职责包括：
1. 获取和分析最新的实时新闻（优先15-30分钟内的新闻）
2. 评估新闻事件的紧急程度和市场影响
3. 识别可能影响股价的关键信息
4. 分析新闻的时效性和可靠性
5. 提供基于新闻的交易建议和价格影响评估

重点关注的新闻类型：
- 财报发布和业绩指导
- 重大合作和并购消息
- 政策变化和监管动态
- 突发事件和危机管理
- 行业趋势和技术突破
- 管理层变动和战略调整

分析要点：
- 新闻的时效性（发布时间距离现在多久）
- 新闻的可信度（来源权威性）
- 市场影响程度（对股价的潜在影响）
- 投资者情绪变化（正面/负面/中性）
- 与历史类似事件的对比

📊 价格影响分析要求：
- 评估新闻对股价的短期影响（1-3天）
- 分析可能的价格波动幅度（百分比）
- 提供基于新闻的价格调整建议
- 识别关键价格支撑位和阻力位
- 评估新闻对长期投资价值的影响
- 不允许回复'无法评估价格影响'或'需要更多信息'

请特别注意：
⚠️ 如果新闻数据存在滞后（超过2小时），请在分析中明确说明时效性限制
✅ 优先分析最新的、高相关性的新闻事件
📊 提供新闻对股价影响的量化评估和具体价格预期
💰 必须包含基于新闻的价格影响分析和调整建议

请撰写详细的中文分析报告，并在报告末尾附上Markdown表格总结关键发现。"""
```

### 2.2 提示词设计原则

#### 2.2.1 角色定位
- **专业身份**: 财经新闻分析师
- **核心职责**: 新闻分析和价格影响评估
- **专业要求**: 量化分析和具体建议

#### 2.2.2 任务导向
- **主要任务**: 5个核心职责明确定义
- **关注重点**: 6类重要新闻类型
- **分析维度**: 5个关键分析要点

#### 2.2.3 输出要求
- **强制要求**: 价格影响分析（不允许回避）
- **格式要求**: 中文报告 + Markdown表格
- **质量标准**: 详细分析 + 量化评估

#### 2.2.4 约束条件
- **时效性约束**: 优先15-30分钟内新闻
- **可靠性约束**: 评估新闻来源权威性
- **完整性约束**: 必须包含价格影响分析

### 2.3 动态提示词注入

```python
prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "您是一位有用的AI助手，与其他助手协作。"
        " 使用提供的工具来推进回答问题。"
        " 您可以访问以下工具：{tool_names}。\n{system_message}"
        "供您参考，当前日期是{current_date}。我们正在查看公司{ticker}。请用中文撰写所有分析内容。",
    ),
    MessagesPlaceholder(variable_name="messages"),
])

# 动态参数注入
prompt = prompt.partial(system_message=system_message)
prompt = prompt.partial(tool_names=", ".join([tool.name for tool in tools]))
prompt = prompt.partial(current_date=current_date)
prompt = prompt.partial(ticker=ticker)
```

## 3. 工具链执行流程

### 3.1 初始化阶段

```python
def create_news_analyst(llm, toolkit):
    @log_analyst_module("news")
    def news_analyst_node(state):
        # 1. 提取状态信息
        current_date = state["trade_date"]
        ticker = state["company_of_interest"]
        session_id = state.get("session_id", "未知会话")
        
        # 2. 股票类型识别
        market_info = StockUtils.get_market_info(ticker)
        is_china = market_info['is_china']
        
        # 3. 工具选择
        tools = select_tools_by_market(is_china, toolkit.config["online_tools"])
        
        # 4. 提示词构建
        prompt = build_prompt_template(system_message, tools, current_date, ticker)
```

### 3.2 新闻获取阶段

```python
def get_realtime_stock_news(ticker: str, hours_back: int = 6):
    # 1. 多源新闻获取
    finnhub_news = _get_finnhub_realtime_news(ticker, hours_back)
    av_news = _get_alpha_vantage_news(ticker, hours_back)
    newsapi_news = _get_newsapi_news(ticker, hours_back)
    chinese_news = _get_chinese_finance_news(ticker, hours_back)
    
    # 2. 新闻聚合
    all_news = finnhub_news + av_news + newsapi_news + chinese_news
    
    # 3. 去重和排序
    unique_news = _deduplicate_news(all_news)
    sorted_news = sorted(unique_news, key=lambda x: x.publish_time, reverse=True)
    
    # 4. 格式化报告
    report = format_news_report(sorted_news, ticker)
    
    return report
```

### 3.3 LLM分析阶段

```python
def analyze_news_with_llm(llm, prompt, tools, state):
    # 1. 工具绑定
    chain = prompt | llm.bind_tools(tools)
    
    # 2. LLM调用
    result = chain.invoke(state["messages"])
    
    # 3. 工具调用处理
    if hasattr(result, 'tool_calls') and len(result.tool_calls) > 0:
        # 处理工具调用结果
        tool_results = process_tool_calls(result.tool_calls)
        report = generate_analysis_report(tool_results)
    else:
        # 直接使用LLM生成的内容
        report = result.content
    
    return report
```

### 3.4 报告生成阶段

```python
def format_news_report(news_items: List[NewsItem], ticker: str) -> str:
    report = f"# {ticker} 实时新闻分析报告\n\n"
    report += f"📅 **生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    report += f"📊 **新闻总数**: {len(news_items)} 条\n\n"
    
    # 紧急新闻优先显示
    urgent_news = [item for item in news_items if item.urgency == 'high']
    if urgent_news:
        report += "## 🚨 紧急新闻\n\n"
        for item in urgent_news:
            report += format_news_item(item)
    
    # 一般新闻
    normal_news = [item for item in news_items if item.urgency != 'high']
    if normal_news:
        report += "## 📰 最新新闻\n\n"
        for item in normal_news[:10]:  # 限制显示数量
            report += format_news_item(item)
    
    return report
```

## 4. 关键特性和优势

### 4.1 智能工具选择
- **股票类型识别**: 自动识别A股、港股、美股
- **数据源优化**: A股优先中文新闻源，美股优先英文新闻源
- **模式适配**: 在线/离线模式自动切换

### 4.2 多源新闻聚合
- **专业API**: FinnHub、Alpha Vantage提供高质量金融新闻
- **通用API**: NewsAPI提供广泛新闻覆盖
- **本地化**: 中文财经新闻源支持A股分析

### 4.3 智能新闻处理
- **去重算法**: 基于内容相似度的智能去重
- **紧急程度评估**: 关键词匹配 + 内容分析
- **相关性评分**: 多维度相关性计算
- **时效性分析**: 新闻发布时间与当前时间对比

### 4.4 强化提示词设计
- **角色明确**: 专业财经新闻分析师定位
- **任务具体**: 5大职责 + 6类新闻类型
- **输出标准**: 强制价格影响分析
- **质量保证**: 详细分析 + 量化评估

### 4.5 完整的日志追踪
- **性能监控**: 每个步骤的耗时统计
- **工具使用**: 工具调用情况记录
- **数据质量**: 新闻数量和质量统计
- **错误处理**: 异常情况的详细记录

## 5. 使用示例

### 5.1 基本使用

```python
from tradingagents.agents.analysts.news_analyst import create_news_analyst
from tradingagents.agents.utils.agent_utils import Toolkit
from tradingagents.llm_adapters import ChatDashScope

# 创建LLM和工具包
llm = ChatDashScope()
toolkit = Toolkit()

# 创建新闻分析师
news_analyst = create_news_analyst(llm, toolkit)

# 执行分析
state = {
    "trade_date": "2024-01-15",
    "company_of_interest": "AAPL",
    "messages": [],
    "session_id": "test_session"
}

result = news_analyst(state)
print(result["news_report"])
```

### 5.2 自定义配置

```python
# 自定义新闻聚合器
from tradingagents.dataflows.realtime_news_utils import RealtimeNewsAggregator

aggregator = RealtimeNewsAggregator()

# 自定义紧急程度关键词
aggregator.high_urgency_keywords = ["破产", "收购", "FDA批准"]
aggregator.medium_urgency_keywords = ["财报", "合作", "新产品"]

# 获取新闻
news_items = aggregator.get_realtime_stock_news("AAPL", hours_back=12)
report = aggregator.format_news_report(news_items, "AAPL")
```

## 6. 配置要求

### 6.1 API密钥配置

```bash
# .env 文件配置
FINNHUB_API_KEY=your_finnhub_key
ALPHA_VANTAGE_API_KEY=your_alpha_vantage_key
NEWSAPI_KEY=your_newsapi_key
```

### 6.2 依赖包要求

```python
# requirements.txt
requests>=2.28.0
langchain-core>=0.1.0
akshare>=1.9.0  # 用于东方财富新闻
```

## 7. 性能优化

### 7.1 缓存机制
- **新闻缓存**: 避免重复API调用
- **分析缓存**: 相同股票的分析结果缓存
- **工具结果缓存**: 工具调用结果缓存

### 7.2 并发处理
- **多源并发**: 多个新闻源并发获取
- **异步处理**: 非阻塞的新闻获取
- **超时控制**: 避免长时间等待

### 7.3 错误处理
- **降级策略**: API失败时的备用方案
- **重试机制**: 网络错误的自动重试
- **异常捕获**: 完整的异常处理机制

## 8. 扩展性设计

### 8.1 新数据源接入
- **标准接口**: 统一的新闻源接入接口
- **插件化**: 新数据源的插件化集成
- **配置化**: 通过配置文件管理数据源

### 8.2 分析能力扩展
- **情感分析**: 新闻情感倾向分析
- **事件提取**: 关键事件的自动提取
- **影响预测**: 基于历史数据的影响预测

### 8.3 多语言支持
- **中英文**: 中英文新闻的统一处理
- **本地化**: 不同市场的本地化支持
- **翻译集成**: 自动翻译功能集成

这个新闻分析工具链和提示词系统为TradingAgentsCN提供了强大的新闻分析能力，能够实时获取、处理和分析市场新闻，为投资决策提供重要参考。