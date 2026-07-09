# TradingAgents-CN v3.0 — 分层提示词架构实施拆解清单

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 待实施 |
| 日期 | 2026-03-07 |
| 作者 | TradingAgents-CN Pro Team |
| 依赖文档 | [分层提示词架构设计](prompt-layered-architecture.md) |

---

## 0. 总体路线

```
Phase 1  兼容式落地（核心组装逻辑 + 预览）    ████████████  2-3 周
Phase 2  策略配置化（注入策略数据库管理）       ██████████    2 周
Phase 3  聊天式 Prompt 设计助手               ████████      2 周
                                              ─────────────────→ 时间
```

Phase 1 是基础，Phase 2/3 在其上递增。以下按 Phase 1 为主做详细拆解，Phase 2/3 给出粒度较粗的条目。

---

## Phase 1：兼容式落地（2-3 周）

### 目标

在不推翻现有模板系统的前提下，完成"基础模板 + 上下文块 + 能力块 + 任务块"的运行时组装，并提供预览能力。

### 前置条件

- `prompt_templates` 集合和 CRUD 正常（✅ 已满足）
- `industry_analysis_profiles` / `stock_analysis_profiles` 集合存在且有数据（✅ 已满足）
- `analysis_profile_service.py` 能力评估逻辑可用（✅ 已满足）
- `template_client.py` 模板选择 + 渲染链路可用（✅ 已满足）

---

### Step 1.1：后端 — 上下文块组装服务（Week 1, Day 1-3）

**新建文件**: `app/services/prompt_assembly_service.py`

**职责**: 将行业画像 + 个股画像 + 能力评估合并为结构化注入块。

**核心方法**:

| 方法 | 说明 |
|------|------|
| `build_analysis_context_block(industry, stock_symbol?)` | 合并行业+个股画像，输出 `analysis_context_block` 文本 |
| `build_capability_block(industry, stock_symbol?)` | 调用能力评估，输出 `capability_block` 文本 |
| `build_task_block(task_description, analysis_type)` | 格式化当前任务目标，输出 `task_block` 文本 |
| `assemble_prompt(agent_type, agent_name, analysis_type, industry, stock_symbol?, task_desc, ...)` | 完整组装入口：选模板 → 生成三块 → 变量替换 → 返回最终 Prompt |

**行业/个股合并规则** (对应设计文档 §6):

```python
def _merge_profiles(industry_profile, stock_profile=None):
    """
    合并规则：
    1. 以行业画像维度为基础
    2. 个股画像可 append / override / disable 行业维度
    3. 输出已归并的最终维度列表 + 每个维度的来源标注
    """
```

**依赖**:
- `app/services/analysis_profile_service.py` → `get_industry_context_for_prompt()`
- `app/models/analysis_profile.py` → `IndustryAnalysisProfile`, `StockAnalysisProfile`
- `tradingagents/utils/template_client.py` → `get_effective_template()`, `format_template()`

---

### Step 1.2：后端 — 扩展模板变量契约（Week 1, Day 2-3）

**修改文件**: `tradingagents/utils/template_client.py`

**改动点**:
1. 在 `format_template()` 中预留三个稳定变量名：
   - `{analysis_context_block}`
   - `{capability_block}`
   - `{task_block}`
2. 这三个变量默认为空字符串（向后兼容），当调用方传入时才替换

**不改动**:
- `get_effective_template()` 的选择逻辑不变
- 模板优先级不变（Node > Workflow > Agent Default）

---

### Step 1.3：后端 — Prompt 预览 API（Week 1, Day 3-4）

**新建路由**: `app/routers/prompt_preview.py`

**端点**:

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/prompt-preview/assemble` | 预览组装后的最终 Prompt |

**请求体**:

```python
class PromptPreviewRequest(BaseModel):
    agent_type: str          # e.g. "analysts_v2"
    agent_name: str          # e.g. "market_analyst_v2"
    analysis_type: str       # "general" / "industry" / "stock"
    industry: Optional[str]  # 行业名称
    stock_symbol: Optional[str]  # 股票代码
    task_description: str    # 当前任务描述
    include_capability: bool = True  # 是否附带能力块
```

**响应**:

```python
class PromptPreviewResponse(BaseModel):
    final_prompt: str           # 最终 Prompt 全文
    sections: Dict[str, str]    # 各段内容：base_role, context_block, capability_block, task_block
    sources: Dict[str, str]     # 各段来源说明
    template_id: str            # 使用的模板 ID
    profile_used: Dict          # 使用的画像信息
    capability_gaps: List[str]  # 能力缺口提醒
```

---

### Step 1.4：后端 — 接入运行时调用链（Week 2, Day 1-2）

**修改文件**: `core/agents/base.py` → `_get_prompt_from_template()`

**改动点**:
1. 在调用 `get_prompt_func()` 之前，检查 state 中是否存在 `industry` / `stock_symbol`
2. 如果存在，调用 `prompt_assembly_service` 生成三个块
3. 将三个块注入 `variables` 字典：
   ```python
   variables["analysis_context_block"] = context_block
   variables["capability_block"] = capability_block
   variables["task_block"] = task_block
   ```
4. 如果 state 中没有相关信息，三个变量留空（向后兼容）

**不改动**:
- 不改变 `_get_prompt_from_template()` 的函数签名
- 不影响不使用这三个变量的旧模板

---

### Step 1.5：前端 — Prompt 预览页（Week 2, Day 2-4）

**新建/修改文件**: `frontend/src/views/Settings/PromptPreview.vue`（新建）

**功能**:
1. 选择 Agent（agent_type + agent_name 联动下拉）
2. 选择分析场景：通用 / 行业 / 个股
3. 选择行业（下拉，数据来自 `industry_analysis_profiles`）
4. 输入股票代码（仅个股场景）
5. 输入任务描述
6. 点击"预览"→ 调用 `/api/v1/prompt-preview/assemble`
7. 左右分栏展示：
   - 左栏：最终 Prompt（高亮各段来源）
   - 右栏：元信息（使用的模板、画像、能力缺口）

**入口**:
- 在现有 Prompt 模板管理页（`TemplateManagement.vue`）顶部新增 Tab "实时预览"
- 或作为独立页面，在设置导航中添加入口

---

### Step 1.6：前端 — 模板编辑器增强提示（Week 2, Day 4-5）

**修改文件**: `frontend/src/views/Settings/TemplateManagement.vue`

**改动点**:
1. 在模板编辑弹窗中，`analysis_requirements` 和 `constraints` 字段旁添加提示：
   - "可使用 `{analysis_context_block}` 变量自动注入行业/个股分析上下文"
   - "可使用 `{capability_block}` 变量自动注入数据能力边界说明"
   - "可使用 `{task_block}` 变量自动注入当前分析任务"
2. 在编辑弹窗底部增加"预览组装效果"按钮，跳转到预览页

**不改动**:
- 不改变模板的保存和 CRUD 流程
- 不强制用户使用新变量

---

### Step 1.7：数据迁移 — 示例模板（Week 3, Day 1-2）

**任务**: 为已有的 v2.0 Agent 模板更新内容，在合适位置插入新变量。

**策略**:
- 不强制迁移所有模板
- 提供 1-2 个"标杆模板"作为示范：
  - `market_analyst_v2` — 在 `analysis_requirements` 中插入 `{analysis_context_block}`
  - `risk_analyst_v2` — 在 `constraints` 中插入 `{capability_block}`
- 编写迁移脚本 `scripts/migrate_templates_add_blocks.py`（可选，手动执行）

---

### Step 1.8：测试与验证（Week 3, Day 3-5）

| 测试项 | 验证内容 |
|--------|----------|
| **向后兼容** | 不使用新变量的旧模板，渲染结果不变 |
| **行业分析** | 选行业后，`analysis_context_block` 正确注入行业维度 |
| **个股分析** | 选个股后，个股维度覆盖行业维度，合并结果正确 |
| **能力块** | `capability_block` 与 UI 能力评估结果一致 |
| **预览 API** | 各段内容、来源、缺口列表正确 |
| **空画像** | 行业/个股画像不存在时，变量为空，不报错 |

---

## Phase 1 交付物清单

| 交付物 | 类型 | 文件路径 |
|--------|------|----------|
| Prompt 组装服务 | 后端 Service | `app/services/prompt_assembly_service.py` |
| Prompt 预览路由 | 后端 Router | `app/routers/prompt_preview.py` |
| 模板变量扩展 | 后端改动 | `tradingagents/utils/template_client.py` |
| 运行时注入 | 后端改动 | `core/agents/base.py` |
| 预览页 | 前端页面 | `frontend/src/views/Settings/PromptPreview.vue` |
| 模板编辑提示 | 前端改动 | `frontend/src/views/Settings/TemplateManagement.vue` |
| 示例模板 | 数据 | 数据库中 1-2 个标杆模板 |

---

## Phase 2：策略配置化（2 周）

> 在 Phase 1 基础上，把注入规则从硬编码搬到数据库，支持按 Agent + 场景精细控制。

### Step 2.1：数据模型 — `prompt_injection_policies` 集合

**新建文件**: `app/models/prompt_injection_policy.py`

**核心字段**（对应设计文档 §7.2）:

```python
class PromptInjectionPolicy(BaseModel):
    agent_type: str                         # Agent 类型
    agent_name: str                         # Agent 名称
    scope: str                              # "general" / "industry" / "stock"
    enabled: bool = True
    injection_mode: str = "summary"         # "none" / "summary" / "full"
    inherit_industry_for_stock: bool = True  # 个股是否继承行业画像
    include_capability_block: bool = True
    include_external_gap_notice: bool = True
    include_comparable_companies: bool = True
    inject_position: str = "analysis_requirements"  # 注入到哪个模板字段
    version: int = 1
```

### Step 2.2：后端 — Policy CRUD API

**新建路由**: `app/routers/prompt_injection_policies.py`

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/v1/prompt-policies` | 列表查询（支持 agent_type/scope 过滤） |
| `GET` | `/api/v1/prompt-policies/{id}` | 获取单个策略 |
| `POST` | `/api/v1/prompt-policies` | 创建策略 |
| `PUT` | `/api/v1/prompt-policies/{id}` | 更新策略 |
| `DELETE` | `/api/v1/prompt-policies/{id}` | 删除策略 |

### Step 2.3：后端 — 组装服务接入策略

**修改文件**: `app/services/prompt_assembly_service.py`

**改动**: `assemble_prompt()` 在组装前先查询当前 Agent + 场景的 Policy，根据 Policy 决定：
- 是否注入行业画像
- 是否注入个股画像
- 注入粒度（summary / full）
- 注入到模板的哪个字段
- 是否附带能力块

### Step 2.4：前端 — 注入策略管理页

**新建文件**: `frontend/src/views/Settings/PromptPolicyManager.vue`

**功能**:
- 按 Agent 列表展示其各场景下的注入策略
- 支持编辑注入模式、继承开关、能力块开关等
- 与 Prompt 预览页联动：修改策略后可立即预览效果

### Step 2.5：初始化脚本

**新建文件**: `scripts/init_prompt_injection_policies.py`

为所有 v2.0 Agent 生成默认策略（统一 summary 模式 + 继承行业画像），作为开箱即用的基础配置。

---

## Phase 3：聊天式 Prompt 设计助手（2 周）

> 让用户通过自然语言优化 Prompt，而非手动改正文。

### Step 3.1：后端 — Prompt 优化对话服务

**新建文件**: `app/services/prompt_design_assistant_service.py`

**功能**:
- 用户输入意图（如"让市场分析师更关注估值"）
- AI 分析当前基础模板 + 注入策略
- 输出建议的模板修改或策略调整
- 支持多轮对话式修订

### Step 3.2：后端 — 对话 API

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/v1/prompt-design/chat` | 对话式 Prompt 修改 |
| `POST` | `/api/v1/prompt-design/apply` | 确认并应用修改 |
| `POST` | `/api/v1/prompt-design/diff` | 查看修改前后对比 |

### Step 3.3：前端 — 聊天式 Prompt 工作台

**新建文件**: `frontend/src/views/Settings/PromptDesignWorkspace.vue`

**交互模式**: 复用行业画像聊天工作台的 UI 模式
- 左栏：对话区
- 右栏：实时预览（修改前 / 修改后对比）
- 底部：确认保存

---

## 风险与缓解

| 风险 | 缓解措施 |
|------|----------|
| 模板正文过长导致 token 超限 | Phase 1 默认用 summary 模式；Phase 2 可按 Agent 单独控制 |
| 旧模板不含新变量，组装无效 | 变量默认空字符串，不影响旧模板；靠标杆模板引导迁移 |
| 能力块与 UI 评估结果不一致 | 共用 `_evaluate_item_coverage()` 数据源，保证一致性 |
| Phase 2 策略过于复杂 | 提供"一键恢复默认策略"功能；限制策略字段数量 |
| 前端改动破坏现有模板管理 | Phase 1 只新增 Tab / 按钮，不改动现有 CRUD 流程 |

---

## 依赖关系图

```
prompt-layered-architecture.md (设计)
    │
    ├── Phase 1: 兼容式落地
    │   ├── Step 1.1: prompt_assembly_service.py
    │   │   └── 依赖: analysis_profile_service.py, template_client.py
    │   ├── Step 1.2: template_client.py 变量扩展
    │   ├── Step 1.3: prompt_preview.py (API)
    │   │   └── 依赖: Step 1.1
    │   ├── Step 1.4: core/agents/base.py 接入
    │   │   └── 依赖: Step 1.1, Step 1.2
    │   ├── Step 1.5: PromptPreview.vue (前端)
    │   │   └── 依赖: Step 1.3
    │   ├── Step 1.6: TemplateManagement.vue 增强
    │   ├── Step 1.7: 示例模板迁移
    │   │   └── 依赖: Step 1.2
    │   └── Step 1.8: 测试验证
    │       └── 依赖: 全部 Step 1.x
    │
    ├── Phase 2: 策略配置化
    │   └── 依赖: Phase 1 全部完成
    │
    └── Phase 3: 聊天式设计助手
        └── 依赖: Phase 2 全部完成
```

---

## 建议开发顺序（Phase 1 内部）

```
Day 1-2:  Step 1.1 (组装服务核心逻辑)
Day 2-3:  Step 1.2 (模板变量扩展) — 可与 1.1 并行
Day 3-4:  Step 1.3 (预览 API) — 依赖 1.1
Day 4-5:  Step 1.4 (运行时接入) — 依赖 1.1 + 1.2
Day 6-8:  Step 1.5 (预览页前端) — 依赖 1.3
Day 8-9:  Step 1.6 (模板编辑器增强) — 可与 1.5 并行
Day 9-10: Step 1.7 (示例模板) — 依赖 1.2
Day 10-12: Step 1.8 (测试) — 依赖全部
```

---

**最后更新**: 2026-03-07
**版本**: v1.0
**维护者**: TradingAgents-CN Pro Team

