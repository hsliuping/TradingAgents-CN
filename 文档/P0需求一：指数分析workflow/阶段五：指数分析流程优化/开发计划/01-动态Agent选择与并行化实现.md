<!--
 * @Author: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
 * @Date: 2025-12-22 21:50:20
 * @LastEditors: zhengweicheng 46236959+zwczwczwc@users.noreply.github.com
 * @LastEditTime: 2025-12-22 21:50:21
 * @FilePath: /TradingAgents-CN-Test/文档/P0需求一：指数分析workflow/阶段五：指数分析流程优化/开发计划/01-动态Agent选择与并行化实现.md
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
-->
# 01-动态Agent选择与并行化实现

## 1. 任务目标
实现指数分析工作流的动态构建与并行执行，打破现有的线性硬编码流程。允许用户通过 `selected_analysts` 参数选择需要的分析模块，并且这些模块应当并行运行以节省时间。

## 2. 涉及文件
*   `app/services/simple_analysis_service.py`
*   `tradingagents/graph/trading_graph.py`
*   `tradingagents/graph/setup.py`

## 3. 详细实施步骤

### 3.1 服务层改造 (`simple_analysis_service.py`)
**目标**：移除对指数分析的特殊限制，允许透传 `selected_analysts`。

1.  **定位代码**：找到 `execute_analysis_background` 方法中的进度跟踪器创建逻辑（约953行）。
2.  **修改逻辑**：
    *   **原逻辑**：`if analysis_type == "index": analysts = []`
    *   **新逻辑**：
        ```python
        if analysis_type == "index":
            # 如果前端传递了 selected_analysts，则使用它；否则使用默认的全量列表
            default_index_analysts = ["macro", "policy", "news", "sector", "technical"]
            analysts = request.parameters.selected_analysts or default_index_analysts
        else:
            analysts = request.parameters.selected_analysts or ["market", "fundamentals"]
        ```

### 3.2 Graph 初始化改造 (`trading_graph.py`)
**目标**：确保 `TradingAgentsGraph` 正确接收并处理 `selected_analysts`。

1.  **检查 `__init__`**：确认 `self.selected_analysts` 已被正确赋值（目前已存在，需确认无逻辑覆盖）。
2.  **透传参数**：在 `setup_graph` 方法中调用 `GraphSetup` 时，确保 `selected_analysts` 被传递给 `GraphSetup` 实例，或者 `GraphSetup` 能访问到它。
    *   *注*：`GraphSetup` 目前是 `TradingAgentsGraph` 的成员变量吗？查看代码发现 `GraphSetup` 是在 `trading_graph.py` 中被调用的类。
    *   需要确认 `GraphSetup` 的初始化是否接收 `selected_analysts`。
    *   如果 `GraphSetup` 是独立类，需要修改其 `__init__` 接收 `selected_analysts`。

### 3.3 图构建逻辑重构 (`setup.py`)
**目标**：重写 `_setup_index_graph` 实现动态并行拓扑。

1.  **定义映射表**：
    ```python
    analyst_map = {
        "macro": ("Macro Analyst", "tools_macro", create_macro_analyst, ...),
        "policy": ("Policy Analyst", "tools_policy", create_policy_analyst, ...),
        "news": ("International News Analyst", "tools_international_news", create_international_news_analyst, ...),
        "sector": ("Sector Analyst", "tools_sector", create_sector_analyst, ...),
        "technical": ("Technical Analyst", "tools_technical", create_technical_analyst, ...),
    }
    ```

2.  **动态添加节点**：
    *   遍历 `self.selected_analysts`。
    *   根据映射表，只添加被选中的 Analyst 节点、Tool 节点和 Clear 节点。

3.  **构建并行层**：
    *   **START 连接**：对每个选中的 Analyst，添加边 `START -> {Analyst Name}`。
    *   **Tool 循环**：配置 Analyst <-> Tool 的条件边。
    *   **汇聚连接**：所有 Analyst 完成后（即通过 Clear 节点后），连接到 `Index Bull Researcher`。
        *   `workflow.add_edge(f"Msg Clear {name}", "Index Bull Researcher")`

4.  **处理空选情况**：
    *   如果用户什么都没选（极端情况），直接连接 `START -> Strategy Advisor` 或报错。

5.  **后续链路保持**：
    *   `Index Bull Researcher` -> `Index Bear Researcher` (循环) -> `Strategy Advisor` -> END
    *   *注意*：后续将在 Phase 2 插入风控层。

## 4. 验证标准
1.  **全量选择**：所有5个分析师并行启动，总耗时应显著低于串行耗时。
2.  **部分选择**：只选 "macro" 和 "technical"，其他节点不应执行。
3.  **数据完整性**：汇聚节点 `Index Bull Researcher` 能正确读取到并行执行产生的 State 数据。
