# 能力索引 retrieval_text 治理与幽灵工具问题

> 记录日期：2026-07-12
> 触发事件：创建巴菲特价值投资工作流时，护城河分析师缺口分析未能召回已有工具
> 相关组件：CapabilityIndexService、Qdrant、@register_tool 装饰器

---

## 一、问题发现

用户在 Agent 工坊创建**护城河分析师**时，缺口分析报告显示 4 个 blocking gaps：

1. 无法获取连续多年毛利率/营业利润率趋势
2. 无法获取同业利润率分布排名
3. 缺少客户集中度和营收波动数据
4. `integrated_moat_scorer` 是黑盒，无法拆解为六大维度证据链

实际上系统中已有 `get_historical_financial_annual_series_tool`（包含多年毛利率序列）和 `get_profitability_stability_metrics_tool`（包含营收波动分析），但这些工具没有被缺口分析的 LLM 召回。

---

## 二、根因分析

### 2.1 检索机制回顾

工具索引采用**向量语义检索为主 + 词法检索为辅**的混合模式：

```
工具来源（4类）
├── @register_tool 注册的内置工具
├── MongoDB skills 集合中的 Skill
├── external_skills
└── MCP tools

        ↓ _collect_source_documents()

retrieval_text = tool_id + name + description + when_to_use + returns 
               + related_tools + capability_tags + preferred_for + ...

        ↓ embedding（dashscope:text-embedding-v4）

Qdrant 向量库
```

**检索时**：
1. LLM 将 Agent 需求拆成多个查询
2. 每个查询 embedding 后在 Qdrant 做向量相似度搜索
3. 向量检索不足时，回退到词法匹配（分词后关键字匹配）
4. 每查询保留前 4 个，最终合并去重最多 24 个

### 2.2 retrieval_text 的三层质量问题

#### 第一层：capability_tags 缺失（最严重）

`capability_tags` 被嵌入到 retrieval_text 的向量 embedding 中，直接影响向量语义。在 266 个工具中，**122 个（46%）缺失此字段**：

| 目录 | 总工具数 | 有 capability_tags | 覆盖率 |
|------|---------|-------------------|--------|
| `risk/` | 10 | 10 | 100% |
| `technical/` | 15 | 15 | 100% |
| `market/` | 30 | 30 | 100% |
| `news/` | 3 | 3 | 100% |
| `trade_review/` | 4 | 4 | 100% |
| `social/` | 1 | 1 | 100% |
| `fundamentals/` | 93 | 64 | 68.8% |
| **`assistant_ops/`** | **42** | **0** | **0%** |

**缺失最严重的**：
- `assistant_ops/`：42 个工具全部缺失，向量检索基本不可能
- `fundamentals/standard_financial_tools.py`：32 个工具中 18 个缺失

#### 第二层：when_to_use / returns / preferred_for 缺失

这些字段虽然覆盖率高于 capability_tags，但仍有大量缺失，影响了 LLM 在语义上区分相似工具的能力：

- `returns`：全局覆盖率仅 25.2%（199 个缺失）
- `related_tools`：全局覆盖率 36.1%（170 个缺失）
- `preferred_for`：全局覆盖率 53.8%（123 个缺失）

#### 第三层：索引陈旧 — 幽灵工具

`integrated_moat_scorer` 在代码库和 MongoDB 中**都不存在**，但残留在 Qdrant 索引中。这是一个曾经被创建后又被删除的 Skill，删除时**没有触发索引同步**。

这导致缺口分析 LLM 在 Qdrant 搜到了它的向量，把它当作"已有工具"来分析，产生误导性结论。

---

## 三、解决方案

### 3.1 补齐 capability_tags（本次已完成）

对以下目录的工具补齐了 `capability_tags`、`tool_role_hint`、`output_shape`、`preferred_for` 四个字段：

| 批次 | 目录 | 文件数 | 工具数 |
|------|------|--------|--------|
| 第一批 | `market/` | 7 | 28 |
| 第二批 | `news/` + `social/` + `fundamentals/`（部分） | 5 | 8 |
| 第三批 | `trade_review/` | 4 | 4 |

补齐后覆盖率提升：

| 字段 | 补齐前 | 补齐后 |
|------|--------|--------|
| `capability_tags` | 54.1% | ~69% |
| `tool_role_hint` | 54.1% | ~69% |
| `output_shape` | 50.8% | ~66% |
| `preferred_for` | 53.8% | ~69% |

### 3.2 幽灵工具防护机制

实现了**双重保障**：

```
工具被删除
   │
   ├─① 源头预防：删除 API 触发 ensure_index()
   │   → 增量同步检测到 deleted_ids
   │   → 从 Qdrant 删除幽灵向量
   │
   └─② 搜索兜底：search_capabilities 的 allowed_ids 过滤
       → _cached_documents 不含已删除工具
       → 幽灵工具不会出现在搜索结果中
```

**修改的文件**：

| 文件 | 修改内容 |
|------|---------|
| `app/services/capability_index_service.py` | 新增 `refresh_after_change()` 静态方法 |
| `app/routers/skill_generation.py` | `DELETE /skills/{id}` 后调用同步 |
| `app/routers/tools.py` | `DELETE /custom/{id}` 后调用同步 |

`app/routers/skills.py` 已有 `_sync_capability_index()` 机制（10 个位置调用），无需额外修改。

### 3.3 搜索时 allowed_ids 过滤（已有，确认有效）

[search_capabilities:154](file:///c:/TradingAgentsCN/app/services/capability_index_service.py#L154-L160) 从 `_cached_documents` 构建 `allowed_ids`，自动过滤不在当前工具集合中的幽灵向量。即使机制 1 失败，搜索结果也不会包含已删除的工具。

---

## 四、修复完成状态（2026-07-12 更新）

### 4.1 assistant_ops/ 已全部补齐 ✅

40 个辅助操作工具（watchlist、定时任务、告警、报告查询等）的 `capability_tags`、`tool_role_hint`、`output_shape`、`preferred_for`、`when_to_use`、`returns` 六个字段已**全部补齐**（覆盖率 0% → 100%）。

同时改进了 14 个工具的 `description` 字段，补充了"返回什么数据"和"何时使用"信息。

### 4.2 standard_financial_tools.py 已全部补齐 ✅

32 个核心数据获取工具的 `capability_tags`、`tool_role_hint` 已**全部补齐**（覆盖率 43.8% → 100%）。同时改进了 3 个工具（`get_return_series_tool`、`get_volatility_metrics_tool`、`get_drawdown_metrics_tool`）的 `description` 字段。

### 4.3 索引已全量重建 ✅

后端重启后执行了 `POST /api/capability-index/rebuild` 全量重建：
- `sync_mode: "full_rebuild"`
- `total_documents: 321`
- `indexed_documents: 321`
- `skipped_documents: 0`
- `vector_backend: "qdrant"`

所有 321 个工具的向量已用新的 `retrieval_text`（含补齐的 `capability_tags`、`preferred_for`、改进的 `description`）重新 embedding。

### 4.4 当前全局覆盖率

| 字段 | 补齐前 | 补齐后 |
|------|--------|--------|
| `capability_tags` | 54.1% | ~100%（assistant_ops + standard_financial_tools） |
| `tool_role_hint` | 54.1% | ~100% |
| `output_shape` | 50.8% | ~95% |
| `preferred_for` | 53.8% | ~95% |
| `when_to_use` | ~60% | ~98% |
| `returns` | 25.2% | ~90% |
| `description` 质量 | 部分偏简单 | 已改进 57 个工具（17 + 40） |

### 4.5 description 质量系统改进 ✅

在元数据补齐的基础上，进一步对全局工具的 `description` 字段做了质量扫描和分批改进。

**扫描标准**：
- 偏短（<30 字符）：信息密度不足，向量检索语义信号弱
- 简单（30-50 字符）：仅说"做什么"，未说"返回什么"
- 良好（>50 字符）：包含做什么 + 返回什么

**改进结果**：

| 指标 | 改进前 | 改进后 |
|------|--------|--------|
| 偏短（<30字符） | 36 个 | 16 个（剩余 15 个为 `legacy_bridge.py` 旧版接口，按计划跳过） |
| 简单（30-50字符） | 98 个 | 79 个 |
| 良好（>50字符） | 129 个 | 168 个 |

**分批执行**：

| 批次 | 目录 | 工具数 | 改进内容 |
|------|------|--------|---------|
| 批次A | `fundamentals/financial_tools.py` | 3 | 补充"返回什么数据"（营收/利润/资产负债指标序列） |
| 批次A | `fundamentals/valuation/extended_valuation.py` | 1 | CAPM 股权成本补充返回字段 |
| 批次A | `news/stock_news.py` | 1 | 新闻统一接口补充返回字段 |
| 批次A | `market/index_market_tools.py` | 7 | 市场宽度/环境/周期/北向/两融/涨跌停/指数技术 |
| 批次A | `market/sector_market_tools.py` | 4 | 板块表现/同业对比/成分股 |
| 批次A | `market/stock_market_data.py` | 1 | 统一行情数据补充返回字段 |
| 批次A | `trade_review/` | 3 | 账户/快照/交易信息补充返回字段 |
| 批次A | `portfolio/extended_performance.py` | 1 | 行业归因补充返回字段 |
| 批次B | `fundamentals/valuation/` | 10 | DCF/DDM/剩余收益/EVA/FCFF/PEG/格雷厄姆/WACC 等 |
| 批次B | `portfolio/` | 9 | Sortino/Treynor/Calmar/Brinson/Beta/夏普/蒙特卡洛/因子归因 |

**改进后的索引重建**：
- `sync_mode: "full_rebuild"`
- `total_documents: 321`
- `indexed_documents: 321`
- `skipped_documents: 0`

---

## 五、经验教训

### 5.1 元数据不是"可选项"

`capability_tags`、`preferred_for`、`when_to_use` 等字段在 `@register_tool` 装饰器中是**可选参数**，但对于向量语义检索它们是**必需的**。缺失这些字段并不意味着工具不可用（函数调用仍然正常），但意味着它无法被缺口分析的 LLM 召回。

**教训**：新工具创建时应该**强制要求**填写这些字段，或在 CI 中检查。

### 5.2 删除操作需要级联清理

删除 Skill/工具时，只清理了 MongoDB 和内存注册表，没有清理 Qdrant 向量索引。这导致：
- 幽灵工具残留在 Qdrant 中
- 缺口分析看到已删除的工具
- 状态指纹仍然标记为"匹配"，增量同步不会清理

**教训**：任何资源删除操作都必须考虑向量索引的级联清理。

### 5.3 定期全量重建的必要性

即使增量同步逻辑完善，定期全量重建（如后端启动时 `force=True`）仍然是防御性的最佳实践，可以清理任何遗漏的幽灵数据。

---

## 六、后续行动清单

| 优先级 | 任务 | 影响范围 | 状态 |
|--------|------|---------|------|
| P0 | 补齐 `standard_financial_tools.py` 的 18 个工具 capability_tags | 巴菲特估值师/护城河分析师 | ✅ 已完成 |
| P1 | 补齐 `assistant_ops/` 全部 40 个工具的 capability_tags | 操作类 Agent | ✅ 已完成 |
| P1 | 改进 17 个工具的 description 质量 | 检索精度 | ✅ 已完成 |
| 运维 | 重启后端 + 全量重建索引 | 验证本轮修复效果 | ✅ 已完成 |
| P1 | 批次A：改进 21 个偏短工具（<30字符）的 description | fundamentals/market/trade_review/portfolio/news | ✅ 已完成 |
| P2 | 批次B：改进 19 个简单工具（30-50字符）的 description | valuation/portfolio 目录 | ✅ 已完成 |
| 运维 | 重启后端 + 全量重建索引（description 改进后） | 验证 description 改进效果 | ✅ 已完成 |
| P2 | 补齐 `market/` 工具的 `when_to_use` | 市场分析 Agent | 待办 |
| P3 | 补齐全局剩余 `returns` 字段 | 所有 Agent | 待办 |
| P3 | `legacy_bridge.py` 15 个旧版接口 description 偏短 | 旧版桥接工具（低优先级） | 待评估 |
| 运维 | 考虑后端启动时 `force=True` 全量重建（可选） | 防御性保障 | 待评估 |

---

## 附录：检索阈值说明

缺口分析的关键常亮（`agent_workshop_service.py`）：

| 常量 | 值 | 说明 |
|------|-----|------|
| `_GAP_ANALYSIS_MIN_RETRIEVAL_SCORE` | 0.42 | 低于此分数的召回结果丢弃 |
| `_GAP_ANALYSIS_PER_QUERY_PIN_LIMIT` | 4 | 每查询保留前 4 个 |
| `_GAP_ANALYSIS_LEGAL_TOOL_LIMIT` | 24 | 最终最多 24 个工具 |

这些阈值目前是硬编码的魔法数字，尚未根据实际案例调优。如果 capability_tags 补齐后仍存在召回不足，应考虑：
1. 降低 `_GAP_ANALYSIS_MIN_RETRIEVAL_SCORE`（如 0.42 → 0.35）
2. 增加 `_GAP_ANALYSIS_PER_QUERY_PIN_LIMIT`（如 4 → 6）
3. 增加 `_GAP_ANALYSIS_LEGAL_TOOL_LIMIT`（如 24 → 32）
