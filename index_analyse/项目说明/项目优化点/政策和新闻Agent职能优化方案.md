# 政策与新闻Agent职能优化方案

## 1. 问题背景

在当前指数分析Workflow中，`Policy Analyst`（政策分析师）和 `International News Analyst`（国际新闻分析师）都以“新闻”作为主要信息来源。这导致了以下问题：

*   **功能重叠**: `International News Analyst` 提到了处理“政策传闻”，这与 `Policy Analyst` 在处理短期政策新闻方面可能存在职责重叠。
*   **职责不清晰**: `Policy Analyst` 的内容可能混杂了长期政策解读和短期新闻事件分析，使得其核心价值——长期政策分析的深度——不够突出。
*   **信息处理效率**: 不同Agent重复拉取和筛选新闻，可能导致资源浪费。
*   **扩展性**: 当需要引入更多国内新闻来源时，现有架构可能难以统一管理。

## 2. 优化目标

通过重新定义 `Policy Analyst` 和 `International News Analyst` 的职责，实现以下目标：

*   **职责明确化**: 使每个Agent的功能更加单一和清晰。
*   **减少重叠**: 消除或显著减少Agent间的功能重叠。
*   **提升分析深度**: 使 `Policy Analyst` 能够更专注于长期、战略性政策的深度解读。
*   **优化信息流**: 统一短期新闻的信息入口，提高处理效率和一致性。
*   **提升可维护性和扩展性**: 简化Agent的内部逻辑，方便未来功能迭代。

## 3. 改造方案

### 3.1. 调整 `Policy Analyst` 的职责

*   **更名建议**：可考虑更名为 `Strategic Policy Analyst` 或 `Policy Interpreter`，以突出其深度解读的职能。
*   **核心职责定位**：
    *   专注于**已颁布的、正式的、具有长期指导意义的国内政策文件和法规的深度解读**。例如，政府工作报告、五年规划、部门发展战略、法律法规修订等。
    *   分析重点是政策文本本身，而非围绕这些政策的短期新闻报道或市场传闻。
    *   评估政策的长期影响、结构性变化、对特定产业的支持或限制，以及政策的连贯性和预期寿命。
*   **数据来源**：除了传统的政策新闻获取，需要引入专门的工具或接口，直接获取官方报告、白皮书、法律法规原文等，以确保分析基于最权威、最原始的信息。
*   **输出侧重**：提供基于政策文本的**深度洞察报告**，包含对政策的解释、对经济结构的影响分析、政策风险与机遇评估等，而非短期市场反应。

### 3.2. 引入统一的 `News Analyst` Agent

*   **功能整合**：该Agent将整合目前 `International News Analyst` 的全部职责，并接管 `Policy Analyst` 当前处理的**所有短期政策新闻和传闻**。
*   **核心职责定位**：
    *   **统筹所有短期、即时性强的国内外新闻消息**，包括：
        *   国际政策传闻（如美联储议息结果预测、地缘政治动态）。
        *   国际突发事件、全球行业动态、市场情绪变化。
        *   国内的短期政策传闻、非官方消息泄露、市场热点新闻。
        *   突发公共事件等。
    *   **评估新闻的短期、中短期影响**：分析新闻事件对市场的影响方向（利好/利空/中性）、强度（高/中/低）、持续时间以及引起市场情绪变化的程度。
    *   **输出侧重**：提供结构化的新闻影响报告，侧重于**市场对短期消息的即时反应和潜在演变**，并给出基于新闻的风险提示。
*   **数据来源**：聚合并兼容当前所有新闻获取工具 (`fetch_policy_news`, `fetch_bloomberg_news`, `fetch_reuters_news`, `fetch_google_news`, `fetch_cn_international_news`)。
*   **内部处理机制**：需要高效地进行新闻的获取、去重、分类（例如：政策类、经济类、行业类、事件类、情绪类），并通过LLM模型进行影响分析。

### 3.3. `Fundamentals Analyst` 的定位

*   根据用户反馈，`Fundamentals Analyst` 应该服务于**指数分析**，分析的是**当前经济基本面情况**。这与我之前的理解（侧重个股）有偏差。
*   **建议调整**: 现有文档 [`Fundamentals Analyst.md`](文档/项目说明/指数分析具体实现/Agent实现/Fundamentals Analyst.md) 的描述需要进行修正，以明确其在指数分析流程中的“基本面”关注点。例如，可以强调其分析的不是单个公司的估值，而是指数整体的估值水平、成分股的盈利能力变化、宏观经济数据在指数层面的体现等。这可能需要新的工具或对 `get_stock_fundamentals_unified()` 进行扩展以支持指数层面的基本面数据聚合。

## 4. 优化后的 Agent 架构

```mermaid
graph TD
    A[START] --> B[Index Info Collector]
    B --> C[并行执行 Barrier]
    C --> D[Macro Analyst]
    C --> E1[Strategic Policy Analyst (聚焦长期、官方政策文本解读)]
    C --> F1[News Analyst (整合国内外短期新闻/事件/传闻)]
    C --> G[Sector Analyst]
    C --> H[Technical Analyst]
    D --> I[同步节点 Barrier]
    E1 --> I
    F1 --> I
    G --> I
    H --> I
    I --> J[Index Bull Researcher]
    J --> K[Index Bear Researcher]
    K --> J{辩论循环}
    J --> L[Strategy Advisor]
    L --> M[风险管理层]
    M --> N[Risky Analyst]
    M --> O[Safe Analyst]
    M --> P[Neutral Analyst]
    N --> Q[Risk Judge]
    O --> Q
    P --> Q
    Q --> R[END]

    subgraph "并行分析阶段 (Parallel Analysis)"
        direction LR
        D --- E1
        E1 --- F1
        F1 --- G
        G --- H
    end
```

## 5. 预期效益

*   **分析精准度提升**: `Policy Analyst` 提供更深入的政策洞察，`News Analyst` 提供更全面的短期市场情绪捕捉。
*   **减少冗余**: 避免重复的新闻获取和去重逻辑。
*   **易于维护和升级**: 各Agent职责清晰，修改和扩展某类分析时影响范围更小。
*   **提高整体运行效率**: 优化新闻处理流程。

## 6. 待讨论事项

*   `Fundamentals Analyst` 的具体职责是否需要进一步细化，明确其在指数分析场景下的“基本面”指的是什么？是否需要开发专门的“指数基本面数据”工具？
*   `Strategic Policy Analyst` 和 `News Analyst` 在具体实现时，新闻筛选和分类规则的粒度如何界定，以确保有效区分？
*   现有 `fetch_policy_news()` 工具是否需要改造或替换，以适应 `Strategic Policy Analyst` 的新定位（如直接获取官方文本）？

## 7. 实施过程中的局限性记录 (2026-01-01)

在实施 `Strategic Policy Analyst` 时，遇到以下局限性：

*   **官方文档获取困难**: 目前系统中缺乏直接获取政府白皮书、法律法规原文、红头文件原件的专用工具。现有的 `fetch_policy_news` 工具主要基于新闻聚合，返回的是媒体报道而非原始文本。
*   **临时解决方案**: 在 Prompt 中明确要求 Agent 将 `fetch_policy_news` 返回的内容作为素材库，并主动筛选出“官方”、“长期”的内容进行分析，同时在报告中注明“缺乏重磅官方文件”的局限性。
*   **未来改进方向**: 需要开发或集成专门的法律法规数据库接口（如北大法宝、中国政府网爬虫等），以支持真正的“原始文本解读”。

## 8. 实施进度更新 (2026-01-01)

### ✅ 已完成工作

1.  **代码重构**:
    *   **战略政策分析师 (`Strategic Policy Analyst`)**: 完成 `policy_analyst.py` 重构，职能转变为专注长期政策解读，Prompt 中增加了对短期传闻的屏蔽指令。
    *   **综合新闻分析师 (`Index News Analyst`)**: 完成 `international_news_analyst.py` 重构，集成了 `fetch_policy_news` 工具，统一处理国内外新闻及政策传闻。
    *   **工作流配置**: 更新 `graph/setup.py`，启用了新的分析师节点和命名。

2.  **测试验证**:
    *   创建测试脚本 `tests/test_analysts_v2.py`。
    *   **单元测试通过**:
        *   验证了战略政策分析师的 Prompt 构建和工具绑定（仅绑定 `fetch_policy_news`）。
        *   验证了综合新闻分析师的工具集成（绑定了所有新闻工具）。
        *   验证了工具调用超限时的降级逻辑。
    *   **环境修复**: 在测试脚本中添加了 MongoDB 连接清理代码，解决了 `ResourceWarning`。

### ⚠️ 后续维护注意事项

1.  **Prompt 调优**: 
    *   目前通过 Prompt 区分“长期政策”和“短期新闻”的效果依赖于 LLM 的理解能力。在实际运行中，如果发现战略政策分析师仍然受短期噪音干扰，需要进一步优化 Prompt 中的 Few-Shot 示例。
    
2.  **数据源扩展**:
    *   当前的 `fetch_policy_news` 返回的是新闻摘要。未来应优先接入全文检索工具，以提升战略分析的深度。

3.  **兼容性监控**:
    *   观察 `Index News Analyst` 在处理国内政策传闻时，是否会与 `Sector Analyst`（板块分析师）产生重叠。如果有，后续可能需要进一步细化板块分析师的输入过滤。
