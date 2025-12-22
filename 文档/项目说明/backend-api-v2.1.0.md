# TradingAgents-CN 后端接口与工作流说明 (v2.1.0)

> **版本**: v2.1.0  
> **日期**: 2024-12-14  
> **代号**: Responsibility Separation (职责分离)

本文档是 TradingAgents-CN 项目 v2.1.0 版本的后端接口与核心工作流的权威说明。本版本重点对**指数分析工作流**进行了架构优化，引入了国际新闻分析节点，并重构了决策机制。

---

## 1. API 接口说明

后端基于 FastAPI 构建，提供 RESTful 接口供前端（Streamlit/Web）调用。

### 1.1 核心分析接口

#### 1.1.1 提交单股/指数分析任务

*   **Endpoint**: `POST /api/analysis/single`
*   **功能**: 提交一个新的分析任务。系统会根据 `is_index` 参数自动选择“个股分析”或“指数分析”工作流。
*   **请求体**:
    ```json
    {
      "symbol": "sh000001",  // 股票或指数代码
      "parameters": {
        "is_index": true,    // true=指数分析, false=个股分析
        "analysis_date": "2024-12-14",
        "research_depth": "deep", // simple, standard, deep
        "selected_analysts": ["macro", "policy", "international_news", "sector"], // 指数分析可选
        "llm_config": { ... } // 可选的模型配置覆盖
      }
    }
    ```
*   **响应**:
    ```json
    {
      "success": true,
      "data": {
        "task_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "pending",
        "message": "任务已创建，等待执行"
      }
    }
    ```

#### 1.1.2 查询任务状态

*   **Endpoint**: `GET /api/analysis/tasks/{task_id}/status`
*   **功能**: 获取任务的实时状态和进度。支持轮询或通过 WebSocket/SSE 获取。
*   **响应**:
    ```json
    {
      "success": true,
      "data": {
        "task_id": "...",
        "status": "processing", // pending, processing, completed, failed
        "progress": 45,         // 0-100 进度百分比
        "current_step": "International News Analyst", // 当前正在执行的节点
        "message": "正在分析国际新闻...",
        "start_time": "2024-12-14T10:00:00",
        "elapsed_time": 120.5
      }
    }
    ```

#### 1.1.3 获取分析结果

*   **Endpoint**: `GET /api/analysis/tasks/{task_id}/result`
*   **功能**: 获取任务完成后的详细分析报告和决策结果。
*   **响应 (指数分析示例)**:
    ```json
    {
      "success": true,
      "data": {
        "analysis_id": "...",
        "stock_symbol": "sh000001",
        "analysis_date": "2024-12-14",
        "summary": "...",
        "recommendation": "...",
        "decision": {
          // v2.1.0 统一决策结构
          "final_position": 0.72,
          "position_breakdown": {
            "core_holding": 0.40,
            "tactical_allocation": 0.32,
            "cash_reserve": 0.28
          },
          "adjustment_triggers": { ... }
        },
        "reports": {
          "macro_report": "...",
          "policy_report": "...",
          "international_news_report": "...", // v2.1 新增
          "sector_report": "...",
          "strategy_report": "..."
        }
      }
    }
    ```

### 1.2 其他接口

*   **批量分析**: `POST /api/analysis/batch` - 提交多个标的进行分析（支持并发）。
*   **历史记录**: `GET /api/analysis/user/history` - 获取用户的历史分析任务。
*   **系统配置**: `GET /api/config/system` - 获取当前系统配置（如模型设置）。

---

## 2. LangGraph 工作流逻辑

后端核心基于 LangGraph 实现多智能体协作。根据任务类型，系统会实例化两种不同的图（Graph）：

### 2.1 个股分析工作流 (Stock Analysis Workflow)
*(v2.1.0 保持稳定，未做重大变更)*

*   **适用场景**: 分析单只个股（A股/港股/美股）。
*   **流程**: Market/News/Social/Fundamental Analysts (串行) -> Bull/Bear Researchers (辩论) -> Research Manager -> Trader -> Risk Team (辩论) -> Risk Judge。
*   **特点**: 侧重于多空辩论和风险控制。

### 2.2 指数分析工作流 (Index Analysis Workflow) - v2.1.0 核心更新
*(代号：Responsibility Separation)*

本版本对指数分析进行了重构，实现了**职责分离架构**：分析 Agent 只负责信息采集和评估，Strategy Advisor 统一负责决策。

#### 2.2.1 工作流图示

```mermaid
graph TD
    START --> Macro[Macro Analyst<br>宏观分析]
    Macro --> Policy[Policy Analyst<br>政策分析]
    Policy --> IntNews[International News Analyst<br>国际新闻分析 (v2.1 New)]
    IntNews --> Sector[Sector Analyst<br>板块轮动]
    Sector --> Strategy[Strategy Advisor<br>策略顾问 (v2.1 Refactored)]
    Strategy --> END
    
    subgraph Data Flow
    Macro -.->|sentiment_score| Strategy
    Policy -.->|overall_support_strength| Strategy
    IntNews -.->|impact_strength| Strategy
    Sector -.->|sentiment_score| Strategy
    end
```

#### 2.2.2 节点详解

1.  **Macro Analyst (宏观分析师)**
    *   **职责**: 分析宏观经济数据（GDP, CPI, PMI, 流动性）。
    *   **输出**: `macro_report`, `sentiment_score` (宏观评分)。

2.  **Policy Analyst (政策分析师) - v2.1 增强**
    *   **职责**: 分析国内政策导向。
    *   **v2.1 新特性**: 能够识别**长期战略政策**（5-10年）与短期政策的区别。
    *   **输出**: `policy_report`, `overall_support_strength` (政策支持强度), `long_term_policies` (长期政策列表)。

3.  **International News Analyst (国际新闻分析师) - v2.1 新增**
    *   **职责**: 监控彭博社、路透社等国际媒体，捕捉先于国内市场的外部冲击或地缘政治信息。
    *   **工具**: `fetch_bloomberg_news`, `fetch_reuters_news`, `fetch_google_news`。
    *   **输出**: `international_news_report`, `impact_strength` (外部冲击强度: 高/中/低)。
    *   **价值**: 提供 1-2 天的信息领先优势，识别“出口管制”、“关税”等外部风险。

4.  **Sector Analyst (板块分析师)**
    *   **职责**: 分析行业轮动和主力资金流向。
    *   **输出**: `sector_report`, `sentiment_score` (板块热度)。

5.  **Strategy Advisor (策略顾问) - v2.1 重构**
    *   **职责**: **统一决策中心**。不再简单的汇总，而是运行一套决策算法。
    *   **输入**: 接收前序所有节点的评分和报告。
    *   **算法逻辑**:
        *   **基础仓位**: 基于宏观评分 + 政策支持强度（长期）。
        *   **短期调整**: 基于国际新闻冲击 + 板块热度（短期）。
        *   **最终仓位** = 基础仓位 + 短期调整。
    *   **输出**: `strategy_report` (包含 `final_position`, `position_breakdown`, `adjustment_triggers`)。

#### 2.2.3 状态管理 (AgentState)

v2.1.0 在 `AgentState` 中新增了以下字段以支持新流程：

```python
class AgentState(TypedDict):
    # ... 原有字段 ...
    
    # v2.1 新增/强化字段
    is_index: bool                  # 标记是否为指数分析
    
    # 国际新闻相关
    international_news_report: str  # 国际新闻分析报告
    
    # 结构化评分 (用于 Strategy Advisor 决策)
    macro_score: float
    policy_score: float
    news_impact_score: float
    sector_score: float
    
    # 最终策略输出
    strategy_report: str            # JSON 格式的策略报告
```

## 3. 升级与兼容性

*   **兼容性**: v2.1.0 的 API 完全向后兼容 v2.0.0。
*   **个股分析**: 未受影响，继续使用原有的“辩论-决策”模型。
*   **指数分析**: 自动启用新的工作流。如果客户端未请求 `international_news`，系统会有默认处理逻辑，但建议在请求参数 `selected_analysts` 中包含它以获得最佳效果。

---

**文档维护**: TradingAgents-CN 架构组