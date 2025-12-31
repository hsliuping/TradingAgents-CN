# 关键技术：RAG 与知识检索 (RAG & Knowledge Retrieval)

## 1. 概述

为了使 Agent 具备"以史为鉴"的能力，TradingAgents-CN 集成了一个基于 ChromaDB 的轻量级 RAG（检索增强生成）系统。在指数分析中，RAG 机制主要用于检索历史上的相似市场情境（Market Situation）及其后续走势，辅助当前决策。

## 2. 核心架构

### 2.1 Vector Store (向量数据库)
*   **选型**: ChromaDB (内存模式，非持久化)。
*   **设计考量**: 考虑到金融市场的动态变化，系统默认采用非持久化模式，每次运行结束后清空记忆，防止过期的历史数据误导当前决策（除非配置为持久化模式）。
*   **多租户隔离**: 系统为不同的 Agent（如 `index_bull_memory`, `index_bear_memory`, `strategy_advisor_memory`）创建独立的 Collection，实现知识隔离。

### 2.2 Embedding (向量化)
系统支持多种 Embedding 模型，按优先级自动降级：
1.  **DashScope (阿里百炼)**: `text-embedding-v3` (首选，中文效果好)。
2.  **OpenAI**: `text-embedding-3-small`。
3.  **DeepSeek**: `deepseek-embedding`。
4.  **Local (Ollama)**: `nomic-embed-text` (离线兜底)。

### 2.3 Memory Structure (记忆结构)
每一条记忆由两部分组成：
*   **Situation (情境)**: 输入向量。包含当时的宏观数据、政策摘要、技术形态等。
*   **Reflection (反思)**: 关联内容。包含当时的决策结果（收益/亏损）、事后复盘总结（Lesson Learned）。

## 3. 工作流程

### 3.1 检索 (Retrieval)
在生成报告前，Agent 会将当前的市场数据（如"CPI上涨，均线死叉"）作为 Query 进行向量检索。
```python
async def retrieve_memories(current_situation):
    situation_vector = await embed_text(current_situation)
    # 检索最相似的 Top-3 历史案例
    results = chromadb.query(situation_vector, n_results=3)
    return format_memories(results)
```

### 3.2 增强 (Augmentation)
检索到的历史案例被注入到 Prompt 中，作为 Context。
```text
System Prompt:
...
Here are some similar historical situations and their outcomes:
1. [2022-03] Similar macro environment (CPI high), Result: Market dropped 15%. Lesson: Avoid tech stocks.
...
Based on the current data and these historical lessons, provide your analysis.
```

### 3.3 反思与存储 (Reflection & Storage)
在交易周期结束后（或模拟回测时），系统会调用 `Reflector` 组件对本次决策进行复盘。
*   **Reflector**: 对比预测与实际走势。
*   **Storage**: 将本次的"情境+反思"存入 ChromaDB，成为未来的参考经验。

## 4. 优势

1.  **个性化进化**: 系统随着运行时间的增长，会积累越来越多的有效经验（Long-term Memory）。
2.  **上下文感知**: 基于语义的相似度检索能够发现非显性的市场规律（如"滞胀期"的特征），而非简单的关键词匹配。
3.  **决策校准**: 历史失败案例的警示作用能有效抑制 LLM 的过度自信。