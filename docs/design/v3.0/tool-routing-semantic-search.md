# 工具路由：从关键词匹配升级为语义向量搜索

> 状态：设计稿，待确认后实现。
>
> 背景：手写工具清单完成后，工具总数从 175 增长到 255，后续还会继续增长。当前基于关键词匹配的工具筛选机制已无法有效区分同类工具，需要升级为语义向量搜索。

---

## 一、问题分析

### 1.1 当前机制

Nanobot 的 `_build_scoped_tools`（[runtime.py](file:///c:/TradingAgentsCN/core/embedded_nanobot/runtime.py)）筛选工具的三级机制：

```
1. CORE_TOOLS（必加）          ~7 个    文件读写、Web 搜索等
2. 意图匹配（按意图添加）       ~10 个    Agent Builder / Skill 创建
3. 关键词评分（动态筛选）        Top 16   对剩余工具按查询词匹配 metadata 文本
```

关键词评分逻辑：把用户查询拆成 token，在每个工具的 `id`、`name`、`description`、`when_to_use`、`returns`、`related_tools` 文本中统计命中次数，按命中数排序取 Top 16。

### 1.2 问题

| 问题 | 说明 | 严重程度 |
|------|------|----------|
| **同词歧义** | "估值" 匹配 DCF、PEG、DDM、格雷厄姆、可比公司、股息估值等 15+ 工具，无法区分哪个最相关 | 高 |
| **语义缺失** | "这股票贵不贵" 不会匹配到"估值"类工具，但匹配到"价格"相关的技术分析工具 | 高 |
| **粒度无区分** | `get_dcf_valuation` 和 `get_dcf_three_stage_valuation` 同时进 Top 16，浪费席位 | 中 |
| **不可扩展** | 每增加 100 个工具，关键词重叠概率线性增长，Top 16 席位被同质化工具占满 | 中 |
| **role_hint 未用** | `tool_role_hint`（specialized/supporting/generic/fallback）已标注但评分未加权 | 低 |

**核心矛盾**：255 个工具的关键词分布在有限的中文财经语料空间内，大量工具共享同一关键词（"估值"、"风险"、"分析"、"信号"），纯文本匹配无法区分。

### 1.3 目标

- 1000 个工具以内，语义搜索能准确找到 Top 16 相关工具
- 同类工具去重，避免席位浪费
- 新增工具无需维护关键词规则，自动生效
- 不增加明显的用户感知延迟

---

## 二、现有基础设施

### 2.1 CapabilityIndexService

系统已有完整的向量检索管线（[capability_index_service.py](file:///c:/TradingAgentsCN/app/services/capability_index_service.py)）：

| 组件 | 说明 |
|------|------|
| `EmbeddingManager` | 多提供商 embedding（DashScope / OpenAI / DeepSeek / Ollama），768 维向量 |
| `VectorStoreManager` | ChromaDB + HNSW 索引，O(log n) 检索 |
| `CapabilityIndexService` | 启动时自动将所有工具 metadata 向量化入库 |
| `search_capabilities()` | 语义搜索入口，支持 `source_types` 过滤、`bindable_only` 过滤 |
| 回退策略 | 向量搜索失败 → 自动回退词法搜索 |

### 2.2 已索引的工具元数据

每个工具的以下字段已被向量化存储：

```python
{
    "capability_id": "get_dcf_valuation",
    "name": "DCF 估值",
    "description": "基于两阶段 DCF 模型计算企业内在价值...",
    "when_to_use": "需要评估公司内在价值时使用...",
    "capability_tags": ["valuation", "fundamental", "dcf"],
    "tool_role_hint": "specialized",
    "preferred_for": ["估值分析", "价值投资"],
    "output_shape": "structured_json",
    "category": "fundamentals",
    "related_tools": ["get_wacc_calculation", "get_financial_data"],
}
```

**尚未入库但已存在于 metadata 中**：`not_replacement_for`、`returns` 字段。这些也应该入库以提升检索精度。

### 2.3 为什么可行

- **向量搜索复杂度 O(log n)**：HNSW 索引，1k 和 10k 工具几乎一样快
- **768 维固定**：不随工具数量增长
- **唯一延迟**：embedding 一次查询（API 调用 ~100ms），搜索本身 < 5ms
- **参考值**：ChromaDB 500 万文档无压力，1k 工具是零头
- **决定质量的是 metadata 质量**：我们的工具 metadata 写得足够详细

---

## 三、方案设计

### 3.1 整体架构

```
用户查询
    │
    ▼
┌─────────────────────────────────────┐
│ 1. CORE_TOOLS（必加）               │  ~7 个，不变
│ 2. 意图匹配（按意图添加）            │  ~10 个，不变
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 3. CapabilityIndexService            │
│    search_capabilities(query)        │  语义搜索 Top 24
│    source_types=["registry"]         │  只搜 registry 工具
│    bindable_only=True                │  只搜可绑定工具
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 4. role_hint 加权排序               │  specialized +30
│                                      │  supporting +15
│                                      │  generic +5
│                                      │  fallback +0
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 5. 同类去重                         │  capability_tags 重叠 > 50%
│                                      │  只保留得分最高的
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│ 6. 取 Top 16                        │  最终返回给 LLM
└─────────────────────────────────────┘
```

### 3.2 关键设计决策

#### 决策 1：先语义搜索，再 role_hint 加权

不把 role_hint 直接作为搜索过滤条件，而是作为后处理排序。原因：
- 用户说"快速看看估值"，可能 expecting 一个 specialized 工具而不是 generic 工具
- 先搜出语义相关的，再按专业化程度排序，确保最专业的工具在前面

#### 决策 2：同类去重用 capability_tags 重叠率

```python
def _is_too_similar(tool_a, tool_b) -> bool:
    tags_a = set(tool_a.capability_tags)
    tags_b = set(tool_b.capability_tags)
    if not tags_a or not tags_b:
        return False
    overlap = len(tags_a & tags_b) / min(len(tags_a), len(tags_b))
    return overlap > 0.5
```

当 `get_dcf_valuation`（tags: valuation, fundamental, dcf）和 `get_dcf_three_stage_valuation`（tags: valuation, fundamental, dcf, three_stage）重叠率 3/3=100% > 50%，只保留得分最高的。

#### 决策 3：保留关键词回退

当 `CapabilityIndexService` 不可用时（向量库未初始化、embedding 服务不可用），自动回退到当前的关键词匹配逻辑。确保系统在任何情况下都能工作。

#### 决策 4：异步改造

`_build_scoped_tools` 当前是同步方法，`search_capabilities` 是 async。改造方案：
- 在 `handle_message` 中提前调用 `_build_scoped_tools`（改为 async）
- 或者：使用 `asyncio.run()` 在同步上下文中调用（简单但不够优雅）
- **推荐**：把 `_build_scoped_tools` 改为 async，在 `handle_message` 中 await

### 3.3 改动范围

| 文件 | 改动 | 说明 |
|------|------|------|
| `core/embedded_nanobot/runtime.py` | 重写 `_build_scoped_tools` | 接入 CapabilityIndexService |
| `core/embedded_nanobot/runtime.py` | `handle_message` 中 await | 异步化 |
| `core/embedded_nanobot/runtime.py` | 新增 `_semantic_tool_search` | 语义搜索逻辑 |
| `core/embedded_nanobot/runtime.py` | 新增 `_deduplicate_similar_tools` | 同类去重逻辑 |
| `core/embedded_nanobot/runtime.py` | 新增 `_rank_by_role_hint` | role_hint 加权排序 |
| `app/services/capability_index_service.py` | 无需改动 | 已有 `search_capabilities` |

### 3.4 不改造的部分

- **Universal Agent** 的工具绑定：Universal Agent 的 `invoke_with_tools` 直接绑定 agent 配置中的所有工具，不走 Nanobot 的工具筛选。这是另一个问题，需要单独设计（按 agent 的 `execution_plan` 做工具筛选）。
- **FlowController** 的 `allowed_tools`：FlowController 仍然按阶段控制工具黑白名单，语义搜索在其约束范围内工作。

---

## 四、实现计划

### 阶段 1：核心改造（本次实现）

1. 在 `runtime.py` 中新增 `_semantic_tool_search` 方法
2. 重写 `_build_scoped_tools`，三步走：
   - CORE_TOOLS + 意图匹配（不变）
   - 语义搜索 Top 24
   - role_hint 加权 + 同类去重 → Top 16
3. `handle_message` 中 await 异步调用
4. 保留关键词回退路径

### 阶段 2：验证（本次实现后）

1. 单元测试：用不同查询验证语义搜索结果的相关性
2. 对比测试：语义搜索 vs 关键词匹配的 Top 16 差异
3. 回归测试：确保 Agent Builder 流程不受影响

### 阶段 3：后续优化（不在本次范围）

1. CapabilityIndexService 补充 `returns`、`not_replacement_for` 字段入库
2. Universal Agent 的工具筛选
3. 用户反馈驱动的搜索结果微调

---

## 五、风险与缓解

| 风险 | 影响 | 缓解 |
|------|------|------|
| Embedding 服务不可用 | 语义搜索失败 | 自动回退关键词匹配 |
| 向量库未初始化 | 搜索无结果 | 回退关键词匹配 + 日志告警 |
| 语义搜索结果不如关键词 | 工具选择变差 | 保留回退路径，可随时切回 |
| 异步改造影响调用链 | 运行时错误 | 只改 `_build_scoped_tools` 和 `handle_message`，边界清晰 |
| API 延迟增加 | 用户感知慢 100ms | embedding 一次查询，后续搜索极快；100ms 相对于 LLM 响应时间可忽略 |

---

## 六、验收标准

1. 用以下查询对比语义搜索和关键词匹配的 Top 16：
   - "分析一下茅台估值合理吗" → 应包含 DCF/PEG/格雷厄姆，不应包含技术分析工具
   - "最近有什么风险信号" → 应包含 Z-Score/M-Score/财务造假，不应包含 VaR/组合风险
   - "技术面怎么看" → 应包含 K线形态/均线交叉/MACD/RSI，不应包含估值工具
2. 同类工具去重生效：`get_dcf_valuation` 和 `get_dcf_three_stage_valuation` 不同时出现
3. embedding 服务不可用时自动回退，不报错
4. Agent Builder 完整流程不受影响（创建 → 确认 → 生成 → 测试 → 发布）

---

## 七、与其他模块的关系

```
                    ┌──────────────────┐
                    │  FlowController  │  ← 阶段级工具黑白名单（不变）
                    └────────┬─────────┘
                             │ allowed_tools / forbidden_tools
                             ▼
用户查询 ──→ _build_scoped_tools ──→ ┌──────────────────────┐
                    │                 │  CORE_TOOLS（必加）    │
                    │                 │  意图匹配（按意图）     │
                    │                 │  语义搜索（Top 24）    │  ← 本次改造
                    │                 │  role_hint 加权        │  ← 本次改造
                    │                 │  同类去重（Top 16）    │  ← 本次改造
                    │                 └──────────────────────┘
                    │
                    ▼
              CapabilityIndexService    ← 已有，不改
              (ChromaDB + Embedding)
```

---
> 文档版本：v1.1
> 创建日期：2026-06-29
> 状态：待实现

## 附录：部署与迁移策略

### A.1 核心原则：预构建索引，随安装包分发

```
开发者侧（发布前）:
  ┌──────────────────────────────────────────────────┐
  │ 1. 用 DashScope embedding 构建全量索引             │
  │ 2. 255 个工具 → ChromaDB 数据（data/chromadb/）    │
  │ 3. 打包到安装包中                                 │
  └──────────────────────────────────────────────────┘

用户侧（安装后）:
  ┌──────────────────────────────────────────────────┐
  │ 启动 → 检测 data/chromadb/ 已有索引               │
  │ 指纹匹配 → 直接使用，零 embedding 调用             │
  │ 指纹不匹配（用户加了自定义工具）→ 见 A.3           │
  └──────────────────────────────────────────────────┘
```

### A.2 为什么需要预构建

| 用户场景 | 问题 |
|----------|------|
| 使用 DeepSeek 大模型 | DeepSeek 线上不提供 embedding 服务 |
| 使用 Ollama 本地模型 | 可能未配置 embedding 模型 |
| 使用 OpenAI 兼容 API | 部分厂商不支持 embedding 端点 |

**预构建索引**让这些用户无需配置 embedding 就能使用语义搜索。

### A.3 增量更新策略

```
用户添加自定义工具/Skill 后:
  ┌──────────────────────────────────────────────────┐
  │ 1. 指纹变更 → 检测到新工具                         │
  │ 2. 有 embedding 模型 → 自动增量构建新工具向量       │
  │ 3. 无 embedding 模型 → 提示用户配置，当前用关键词兜底 │
  └──────────────────────────────────────────────────┘
```

### A.4 索引数据管理

- **存储位置**：`data/chromadb/`（持久化目录）
- **磁盘占用**：~2MB（255 个工具 × 768 维）
- **模型绑定**：DashScope text-embedding-v3（开发者统一构建）
- **导出导入**：直接打包 `data/chromadb/` 目录即可
- **模型隔离**：不同 embedding 模型的向量不可混用，索引中记录 `embedding_provider` 元数据

### A.5 回退保障

任何时候 embedding 索引不可用（文件损坏、模型不兼容），自动回退到关键词匹配，系统正常运行。

### A.6 构建脚本

```bash
# 开发者发布前执行，构建预置索引
python scripts/build_capability_index.py

# 作用：
# 1. 确保 embedding 模型可用（DashScope）
# 2. 遍历 255 个工具，构建 CapabilityIndex
# 3. 验证索引完整性
# 4. 输出 data/chromadb/ 目录
```