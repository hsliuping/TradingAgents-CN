# 统一记忆层设计 — 基于 mem0 的全系统记忆整合

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 设计中 |
| 日期 | 2026-03-24 |
| 目标 | 将系统中 6 个分散的记忆孤岛统一接入 mem0，实现跨子系统的智能记忆存储与召回 |
| 前置文档 | [v4.0 Cognee 知识与记忆架构](../v4.0/cognee-knowledge-memory-concept.md)、[v3.0 智能助手](./intelligent-assistant.md)、[v3.0 Skill 生成系统](./skill-generation-system.md) |

---

## 1. 背景与问题

### 1.1 现状：6 个记忆孤岛

当前系统中存在 6 个互不相通的记忆子系统：

```
┌──────────────────┬───────────────────┬────────────────┐
│  智能助手对话历史   │  Skill 生成经验     │ v1.x Agent 记忆 │
│  MongoDB 5 个集合  │  MongoDB sessions   │ ChromaDB       │
│  + 用户画像        │  (pipeline_history) │ (情境→建议)     │
├──────────────────┼───────────────────┼────────────────┤
│  Agent 成长记忆    │  RAG 金融知识库     │ v2.0 Agent 记忆 │
│  MongoDB 2 个集合  │  Qdrant            │ Qdrant(空壳)   │
│  (审核→召回)       │  (knowledge)       │                │
└──────────────────┴───────────────────┴────────────────┘
```

### 1.2 核心问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | 助手对话洞察无法被 Agent 使用 | Agent 不知道用户聊了什么，无法个性化分析 |
| 2 | 成长记忆 → 助手断路 | 助手无法引用 Agent 积累的投研经验 |
| 3 | Skill 经验各自隔离 | 同类 Skill 反复犯相同错误，教训不共享 |
| 4 | v1.x / v2.0 双向量库并存 | 数据不互通，维护成本翻倍 |
| 5 | 无统一检索接口 | 每个子系统自己实现存储和召回，方式各异 |
| 6 | 跨会话记忆薄弱 | 助手只记住最近 10 条消息，长期偏好靠手动画像 |

### 1.3 与 v4.0 Cognee 设想的关系

[v4.0 Cognee 概念文档](../v4.0/cognee-knowledge-memory-concept.md) 提出了三层架构：
- **MongoDB**：结构化业务真相源
- **RAG**：原文与证据召回层
- **Cognee**：关系、变化、长期记忆与事件链推理层

本设计中 mem0 的定位是 **Cognee 之下的通用记忆基础设施**，两者互补：

| 层级 | 职责 | 技术选型 |
|------|------|----------|
| 业务真相 | 结构化数据、配置、状态 | MongoDB（不变） |
| 原文证据 | 文档片段检索 | RAG / FinancialKnowledgeManager（不变） |
| **通用记忆** | **事实提取、语义检索、冲突解决、多级记忆** | **mem0（新增）** |
| 关系推理 | 实体关系图谱、演化跟踪 | Cognee（v4.0 规划，可选） |

mem0 解决的是 "**记住了什么、怎么检索**" 的问题；
Cognee 解决的是 "**实体之间的关系如何变化**" 的问题。

---

## 2. 设计目标

### 2.1 核心目标

1. **一个接口存/取所有记忆** — 智能助手、Skill 生成、Agent 工作流、成长系统统一调用 mem0
2. **智能提取而非原文存储** — mem0 内置 LLM 自动从对话/结论中提取事实
3. **跨子系统记忆互通** — 助手能召回 Agent 经验，Skill 能共享教训
4. **渐进式迁移** — 现有系统逐步接入，不一次性替换

### 2.2 非目标

- 不替代 MongoDB 作为业务真相源
- 不替代 RAG 原文检索
- 不替代 Cognee 的关系图谱推理（v4.0 可以在 mem0 之上叠加 Cognee）
- 不替代 `assistant_threads` / `assistant_thread_messages` 的完整对话存储

---

## 3. mem0 技术选型分析

### 3.1 mem0 核心能力

| 能力 | 说明 | 对我们的价值 |
|------|------|-------------|
| **多级记忆** | User / Session / Agent 三层 | 天然映射我们的用户/会话/Agent |
| **智能事实提取** | LLM 自动从对话中提取关键事实 | 不存原文，只存洞察 |
| **冲突解决** | 新旧记忆矛盾时自动合并/更新 | 用户偏好变化自动更新 |
| **语义检索** | 向量相似度 + 可选 Reranker | 按语义而非关键词召回 |
| **Graph Memory** | 实体关系图谱（可选，需 Neo4j） | 为 v4.0 Cognee 铺路 |
| **自定义提取 prompt** | 可针对金融领域定制 | 定制投研事实提取规则 |
| **异步支持** | async add / search | 与我们的 FastAPI 异步架构匹配 |

### 3.2 基础设施复用

| 组件 | mem0 需要 | 我们已有 | 对接方式 |
|------|----------|---------|---------|
| 向量库 | Qdrant / ChromaDB / MongoDB 等 | Qdrant (`core/memory/`) | 直接复用现有 Qdrant 实例 |
| LLM | OpenAI / DeepSeek / Ollama 等 | DeepSeek + 多 Provider | 通过 OpenAI 兼容接口对接 |
| Embedding | OpenAI / HuggingFace / Ollama 等 | EmbeddingManager (多 Provider) | 配置 mem0 使用相同的 Embedding |
| 历史存储 | SQLite（默认）| MongoDB | 可配置使用 MongoDB 或保持默认 |

### 3.3 部署方式

推荐 **自托管开源版**（`pip install mem0ai`），原因：
- 数据不出境，符合金融数据合规要求
- 复用现有 Qdrant，无额外基础设施成本
- 可自定义提取 prompt，针对 A 股/金融领域优化
- Apache 2.0 许可证，无商业限制

---

## 4. 记忆分类与 scope 设计

### 4.1 记忆 scope 定义

为所有记忆统一定义 scope（通过 mem0 的 metadata 实现）：

| scope | 含义 | 写入来源 | 召回场景 |
|-------|------|---------|---------|
| `conversation` | 对话中提取的事实/偏好 | 智能助手每轮对话后 | 助手对话前、Agent 执行前 |
| `user_preference` | 用户长期偏好（投资风格、风险等级等）| 对话提取 + 画像同步 | 助手 system prompt、分析配置 |
| `analysis_insight` | 分析结论/观点 | 工作流完成后 | 助手回答相关问题时、二次分析时 |
| `skill_lesson` | Skill 生成教训 | 管线迭代失败后 | Skill 生成/修复时 |
| `agent_experience` | Agent 投研经验 | 工作流完成后 Agent 沉淀 | Agent 执行前召回 |
| `trade_pattern` | 交易行为模式/纪律偏差 | 复盘完成后 | 助手讨论交易时、制定计划时 |

### 4.2 mem0 多级记忆映射

```
mem0 层级          我们的映射
──────────────     ────────────────────────────────
user_id           → 系统 user_id（跨会话持久）
session_id        → thread_id / session_id（单次会话内）
agent_id          → agent 类型 ID（如 "assistant", "bull_researcher", "skill_generator"）
metadata.scope    → 上述 6 种 scope
metadata.symbol   → 股票代码（可选）
metadata.task_id  → 关联任务 ID（可选）
```

---

## 5. 系统架构

### 5.1 整体架构

```
┌────────────────────────────────────────────────────────────────────┐
│                         应用层 (调用方)                              │
│                                                                    │
│  智能助手    Skill 生成    工作流 Agent    成长系统    Gateway IM    │
│     │           │             │             │            │         │
│     └───────────┴─────────────┴─────────────┴────────────┘         │
│                               │                                    │
│                    ┌──────────▼──────────┐                         │
│                    │  MemoryService      │  core/memory/service.py  │
│                    │  (适配层/门面)       │                         │
│                    └──────────┬──────────┘                         │
│                               │                                    │
├───────────────────────────────┼────────────────────────────────────┤
│                    ┌──────────▼──────────┐                         │
│                    │      mem0 SDK       │  pip install mem0ai     │
│                    │  Memory.from_config │                         │
│                    └──┬──────────────┬───┘                         │
│                       │              │                              │
│              ┌────────▼───┐  ┌───────▼────────┐                    │
│              │  Qdrant    │  │  DeepSeek LLM  │                    │
│              │  (向量库)   │  │  (事实提取)     │                    │
│              └────────────┘  └────────────────┘                    │
│                                                                    │
│  不变的层:  MongoDB (业务真相) │ RAG (原文检索) │ Cognee (v4.0 图谱)  │
└────────────────────────────────────────────────────────────────────┘
```

### 5.2 MemoryService 适配层

`core/memory/service.py` 作为 mem0 之上的薄包装，提供：

1. **初始化** — 从系统配置（MongoDB `system_configs`）读取 mem0 config
2. **存储** — 按 scope 标记元数据
3. **召回** — 按 scope + user_id + agent_id 过滤检索
4. **批量** — 支持批量写入（如 Skill 教训）
5. **降级** — mem0 不可用时静默降级，不阻塞主流程

```python
class MemoryService:
    """统一记忆服务 — mem0 适配层"""

    async def store(
        self,
        messages: list[dict],
        *,
        user_id: str = "",
        agent_id: str = "",
        session_id: str = "",
        scope: str = "conversation",
        metadata: dict | None = None,
    ) -> list[str]:
        """存储记忆（mem0 自动提取事实）"""

    async def recall(
        self,
        query: str,
        *,
        user_id: str = "",
        agent_id: str = "",
        scopes: list[str] | None = None,
        limit: int = 5,
    ) -> list[MemoryItem]:
        """语义召回相关记忆"""

    async def recall_formatted(
        self,
        query: str,
        *,
        user_id: str = "",
        agent_id: str = "",
        scopes: list[str] | None = None,
        limit: int = 5,
        max_chars: int = 1500,
    ) -> str:
        """召回并格式化为可注入 prompt 的文本"""

    async def get_user_summary(
        self,
        user_id: str,
        scopes: list[str] | None = None,
    ) -> str:
        """获取用户记忆摘要"""
```

### 5.3 MemoryItem 数据模型

```python
class MemoryItem(BaseModel):
    """mem0 返回的单条记忆"""
    id: str
    memory: str              # mem0 提取的事实文本
    user_id: str = ""
    agent_id: str = ""
    scope: str = ""
    score: float = 0.0       # 语义相似度分
    metadata: dict = {}
    created_at: str = ""
    updated_at: str = ""
```

---

## 6. 各子系统接入方案

### 6.1 智能助手

**写入时机**：每轮对话完成后

```python
# app/services/intelligent_assistant_service.py

# 对话结束后，异步存储记忆
async def _store_conversation_memory(db, user_id, thread_id, user_msg, assistant_msg, tools_used):
    memory_svc = get_memory_service()
    messages = [
        {"role": "user", "content": user_msg},
        {"role": "assistant", "content": assistant_msg},
    ]
    await memory_svc.store(
        messages,
        user_id=user_id,
        agent_id="assistant",
        session_id=thread_id,
        scope="conversation",
        metadata={"tools_used": tools_used},
    )
```

**召回时机**：构建 system prompt 时

```python
# 在 _build_system_prompt 或 chat 入口处
relevant_memories = await memory_svc.recall_formatted(
    query=user_message,
    user_id=user_id,
    scopes=["conversation", "user_preference", "analysis_insight", "trade_pattern"],
    limit=8,
    max_chars=2000,
)
# 注入到 system prompt 的【你对该用户的了解】段落
```

**与现有系统关系**：
- `assistant_threads` / `assistant_thread_messages` 继续负责完整对话存储（原文历史）
- `assistant_user_profiles` 的核心字段保留，但长期偏好同步写入 mem0
- mem0 负责**跨会话的事实记忆**，thread 负责**单会话的完整消息**

### 6.2 Skill 生成系统

**写入时机**：管线每轮迭代产生 reflection 后 + 最终失败/成功后

```python
# core/tools/external/iteration_controller.py

# 每轮反思后存教训
if reflection and reflection.root_cause:
    await memory_svc.store(
        [{"role": "system", "content": f"Skill {spec.tool_id} 生成失败: {reflection.root_cause}"}],
        agent_id="skill_generator",
        scope="skill_lesson",
        metadata={
            "tool_id": spec.tool_id,
            "category": spec.category,
            "data_source": spec.data_source,
            "stage": stage,
        },
    )
```

**召回时机**：代码生成前

```python
# code_generator.py — 构建 prompt 前

# 召回同类 Skill 的历史教训
lessons = await memory_svc.recall_formatted(
    query=f"{spec.description} {spec.data_source} {spec.category}",
    agent_id="skill_generator",
    scopes=["skill_lesson"],
    limit=10,
    max_chars=2000,
)
# 注入到 system prompt 的【历史教训】段落
```

**关键改进**：教训不再局限于单个 session 的 `pipeline_history`，而是**跨所有 Skill 共享**。
生成"获取东方财富新闻"的 Skill 时，能召回之前生成"获取新浪新闻"时踩过的坑。

### 6.3 工作流 Agent

**写入时机**：工作流完成后

```python
# app/services/unified_analysis_service.py — 任务完成回调

# 提取分析结论作为记忆
await memory_svc.store(
    [{"role": "assistant", "content": conclusion_text}],
    user_id=user_id,
    agent_id=agent_id,  # e.g. "bull_researcher"
    scope="analysis_insight",
    metadata={"symbol": symbol, "task_id": task_id},
)
```

**召回时机**：Agent 执行前（替换当前的 growth_memory_recall 注入）

```python
# core/agents/base.py — 渲染 prompt 时

# 召回该 Agent 的历史经验 + 该用户的分析记忆
memories = await memory_svc.recall_formatted(
    query=current_task_description,
    user_id=user_id,
    agent_id=agent_id,
    scopes=["agent_experience", "analysis_insight"],
    limit=5,
    max_chars=1500,
)
```

### 6.4 Agent 成长系统

**迁移策略**：渐进式

- Phase 1：成长记忆的**写入**同时写 MongoDB + mem0（双写）
- Phase 2：成长记忆的**召回**切换到从 mem0 检索（验证效果后）
- Phase 3：MongoDB 的 `agent_memory_items` 降级为审计日志

### 6.5 Gateway IM

**写入时机**：IM 对话结束后（同智能助手）

**特殊处理**：IM 对话通常更短、更口语化，mem0 的事实提取需要过滤噪音。
通过自定义 `custom_fact_extraction_prompt` 实现。

### 6.6 RAG 金融知识库

**不迁移**。`FinancialKnowledgeManager` 负责原文片段检索，与 mem0 的事实记忆互补：
- RAG 回答 "年报第三章说了什么"
- mem0 回答 "这家公司近三年的战略方向怎么变的"

---

## 7. mem0 配置方案

### 7.1 基础配置

```python
MEM0_CONFIG = {
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "host": QDRANT_HOST,       # 复用现有 Qdrant
            "port": QDRANT_PORT,
            "collection_name": "mem0_memories",
        },
    },
    "llm": {
        "provider": "openai",          # DeepSeek 兼容 OpenAI 接口
        "config": {
            "api_key": DEEPSEEK_API_KEY,
            "base_url": DEEPSEEK_BASE_URL,
            "model": "deepseek-chat",
            "temperature": 0.1,
        },
    },
    "embedder": {
        "provider": "openai",
        "config": {
            "api_key": EMBEDDING_API_KEY,
            "base_url": EMBEDDING_BASE_URL,
            "model": EMBEDDING_MODEL,
        },
    },
}
```

### 7.2 自定义事实提取 prompt（金融领域）

```python
CUSTOM_FACT_EXTRACTION_PROMPT = """
你是一个专业的金融信息提取器。从对话中提取以下类型的事实：

1. 用户投资偏好（风格、行业偏好、风险等级）
2. 用户对特定股票/板块的观点或结论
3. 分析结论和投资建议
4. 交易行为模式和纪律偏差
5. 数据源使用经验和技术教训

规则：
- 只提取明确陈述的事实，不做推测
- 忽略寒暄、问候、闲聊
- 每条事实独立、简洁（一句话）
- 包含关键实体（股票代码、时间、金额等）
"""
```

### 7.3 配置存储位置

遵循项目配置原则：**数据库配置 > .env 配置 > 代码默认值**

- mem0 的 Qdrant/LLM/Embedding 连接参数 → `.env`（基础设施）
- mem0 的自定义 prompt / scope 定义 → MongoDB `system_configs`（业务配置）
- 代码中的默认值 → 作为最后兜底

---

## 8. 数据流图

### 8.1 写入流

```
用户对话 / Agent 产出 / Skill 迭代
         │
         ▼
    MemoryService.store()
         │
         ▼
    mem0.add(messages, user_id, agent_id, metadata={scope, symbol, ...})
         │
         ├──→ LLM 事实提取（DeepSeek）
         │         │
         │         ▼
         │    提取出 N 条事实
         │         │
         │         ├──→ 冲突检测（与现有记忆对比）
         │         │         │
         │         │         ▼
         │         │    合并 / 更新 / 新增
         │         │
         ▼         ▼
    Qdrant 向量存储（语义索引）
```

### 8.2 召回流

```
用户提问 / Agent 执行 / Skill 生成
         │
         ▼
    MemoryService.recall(query, user_id, scopes, limit)
         │
         ▼
    mem0.search(query, user_id, agent_id, filters={scope: [...]})
         │
         ├──→ Embedding 向量化
         │         │
         │         ▼
         │    Qdrant 语义检索
         │         │
         │         ▼
         │    Top-K 结果 + 分数
         │
         ▼
    MemoryService.recall_formatted()
         │
         ▼
    格式化为 prompt 注入文本（控制在 max_chars 内）
         │
         ▼
    注入到 LLM 的 system prompt / user prompt
```

---

## 9. 迁移计划

### Phase 0：基础设施就绪（1 周）

- [ ] 安装 `mem0ai` 依赖
- [ ] 实现 `core/memory/service.py` — MemoryService 适配层
- [ ] 编写 mem0 配置加载逻辑（从 `.env` + MongoDB）
- [ ] 编写金融领域自定义事实提取 prompt
- [ ] 验证 mem0 + Qdrant + DeepSeek 联通性

### Phase 1：智能助手接入（1~2 周）

- [ ] 助手对话结束后异步写入 mem0（新增，不改现有流程）
- [ ] 助手构建 prompt 时从 mem0 召回记忆（替换/增强 `_build_profile_block`）
- [ ] 用户画像核心字段同步到 mem0（双写期）
- [ ] 验证跨会话记忆效果
- [ ] 观测 mem0 事实提取质量，调优 prompt

### Phase 2：Skill 生成接入（1 周）

- [ ] 迭代失败反思后写入 skill_lesson 到 mem0
- [ ] CodeGenerator 生成前召回同类教训
- [ ] 验证跨 Skill 教训共享效果
- [ ] 对比有/无 mem0 教训时的生成成功率

### Phase 3：工作流 Agent 接入（1~2 周）

- [ ] 分析完成后写入 analysis_insight
- [ ] BaseAgent 执行前召回 agent_experience
- [ ] 替换当前 growth_memory_recall 的注入方式
- [ ] 验证 Agent 分析质量是否提升

### Phase 4：统一收口 + 清理（1 周）

- [ ] 成长记忆系统切换到 mem0 召回
- [ ] v1.x ChromaDB Agent 记忆迁移到 mem0
- [ ] 清理 `core/memory/memory_manager.py` 中不再使用的代码
- [ ] 统一 API：所有子系统通过 MemoryService 交互，不再直连向量库
- [ ] 监控 & 告警：mem0 写入/召回延迟、事实提取质量

---

## 10. 性能与成本估算

### 10.1 LLM 调用量

mem0 每次 `add` 需要一次 LLM 调用做事实提取：

| 场景 | 频率 | 单次 token | 日估算 |
|------|------|-----------|--------|
| 助手对话写入 | ~200 次/天 | ~500 token | ~100K token |
| Skill 教训写入 | ~20 次/天 | ~300 token | ~6K token |
| 分析结论写入 | ~50 次/天 | ~400 token | ~20K token |
| **合计** | | | **~126K token/天** |

使用 DeepSeek 按 ¥1/百万 token 计算，**日成本 < ¥0.2**，几乎可忽略。

### 10.2 检索延迟

mem0 + Qdrant 本地部署，语义检索延迟 **< 50ms**。
不会对对话响应时间产生可感知的影响。

### 10.3 存储量

按每用户每天 20 条记忆，100 个活跃用户，运行 1 年：
- 记忆条数：~730K 条
- Qdrant 向量存储：~1.5 GB（1536 维 × 730K）
- 完全在现有 Qdrant 的承载范围内

---

## 11. 风险与应对

| 风险 | 概率 | 影响 | 应对 |
|------|------|------|------|
| mem0 事实提取质量不足 | 中 | 记忆噪音 | 自定义金融领域提取 prompt；定期审计记忆质量 |
| 记忆膨胀导致检索变慢 | 低 | 延迟上升 | 按 scope 分 collection；过期记忆定期清理 |
| mem0 版本升级不兼容 | 低 | 需要适配 | MemoryService 适配层隔离，不直接暴露 mem0 API |
| 多用户记忆串线 | 中 | 隐私泄露 | 所有操作强制带 user_id；定期校验隔离性 |
| Qdrant 不可用 | 低 | 记忆不可用 | MemoryService 降级处理，返回空记忆，不阻塞主流程 |
| LLM 提取幻觉 | 中 | 虚假记忆 | 提取 prompt 要求只提取明确陈述的事实；召回时附带置信度分数 |

---

## 12. 文件结构规划

```
core/memory/
├── __init__.py
├── service.py              # MemoryService — mem0 适配层（新增）
├── config.py               # mem0 配置加载（新增）
├── prompts.py              # 自定义事实提取 prompt（新增）
├── models.py               # MemoryItem 等数据模型（新增）
├── memory_manager.py       # 现有 VectorStoreManager（保留，Phase 4 后降级）
├── embedding_manager.py    # 现有 EmbeddingManager（保留，mem0 可复用）
└── compat.py               # v1.x 记忆兼容层（Phase 4 迁移用）
```

---

## 13. 验收标准

### Phase 1 验收

- [ ] 助手能记住用户 3 天前说过的偏好（如"我偏好科技股"），并在后续对话中引用
- [ ] 用户切换主题后，助手仍能召回相关记忆
- [ ] mem0 不可用时，助手正常工作（降级）

### Phase 2 验收

- [ ] 生成"获取东方财富新闻"Skill 时，能召回之前"获取新浪新闻"的教训
- [ ] Skill 生成成功率相比无 mem0 教训时提升 ≥ 15%

### Phase 3 验收

- [ ] Agent 分析时能引用该用户之前的分析结论
- [ ] 助手能回答"上次分析贵州茅台得出什么结论"类跨会话问题

### Phase 4 验收

- [ ] 所有子系统通过 MemoryService 统一接口交互
- [ ] v1.x ChromaDB 记忆数据已迁移
- [ ] 系统中不再有直连向量库的记忆操作（MemoryService 之外）

---

## 14. 后续演进

| 时间 | 方向 |
|------|------|
| v3.x | mem0 统一记忆层上线，6 个孤岛收口 |
| v4.0 | 在 mem0 之上叠加 Cognee Graph Memory，支持关系推理 |
| v4.x | 记忆过期/衰减策略、记忆质量评估、用户可见的"我的记忆"管理页面 |
