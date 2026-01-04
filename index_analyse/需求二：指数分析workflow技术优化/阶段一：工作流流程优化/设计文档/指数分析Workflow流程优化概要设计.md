# 指数分析 Workflow 流程优化概要设计

## 1. 系统架构图

```mermaid
graph TD
    A[Index Info Collector] --> B{数据源健康检查}
    B -->|正常/降级| C[并行分析 Barrier]
    
    subgraph "并行分析层 (支持动态选择)"
        direction TB
        C -.-> D1[Macro Analyst (带缓存)]
        C -.-> D2[Strategic Policy Analyst (长期)]
        C -.-> D3[News Analyst (短期/综合)]
        C -.-> D4[Sector Analyst (资金流增强)]
        C -.-> D5[Technical Analyst]
        C -.-> D6[Sentiment Analyst (后续版本)]
    end
    
    D1 & D2 & D3 & D4 & D5 & D6 --> E[同步节点 Barrier]
    E --> F[Index Bull Researcher]
    E --> G[Index Bear Researcher]
    
    subgraph "多空博弈层"
        F <-->|基于历史模式匹配| G
    end
    
    F & G --> H[Strategy Advisor]
    
    subgraph "风险管理层 (基于 research_depth)"
        H --> I[Risk Manager]
        I --> J1[Risky Analyst]
        I --> J2[Safe Analyst]
        I --> J3[Neutral Analyst]
        J1 & J2 & J3 --> K[Risk Judge]
    end
    
    K --> L[END]
```

## 2. 核心模块设计

### 2.1 宏观分析缓存模块
*   **实现位置**: `tradingagents/tools/index_tools.py` -> `fetch_macro_data`
*   **存储**: MongoDB
*   **Key设计**: `macro_analysis:{YYYY-MM-DD}` (基于查询日期或分析基准日)
*   **TTL**: 7天
*   **逻辑**: 
    1.  计算 Cache Key。
    2.  查询 MongoDB，检查是否存在且 `timestamp > now - 7 days`。
    3.  命中：反序列化返回。
    4.  未命中：调用 API，结果序列化存入 MongoDB，返回结果。

### 2.2 节点职能重构
*   **Strategic Policy Analyst**:
    *   **Prompt**: 强化“长期”、“官方文本”、“结构性影响”，屏蔽“传闻”、“短期”。
    *   **Tools**: 绑定 `fetch_policy_news` (长期模式) 或未来接入的法规库。
*   **News Analyst**:
    *   **Prompt**: 强化“短期”、“市场情绪”、“即时反应”。
    *   **Tools**: 聚合 `fetch_bloomberg_news`, `fetch_reuters_news`, `fetch_google_news`, `fetch_policy_news` (短期模式)。

### 2.3 动态 Agent 选择
*   **实现位置**: `tradingagents/graph/setup.py` -> `_setup_index_graph`
*   **逻辑**: 
    *   接收 `selected_analysts` 列表。
    *   在添加节点 (`graph.add_node`) 和边 (`graph.add_edge`) 时，判断该节点是否在列表中。
    *   **注意**: 必须保留 `index_info_collector`、`strategy_advisor` 等核心骨架节点，仅对分析师节点进行动态剔除。

### 2.4 深度参数传递与应用
*   **Prompt 注入**: 在 `Strategy Advisor` 和 `Risk Manager` 的 System Prompt 中，根据 `research_depth` 动态插入指令。
    *   `depth >= 4`: 插入“必须进行跨周期对比（2018/2020）”、“必须推演极端情境”等强指令。
*   **循环控制**: `research_depth` 继续控制多空辩论的轮次 (1-3轮)。

## 3. 数据结构变更

### 3.1 MongoDB 集合
*   `macro_analysis_cache`:
    *   `key`: String (Index, Unique)
    *   `data`: Object (JSON Report)
    *   `timestamp`: Date
    *   `expire_at`: Date (TTL Index)

### 3.2 AgentState
*   新增 `data_source_status`: `Dict[str, bool]`，用于记录各辅助数据源的可用性状态。
*   新增 `sentiment_analysis`: `Optional[str]`，用于存储情绪分析结果。（后续版本实现）

## 4. 接口设计

### 4.1 Workflow 入口
*   参数新增/确认:
    *   `selected_analysts`: `List[str]` (e.g., `['macro', 'policy']`)
    *   `research_depth`: `str` (Enum: `['快速', '基础', '标准', '深度', '全面']`)