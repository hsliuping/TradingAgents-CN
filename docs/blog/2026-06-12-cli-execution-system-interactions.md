# `python3 -m cli.main` 执行时的系统交互全解析

**日期**: 2026-06-12  
**作者**: TradingAgents-CN 开发团队  
**标签**: `CLI` `LangGraph` `系统交互` `执行流程` `数据流`  

---

## 📋 概述

本文档细致拆解当用户在 `~/projects/TradingAgents-CN` 目录下执行
`python3 -m cli.main` 后，程序在操作系统、文件系统、本地/远程服务、LLM 网关、
数据源 API 之间发生的真实交互。理解这些交互有助于：

- 排查"卡住"或超时类问题
- 优化 token/数据缓存命中
- 评估离线/在线运行模式
- 编写自动化运维脚本

整条流程可拆为 **5 个阶段**：

1. **进程启动与日志初始化**（本地进程 + 配置文件）
2. **交互式问卷与参数采集**（stdin/stdout，无网络）
3. **数据预获取与验证**（API Key 校验 + 数据源拉取 + 落盘缓存）
4. **LangGraph 多智能体编排**（LLM 推理 + 工具调用 + 状态流转）
5. **报告落盘与信号处理**（本地文件 + MongoDB 可选）

---

## 🗺️ 总体交互时序图

```
                 ┌──────────────────────────────────────────┐
                 │  Python 3.x 解释器                        │
                 │  ├─ load_dotenv()  读 .env               │
                 │  ├─ setup_cli_logging()  移除 console     │
                 │  └─ typer CLI 启动                        │
                 └────────────┬─────────────────────────────┘
                              │ stdin/stdout
                 ┌────────────▼─────────────────────────────┐
                 │  get_user_selections()  7 步问卷          │
                 │  市场/代码/日期/分析师/深度/LLM/思考模型   │
                 └────────────┬─────────────────────────────┘
                              │
        ┌─────────────────────▼──────────────────────┐
        │  check_api_keys()   校验本地 .env            │
        │  缺 key 则 logger.error 打印后退出          │
        └─────────────────────┬──────────────────────┘
                              │
        ┌─────────────────────▼──────────────────────────┐
        │  TradingAgentsGraph.__init__()                  │
        │  ├─ 创建 quick/deep_thinking_llm  LLM 客户端    │
        │  ├─ 实例化 Toolkit (工具注册表)                │
        │  ├─ 创建 5 个 FinancialSituationMemory  (Chroma)│
        │  ├─ 创建 4 个 ToolNode  (market/social/news/..)│
        │  ├─ GraphSetup.setup_graph()  编译 LangGraph   │
        │  └─ 创建 results_dir  /  report_dir / log_file │
        └─────────────────────┬──────────────────────────┘
                              │
        ┌─────────────────────▼──────────────────────────┐
        │  prepare_stock_data()  数据预获取                │
        │  ├─ MongoDB 查询   (本地)                       │
        │  ├─ BaoStock HTTP  (本地 8086 或公网)           │
        │  ├─ AKShare HTTP   (公网)                       │
        │  ├─ Tushare HTTP   (公网)                       │
        │  └─ 写入 data_cache/*.json / *.pkl              │
        └─────────────────────┬──────────────────────────┘
                              │
        ┌─────────────────────▼──────────────────────────┐
        │  graph.stream(init_agent_state, ...)  流式执行  │
        │  ┌──────────────────────────────────────┐      │
        │  │  Analyst Team  (4个分析师)            │      │
        │  │  →  LLM 推理 + 工具调用 循环          │      │
        │  └──────────────────────────────────────┘      │
        │  ┌──────────────────────────────────────┐      │
        │  │  Research Team  (Bull vs Bear 辩论)   │      │
        │  │  →  LLM 推理 循环 max_debate_rounds   │      │
        │  └──────────────────────────────────────┘      │
        │  ┌──────────────────────────────────────┐      │
        │  │  Trader  (出交易计划)                │      │
        │  └──────────────────────────────────────┘      │
        │  ┌──────────────────────────────────────┐      │
        │  │  Risk Team  (Risky/Neutral/Safe 辩论) │      │
        │  │  →  LLM 推理 循环 max_risk_rounds    │      │
        │  └──────────────────────────────────────┘      │
        │  ┌──────────────────────────────────────┐      │
        │  │  Portfolio Manager  (最终决策)         │      │
        │  └──────────────────────────────────────┘      │
        │  每节点完成 → chunk → message_buffer            │
        │  → save_message_decorator 写 message_tool.log │
        │  → save_report_section_decorator 写 *.md 报告  │
        └─────────────────────┬──────────────────────────┘
                              │
        ┌─────────────────────▼──────────────────────────┐
        │  SignalProcessor.process_signal()              │
        │  → 抽取 BUY/SELL/HOLD 信号                     │
        │  → display_complete_report()  控制台展示       │
        │  → 写 final_trade_decision.md                   │
        └────────────────────────────────────────────────┘
```

---

## 阶段 1：进程启动与日志初始化

### 1.1 Python 解释器启动

| 项目 | 内容 |
|:---|:---|
| 入口命令 | `python3 -m cli.main` |
| 工作目录 | `~/projects/TradingAgents-CN` |
| 触发文件 | [cli/main.py](file:///Users/lishinho/projects/TradingAgents-CN/cli/main.py) |
| Python 行为 | 查找 `sys.path` 中的 `cli` 包 → 找到 `cli/__init__.py` → 加载 `cli/main.py` 模块 |

### 1.2 模块导入级联

`cli/main.py` 顶部会触发一连串 import（按依赖顺序）：

| 导入 | 触发的副作用 |
|:---|:---|
| `dotenv.load_dotenv()` | 读 `.env` 文件 → 设置进程环境变量 `DASHSCOPE_API_KEY`、`DEEPSEEK_API_KEY` 等 |
| `tradingagents.default_config.DEFAULT_CONFIG` | 加载默认配置（deep_think_llm、quick_think_llm、max_debate_rounds 等） |
| `tradingagents.graph.trading_graph.TradingAgentsGraph` | 间接触发 `tradingagents.llm_clients.factory` 导入 |
| `tradingagents.utils.logging_manager.get_logger` | 初始化日志系统（写 `logs/` 目录） |

> ⚠️ 这一阶段 **不会有任何网络请求**。所有 I/O 都发生在本地磁盘。

### 1.3 日志系统重写

`setup_cli_logging()` 主动移除所有 `<stderr>` / `<stdout>` StreamHandler：

```python
# cli/main.py:53-66
for handler in root_logger.handlers[:]:
    if isinstance(handler, logging.StreamHandler) and hasattr(handler, 'stream'):
        if handler.stream.name in ['<stderr>', '<stdout>']:
            root_logger.removeHandler(handler)
```

> **副作用**：之后所有 `logger.info()` 都只写文件，不再污染 Rich 终端界面。

### 1.4 文件系统初始化

- `cli/static/welcome.txt` 读取（ASCII 艺术字横幅）
- **不创建**结果目录（推迟到第 4 阶段）

---

## 阶段 2：交互式问卷与参数采集

### 2.1 7 步问答

`get_user_selections()` 通过 [rich](https://github.com/Textualize/rich) + typer 完成 7 步对话：

| 步骤 | 提示 | 默认值 | 校验 |
|:---:|:---|:---|:---|
| 1 | 选择市场（1=美股 / 2=A股 / 3=港股） | `2` | 必须 ∈ {1,2,3} |
| 2 | 输入股票代码 | `600036` | 正则 `^\d{6}$`（A股） |
| 3 | 输入分析日期 | 今天 | 必须 ≤ 今天 |
| 4 | 选分析师（多选） | 4 个全选 | 枚举校验 |
| 5 | 选研究深度 | `1` | 1/3/5 |
| 6 | 选 LLM Provider | 来自 `.env` 默认 | 枚举 |
| 7 | 选 quick/deep 模型 | 与 Provider 相关 | 枚举 |

> 全部通过 `typer.prompt()` 走 **stdin** 读入。**不发起任何网络请求**。

### 2.2 API Key 校验

`check_api_keys()` 读取进程环境变量：

```python
# cli/main.py:978-1014
if provider in {"qwen", "dashscope"}:
    if not os.getenv("DASHSCOPE_API_KEY"):
        missing_keys.append("DASHSCOPE_API_KEY (阿里百炼)")
# ... 其他 provider
```

- **缺关键 Key** → `ui.show_error()` + `return` 直接退出，不进入第 3 阶段
- **缺少 `FINNHUB_API_KEY`** → 仅 `logger.warning()`，**不阻塞**（因为 A 股分析用不到）

---

## 阶段 3：数据预获取与验证

### 3.1 `TradingAgentsGraph.__init__()`

这是最重的一步。完整调用链：

```
TradingAgentsGraph.__init__()
  ├─ set_config(self.config)              # 更新 dataflows.interface 全局 config
  ├─ os.makedirs("dataflows/data_cache")  # 创建缓存目录
  │
  ├─ _create_provider_pair(...)           # ⭐ 真正发起 LLM 连接的步骤
  │    └─ create_llm_client(provider=...) 
  │         └─ 各厂商适配器：DashScope / OpenAI / DeepSeek / GLM ...
  │              ├─ 读 API Key (env 或 db)
  │              ├─ 构造 base_url
  │              └─ ChatOpenAI(...) 实例化
  │                  ⚠️ 此刻 ChatOpenAI 不会真的连接，
  │                  只在第一次 .invoke() 时连接
  │
  ├─ self.toolkit = Toolkit(config=...)   # 注册所有工具方法
  │
  ├─ self.bull_memory = FinancialSituationMemory("bull_memory", config)
  │    └─ ChromaDB  持久化目录：./chroma_db/bull_memory/
  │    └─ 首次启动会下载 Embedding 模型（如 BAAI/bge-small-zh-v1.5）
  │       → 走 HF Hub 下载或本地缓存
  │
  ├─ self.tool_nodes = self._create_tool_nodes()  
  │    └─ {market, social, news, fundamentals} = {ToolNode(...)}
  │    └─ 此刻不发起网络，只是包装工具函数
  │
  ├─ ConditionalLogic(max_debate_rounds, max_risk_discuss_rounds)
  │
  ├─ GraphSetup.setup_graph(selected_analysts)  
  │    └─ 创建 4 套分析师节点 + 1 套研究员节点 + 1 套风控节点
  │    └─ StateGraph(AgentState) → 编译成可执行图
  │    └─ 返回 self.graph  (LangGraph CompiledStateGraph)
  │
  └─ Propagator / Reflector / SignalProcessor 实例化
```

### 3.2 第一次磁盘写入

```python
# cli/main.py:1099-1104
results_dir = Path(config["results_dir"]) / ticker / analysis_date
results_dir.mkdir(parents=True, exist_ok=True)  # ← 创建 results/600036/2026-06-12/
report_dir = results_dir / "reports"
report_dir.mkdir(parents=True, exist_ok=True)    # ← 创建 reports/ 子目录
log_file = results_dir / "message_tool.log"
log_file.touch(exist_ok=True)                    # ← 创建空日志文件
```

### 3.3 Decorator 替换（关键）

`message_buffer` 的 3 个方法被替换为带"文件落盘副作用"的版本：

```python
# cli/main.py:1106-1133
message_buffer.add_message = save_message_decorator(...)
message_buffer.add_tool_call = save_tool_call_decorator(...)
message_buffer.update_report_section = save_report_section_decorator(...)
```

**这就是为什么后面每条 LLM 回复/工具调用都会** **自动写日志/写报告**——是装饰器在背后做的。

### 3.4 数据预获取 `prepare_stock_data()`

```python
# cli/main.py:1198-1220
from tradingagents.utils.stock_validator import prepare_stock_data

preparation_result = prepare_stock_data(
    stock_code="600036",
    market_type="A股",
    period_days=30,
    analysis_date="2026-06-12"
)
```

| 数据源 | 行为 | 失败时 |
|:---|:---|:---|
| MongoDB | `find({"symbol": "600036", "date": ...})` | 缓存未命中则降级 |
| BaoStock SDK | `bs.query_history_k_data_plus(...)` | `bs.logout()` 后捕获 |
| AKShare | `ak.stock_zh_a_hist(...)` | 走 Tushare |
| Tushare | `pro.daily(...)` | 返回 `is_valid=False` |

返回 `StockPreparationResult` 含：

- `stock_name`: 股票中文名
- `market_type`: "A股"
- `cache_status`: "HIT" / "MISS"
- `is_valid`: bool

> **如果预获取失败**，CLI 直接 `return` 退出，不进入第 4 阶段。

---

## 阶段 4：LangGraph 多智能体编排（最重）

### 4.1 状态初始化

```python
# cli/main.py:1231
init_agent_state = graph.propagator.create_initial_state(ticker, analysis_date)
args = graph.propagator.get_graph_args()
```

`AgentState`（[agent_states.py](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/agents/utils/agent_states.py)）的初始字段：

| 字段 | 初始值 |
|:---|:---|
| `messages` | `[SystemMessage(...)]`（任务提示） |
| `company_of_interest` | `"600036"` |
| `trade_date` | `"2026-06-12"` |
| `market_report` | `""` |
| `fundamentals_report` | `""` |
| `investment_debate_state` | `InvestDebateState(...)` |
| `risk_debate_state` | `RiskDebateState(...)` |

### 4.2 图结构（LangGraph）

`GraphSetup.setup_graph()` 创建的有向图：

```
START
  │
  ▼
Market Analyst ──[should_continue_market]──► tools_market ──► Market Analyst
  │                                              │
  │  (无 tool_calls 或报告已生成)                 │
  ▼                                              │
Msg Clear Market                                  │
  │                                              │
  ▼                                              │
Social Analyst ──[should_continue_social]──► tools_social ──► Social Analyst
  │
  ▼
News Analyst ──[should_continue_news]──► tools_news
  │
  ▼
Fundamentals Analyst ──[should_continue_fundamentals]──► tools_fundamentals
  │
  ▼
Bull Researcher ──[should_continue_debate]──┐
  │                                          │
  ▼                                          │
Bear Researcher ──[should_continue_debate]──┤
  │                                          │
  ▼                                          │
Research Manager                             │
  │                                          │
  ▼                                          │
Trader                                       │
  │                                          │
  ▼                                          │
Risky Analyst ──[should_continue_risk_analysis]──┐
  │                                              │
  ▼                                              │
Safe Analyst ──[should_continue_risk_analysis]───┤
  │                                              │
  ▼                                              │
Neutral Analyst ──[should_continue_risk_analysis]
  │
  ▼
Risk Judge
  │
  ▼
END
```

**条件边函数**：每个分析师都有 `should_continue_xxx()` 检查 `tool_call_count`（最大 3 次）和 `report` 长度，避免死循环。

### 4.3 流式执行主循环

```python
# cli/main.py:1267-1268
for chunk in graph.graph.stream(init_agent_state, **args):
    if len(chunk["messages"]) > 0:
        last_message = chunk["messages"][-1]
        # ... 提取 content / tool_calls
        message_buffer.add_message(msg_type, content)  # 装饰器自动写日志
        # ... 更新报告段
        message_buffer.update_report_section(...)  # 装饰器自动写 .md
        update_display(layout)  # 刷新 Rich Live 界面
```

每次 `chunk` 都来自 LangGraph 的 `updates` 流，结构示例：

```python
{
    "Market Analyst": {
        "messages": [AIMessage(content="...", tool_calls=[...])],
        "market_report": "### Market Analysis\n..."  # 由节点最后输出
    }
}
```

### 4.4 一次 LLM 调用的真实网络交互

以 **Market Analyst** 第一次循环为例：

```
┌─────────────────────────────────────────┐
│  1. 节点函数 market_analyst_node(state)   │
│     - 构造 LLM Prompt (SystemMessage +  │
│       工具 schema)                       │
│     - 调 self.quick_thinking_llm.invoke  │
│       (实为 ChatOpenAI 等客户端)         │
└──────────────────┬──────────────────────┘
                   │ HTTPS POST
                   ▼
        ┌──────────────────────┐
        │  LLM API 网关          │
        │  (DashScope / DeepSeek│
        │   / OpenAI / GLM ...)  │
        │  → 鉴权 → 计费 → 推理 │
        └──────────┬───────────┘
                   │ 200 OK + Stream
                   ▼
        ┌──────────────────────┐
        │  返回 AIMessage:       │
        │  - content (str)       │
        │  - tool_calls (list)   │
        │  - additional_kwargs   │
        └──────────┬───────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  2. should_continue_market()             │
│     - 检查 last_message.tool_calls        │
│     - 有 tool_call → 路由到 tools_market │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  3. ToolNode.tools_market (并行执行)     │
│     ├─ get_stock_market_data_unified     │
│     │   → 数据源 API (BaoStock/AKShare)   │
│     │   → 写缓存 dataflows/data_cache/... │
│     └─ get_stockstats_indicators_report   │
│         → BaoStock 实时指标                │
│  返回 ToolMessage(content="...")         │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────┐
│  4. 回到 Market Analyst 节点              │
│     - state.messages 追加 ToolMessage     │
│     - 第二次 invoke LLM，让它总结         │
│     - 最终在节点末尾写 market_report     │
└─────────────────────────────────────────┘
```

### 4.4.1 工具调用详细协议：`get_stockstats_indicators_report`

> 这一节是文档原第 424-425 行的展开，剖析工具的完整协议栈。

#### 协议栈总览

```
LLM 推理输出 tool_call
    ↓ JSON 序列化
LangGraph ToolNode 调度
    ↓ 函数调用
Toolkit.get_stockstats_indicators_report()
    ↓ 接口层
dataflows.interface.get_stock_stats_indicators_window()
    ↓ 指标计算器
StockstatsUtils.get_stock_stats()
    ↓ 数据源
yf.download()  (yfinance)  ← 实际是美股数据源！
    ↓
CSV 缓存 + stockstats 库计算
    ↓
返回字符串给 LLM
```

#### 4.4.1.1 协议层 1：LLM → ToolNode（OpenAI Function Calling 协议）

LLM 网关返回的 `AIMessage` 中 `tool_calls` 字段是标准 [OpenAI Function Calling](https://platform.openai.com/docs/guides/function-calling) 格式：

```json
{
  "id": "call_abc123",
  "type": "function",
  "function": {
    "name": "get_stockstats_indicators_report",
    "arguments": "{\"symbol\": \"600036\", \"indicator\": \"rsi\", \"curr_date\": \"2026-06-12\", \"look_back_days\": 30}"
  }
}
```

> LLM 怎么知道参数 schema？看 [agent_utils.py:281-308](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/agents/utils/agent_utils.py#L281-L308)：
> `@tool` 装饰器把 `Annotated[type, "描述"]` 转换为 JSON Schema 写入 `tools` 字段，
> 随 ChatCompletion 请求一起发给 LLM。

#### 4.4.1.2 协议层 2：ToolNode → Toolkit

LangGraph 内部用 LangChain 的 `Tool` 抽象：

```python
# 节点绑定
self.toolkit = Toolkit(config=...)
tools_market = ToolNode([toolkit.get_stock_market_data_unified, toolkit.get_stockstats_indicators_report])
```

ToolNode 在执行时：

1. 遍历 `last_message.tool_calls`
2. 按 `name` 字段查找 Python 函数
3. 解析 `arguments` JSON → 关键字参数
4. 并行执行所有工具（实际是 `RunnableParallel`）
5. 收集结果 → 包装成 `ToolMessage` 列表
6. 写回 state（`state["messages"]` 追加）

#### 4.4.1.3 协议层 3：Toolkit → Interface（方法签名透传）

```python
# [agent_utils.py:281-308](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/agents/utils/agent_utils.py#L281-L308)
@staticmethod
@tool
def get_stockstats_indicators_report(
    symbol: Annotated[str, "ticker symbol of the company"],
    indicator: Annotated[str, "technical indicator to get the analysis and report of"],
    curr_date: Annotated[str, "The current trading date you are trading on, YYYY-mm-dd"],
    look_back_days: Annotated[int, "how many days to look back"] = 30,
) -> str:
    result_stockstats = interface.get_stock_stats_indicators_window(
        symbol, indicator, curr_date, look_back_days, False  # online=False
    )
    return result_stockstats
```

**入参**：

| 参数 | 类型 | 含义 | LLM 怎么填 |
|:---|:---|:---|:---|
| `symbol` | str | 股票代码 | 从 state.company_of_interest 取 |
| `indicator` | str | 技术指标名 | LLM 自选（如 `rsi`, `macd`, `close_50_sma`） |
| `curr_date` | str | 当前日期 | 从 state.trade_date 取 |
| `look_back_days` | int | 回看天数 | LLM 决策（默认 30） |

#### 4.4.1.4 协议层 4：Interface → StockstatsUtils（循环拉数据）

```python
# [interface.py:653-781](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/dataflows/interface.py#L653-L781)
def get_stock_stats_indicators_window(symbol, indicator, curr_date, look_back_days, online):
    ...
    # 关键：best_ind_params 是技术指标的"说明文档"
    best_ind_params = {
        "close_50_sma": "50 SMA: A medium-term trend indicator...",
        "rsi": "RSI: Measures momentum to flag overbought/oversold...",
        # ... 共 30+ 个指标
    }
    ...
    curr_date = datetime.strptime(curr_date, "%Y-%m-%d")
    before = curr_date - relativedelta(days=look_back_days)
    ...
    ind_string = ""
    while curr_date >= before:
        indicator_value = get_stockstats_indicator(symbol, indicator, curr_date, online)
        ind_string += f"{curr_date.strftime('%Y-%m-%d')}: {indicator_value}\n"
        curr_date = curr_date - relativedelta(days=1)
    
    return f"## {indicator} values from {before} to {end_date}:\n\n{ind_string}\n\n{indicator_description}"
```

**关键行为**：
- **倒序遍历**：`curr_date` 递减到 `before`，每天调一次 `get_stockstats_indicator`
- **一次工具调用 = N 次子调用**：30 天回看 = 30 次单日计算
- **offline 模式**（默认）：读本地 CSV；**online 模式**：调 yfinance

#### 4.4.1.5 协议层 5：StockstatsUtils → yfinance 或本地 CSV

```python
# [stockstats.py:15-91](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/dataflows/technical/stockstats.py#L15-L91)
@staticmethod
def get_stock_stats(symbol, indicator, curr_date, data_dir, online=False):
    if not online:
        # 离线模式：读本地 Yahoo Finance CSV
        data = pd.read_csv(
            os.path.join(data_dir, f"{symbol}-YFin-data-2015-01-01-2025-03-25.csv")
        )
        df = wrap(data)  # ← 关键：stockstats 库接管 DataFrame
    else:
        # 在线模式：调 yfinance → 缓存到 CSV
        data = yf.download(
            symbol, start=start_date, end=end_date,
            multi_level_index=False, progress=False, auto_adjust=True
        )
        data.to_csv(data_file, index=False)
        df = wrap(data)
    
    df[indicator]  # ← 触发 stockstats 动态计算
    matching_rows = df[df["Date"].str.startswith(curr_date)]
    return matching_rows[indicator].values[0] if not matching_rows.empty else "N/A"
```

**`stockstats.wrap()` 的魔法**：
- 接收一个含 `Date, Open, High, Low, Close, Volume` 的 DataFrame
- 返回一个 **动态指标 DataFrame**，访问 `df["rsi"]` 时才计算 RSI
- 支持 50+ 指标（`rsi`, `macd`, `kdjk`, `boll`, `close_50_sma` 等）

#### 4.4.1.6 实际触发的网络/磁盘 I/O

| 模式 | 网络 | 磁盘 | 延迟 |
|:---|:---|:---|:---|
| **offline + 缓存命中** | 0 | 1 次 CSV 读 | < 100ms |
| **offline + 未命中** | 0 | 0 | 抛 `FileNotFoundError` |
| **online + 缓存命中** | 0 | 1 次 CSV 读 | < 200ms |
| **online + 未命中** | 1 次 HTTPS yfinance | 1 次 CSV 写 | 1-5s |

> ⚠️ **A 股代码问题**：`get_stockstats_indicators_report` 底层是 **Yahoo Finance**，
> 对 A 股代码（如 `600036`）支持有限，通常需要带交易所后缀（`600036.SS`）。
> 这就是为什么 A 股分析时该工具经常返回空值——实际上它被设计为美股工具！

#### 4.4.1.7 完整调用时序

```
T+0ms    LLM 推理完成，返回 tool_call
T+50ms   LangGraph ToolNode 解析 tool_call
T+80ms   Toolkit.get_stockstats_indicators_report() 被调
T+100ms  interface.get_stock_stats_indicators_window() 进入循环
T+120ms  ┌─ 第1天: get_stockstats_indicator()
T+150ms  │   └─ StockstatsUtils.get_stock_stats()
T+170ms  │       └─ pd.read_csv()  ← 命中缓存
T+200ms  │       └─ df["rsi"]  ← stockstats 计算
T+220ms  │   返回 RSI 值（如 65.3）
T+250ms  ├─ 第2天: ... (重复 30 次)
T+1000ms ┘  循环结束
T+1050ms 拼接字符串返回给 LLM
T+2000ms LLM 第二次推理（基于 RSI 序列出总结）
T+4000ms market_report 写入 reports/market_report.md
```

> 一次完整工具调用 ≈ **2-4 秒**（30 天回看 + LLM 二次推理）。

### 4.5 实际触发的网络请求（按节点）

| 阶段 | 网络目标 | 请求内容 | 频率 |
|:---|:---|:---|:---|
| Market Analyst | LLM 网关 + BaoStock/AKShare | chat.completions + K线/指标 | 2-3 次/分析师 |
| Social Analyst | LLM 网关 + Reddit/雪球 | chat.completions + 帖子 | 2-3 次 |
| News Analyst | LLM 网关 + GoogleNews/Finnhub | chat.completions + 新闻 | 2-3 次 |
| Fundamentals Analyst | LLM 网关 + BaoStock/AKShare/Tushare | chat.completions + 财务/PE/PB | 2-3 次 |
| Bull Researcher | LLM 网关 + ChromaDB 检索 | 仅推理（不调工具） | 1 次/轮 |
| Bear Researcher | LLM 网关 + ChromaDB 检索 | 仅推理 | 1 次/轮 |
| Research Manager | LLM 网关 | 总结辩论 | 1 次 |
| Trader | LLM 网关 | 出计划 | 1 次 |
| Risky/Safe/Neutral | LLM 网关 | 风险辩论 | 1 次/角色/轮 |
| Risk Judge | LLM 网关 | 最终决策 | 1 次 |

> **总 LLM 调用次数 ≈ 12-20 次**（取决于研究深度）

### 4.6 ChromaDB 内存交互

每次 Bull/Bear Researcher 决策前：

```python
# tradingagents/agents/researchers/bull_researcher.py
similar = self.bull_memory.get_memories(query, n_matches=2)
# → 走 ChromaDB 持久化存储
# → 文件落在 ./chroma_db/bull_memory/chroma.sqlite3
# → 走本地 SQLite 查询，不发网络
```

> **首次运行**会下载 Embedding 模型（HF Hub，国内可能慢）。之后命中本地缓存。

### 4.7 文件落盘副作用

通过装饰器，每个 chunk 处理时会自动写：

| 文件 | 内容 |
|:---|:---|
| `message_tool.log` | `HH:MM:SS [Reasoning] <AI 思考>...` |
| `message_tool.log` | `HH:MM:SS [Tool Call] <func>(<args>)` |
| `reports/market_report.md` | 市场分析完整内容 |
| `reports/sentiment_report.md` | 情感分析 |
| `reports/news_report.md` | 新闻分析 |
| `reports/fundamentals_report.md` | 基本面分析 |
| `reports/investment_plan.md` | 研究团队辩论+决策 |
| `reports/trader_investment_plan.md` | 交易计划 |
| `reports/final_trade_decision.md` | 最终决策 |

---

## 阶段 5：报告落盘与信号处理

### 5.1 投资信号处理

```python
# cli/main.py:1567
decision = graph.process_signal(final_state["final_trade_decision"], ticker)
```

`SignalProcessor.process_signal()` 用快速 LLM 抽取：

- `BUY` / `SELL` / `HOLD` 之一
- 理由摘要
- 信心度（0-100）

### 5.2 最终展示

`display_complete_report()` 在 Rich 面板中按 5 个团队分组展示所有报告。

### 5.3 进程退出时的副作用

| 动作 | 文件位置 |
|:---|:---|
| 写 `message_tool.log` | `results/{ticker}/{date}/message_tool.log` |
| 写 7 个 `*_report.md` | `results/{ticker}/{date}/reports/` |
| 写决策摘要 | 控制台 + 日志 |
| 关闭所有日志 Handler | `logger.removeHandler(...)` |
| 关闭 Rich Live 上下文 | `with Live(...) as live:` 自动清理 |

---

## 🌐 全程网络流量汇总

| 流量类型 | 数量 | 来源 |
|:---|:---|:---|
| **LLM API** | 12-20 次 HTTPS POST | DashScope / OpenAI / DeepSeek / GLM 等 |
| **A 股数据 API** | 4-8 次 HTTPS | Tushare（公网）/ BaoStock（公网或本地） |
| **新闻 API** | 1-3 次 HTTPS | GoogleNews RSS / Finnhub |
| **MongoDB** | 1-5 次 TCP | 本地 27017 或远程（取决于配置） |
| **ChromaDB** | 0 次网络 | 本地 SQLite 文件 |
| **HF Hub** | 0-1 次 | 首次下载 Embedding 模型 |

---

## 📁 全程磁盘 I/O 汇总

| 路径 | 内容 | 写入时机 |
|:---|:---|:---|
| `./dataflows/data_cache/*.pkl` | K线/财务数据缓存 | 每次数据源调用 |
| `./chroma_db/{name}/` | 5 套 ChromaDB | 启动时创建/读取 |
| `./results/{ticker}/{date}/reports/*.md` | 7 份报告 | 每节点完成 |
| `./results/{ticker}/{date}/message_tool.log` | 全程消息流 | 每条消息 |
| `./logs/*.log` | 框架日志 | 全程 |

---

## ⏱️ 时间消耗分布（典型情况）

| 阶段 | 占比 | 阻塞点 |
|:---|:---:|:---|
| 1. 启动+问卷 | < 1% | 用户输入速度 |
| 2. LLM 实例化 | < 1% | 无网络 |
| 3. 数据预获取 | 5-10% | Tushare/BaoStock 接口延迟 |
| 4. LangGraph 编排 | 80-90% | LLM 推理 + 工具调用 |
| 5. 信号处理 | 1-2% | 1 次 LLM 调用 |

> **8-15 分钟**是健康时长。超过 20 分钟通常有节点卡死（条件边未触发或 LLM 超时）。

---

## 🔧 常见卡死场景的诊断

| 现象 | 可能原因 | 排查位置 |
|:---|:---|:---|
| `Market Analyst` 卡 5 分钟 | LLM 网关超时 / 工具调用死循环 | `message_tool.log` 看 `tool_call_count` |
| `BaoStock` 一直 pending | 网络问题 | `data_source_manager._try_fallback_sources` 日志 |
| 内存持续上涨 | ChromaDB 重复创建 | `chroma_db/` 目录大小 |
| 报告落盘失败 | `report_dir` 权限 | `cli/main.py:1102` |

---

## 📚 关键代码引用

- [cli/main.py](file:///Users/lishinho/projects/TradingAgents-CN/cli/main.py) — CLI 入口、问卷、流式执行
- [tradingagents/graph/trading_graph.py](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/graph/trading_graph.py) — LangGraph 编排器
- [tradingagents/graph/setup.py](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/graph/setup.py) — 节点注册、边定义
- [tradingagents/graph/conditional_logic.py](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/graph/conditional_logic.py) — 条件边函数
- [tradingagents/agents/utils/agent_utils.py](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/agents/utils/agent_utils.py) — 工具方法
- [tradingagents/dataflows/optimized_china_data.py](file:///Users/lishinho/projects/TradingAgents-CN/tradingagents/dataflows/optimized_china_data.py) — 中国股票数据聚合

---

**版本**: v1.0  
**最后更新**: 2026-06-12
