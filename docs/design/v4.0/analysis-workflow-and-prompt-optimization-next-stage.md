# 分析流程提示词优化设计：智能修改 + 上下文感知

> **版本**: v4.0 设计草案
> **日期**: 2026-03-07
> **状态**: 设计讨论中

---

## 一、问题定义

### 问题 1：提示词修改仍然是手动的

当前系统的提示词修改流程：

```
用户 → 打开模板管理页面 → 手动编辑 system_prompt / user_prompt → 保存
```

用户需要**自己懂提示词工程**，才能写出好的分析提示词。这对绝大多数投资者来说门槛太高。

### 问题 2：提示词是"一刀切"的

当前提示词优先级：`Debug > Workflow专属 > User > System默认`

但无论分析比亚迪（新能源汽车）还是贵州茅台（白酒），**用的是同一套提示词**。实际上：

- **行业不同**：分析银行需要关注 NIM、不良率；分析半导体需要关注产能利用率、制程
- **个股不同**：分析茅台需要关注渠道价差、批价；分析宁德时代需要关注出货量、技术路线
- **市场阶段不同**：牛市关注成长性，熊市关注防御性

---

## 二、现有基础设施盘点

### ✅ 已具备的能力

| 能力 | 位置 | 说明 |
|------|------|------|
| 模板优先级加载 | `core/agents/base.py` | Debug > Workflow > User > System |
| 系统变量注入 | `core/api/workflow_api.py` | `industry`, `company_name`, `ticker`, `market_type` 已自动提取 |
| workflow_id 绑定 | `PromptTemplate.workflow_id` | 支持工作流级别专属提示词 |
| node_id 绑定 | `PromptTemplate.node_id` | 支持节点级别专属提示词 |
| AI 生成提示词 | `core/workflow/generator/prompt_generator.py` | `PromptGenerator` 已能根据蓝图生成工作流专属提示词 |
| 模板变量渲染 | `PromptManager.render()` | 支持 `{{ticker}}`, `{{industry}}` 等变量替换 |
| preference_type | `PromptTemplate.preference_type` | 已支持 aggressive / neutral / conservative |

### ❌ 缺失的能力

| 能力 | 说明 |
|------|------|
| 行业级提示词 | 无法为"银行业"统一定制一套分析重点 |
| 个股级提示词 | 无法为"比亚迪"单独定义分析维度 |
| AI 辅助修改 | 用户不会写提示词，没有 AI 协助 |
| 分析质量反馈闭环 | 分析结果好坏无法反哺提示词改进 |
| 行业知识库 | 没有结构化的行业分析维度知识 |

---

## 三、设计方案

### 方案总览

```
┌────────────────────────────────────────────────────────┐
│                  提示词解析优先级 (扩展后)                │
│                                                        │
│  Debug模板 > 个股专属 > 行业专属 > Workflow专属          │
│           > User模板 > System默认                       │
│                                                        │
│  新增两层：                                             │
│  - 个股专属: stock_symbol = "002594.SZ"                 │
│  - 行业专属: industry = "汽车"                          │
└────────────────────────────────────────────────────────┘
```

### 3.1 上下文感知提示词（Context-Aware Prompts）

#### 核心思路：模板继承 + 行业知识注入

不改变现有模板结构，而是在模板渲染阶段，**根据上下文动态注入行业/个股专属分析维度**。

#### 3.1.1 新增数据模型：行业分析配置

```python
# 新集合: industry_analysis_profiles
{
    "industry": "银行",           # 行业名称（与 stock_basic_info.industry 对应）
    "analysis_dimensions": [       # 该行业的关键分析维度
        {
            "name": "净息差(NIM)",
            "description": "银行核心盈利指标，衡量资产收益率与负债成本率之差",
            "importance": "critical",
            "data_source": "fundamentals"
        },
        {
            "name": "不良贷款率",
            "description": "衡量银行资产质量的关键指标",
            "importance": "critical",
            "data_source": "fundamentals"
        },
        {
            "name": "拨备覆盖率",
            "description": "银行风险缓冲能力指标",

#### 3.1.2 新增数据模型：个股分析配置

```python
# 新集合: stock_analysis_profiles
{
    "stock_symbol": "002594.SZ",   # 股票代码
    "company_name": "比亚迪",
    "industry": "汽车",
    "analysis_dimensions": [        # 个股专属分析维度（覆盖行业默认）
        {
            "name": "新能源汽车月销量",
            "description": "比亚迪核心增长指标，关注同比和环比变化",
            "importance": "critical",
            "data_source": "news"
        },
        {
            "name": "DM-i/EV 销售占比",
            "description": "混动与纯电销量结构，反映产品战略方向",
            "importance": "high",
            "data_source": "fundamentals"
        }
    ],
    "special_notes": "比亚迪同时涉及汽车制造和动力电池，需要从两个维度评估",
    "created_at": "2026-03-07T00:00:00Z",
    "source": "ai_generated"       # system | ai_generated | user
}
```

#### 3.1.3 提示词渲染流程（扩展后）

```
原始模板 (system_prompt + analysis_requirements)
        │
        ▼
┌───────────────────────┐
│  1. 查找个股配置       │  stock_analysis_profiles.find(symbol=ticker)
│     有 → 注入个股维度  │
│     无 → 继续          │
└───────┬───────────────┘
        ▼
┌───────────────────────┐
│  2. 查找行业配置       │  industry_analysis_profiles.find(industry=行业)
│     有 → 注入行业维度  │
│     无 → 继续          │
└───────┬───────────────┘
        ▼
┌───────────────────────┐
│  3. 变量替换           │  {{ticker}}, {{company_name}}, {{industry}}...
│     + 注入分析维度     │  {{industry_dimensions}}, {{stock_dimensions}}
└───────┬───────────────┘
        ▼
   最终提示词发送给 LLM
```

**关键设计决策**：不新增提示词模板，而是在现有模板中增加 `{{industry_dimensions}}` 和 `{{stock_dimensions}}` 变量。这样：

- 不需要为每个行业 × 每个 Agent 创建独立模板（组合爆炸）
- 行业知识和提示词模板解耦，可以独立维护
- 个股维度覆盖行业维度，行业维度补充通用模板

#### 3.1.4 实现位置

在 `_prepare_system_variables()` 中扩展：

```python
# core/api/workflow_api.py - _prepare_system_variables() 扩展

# 现有: 已获取 industry, company_name
# 新增: 查询行业分析配置
industry_profile = db.industry_analysis_profiles.find_one(
    {"industry": industry}
)
if industry_profile:
    dimensions = industry_profile.get("analysis_dimensions", [])
    system_vars["industry_dimensions"] = "\n".join(
        f"- **{d['name']}**: {d['description']}" for d in dimensions
    )
    system_vars["industry_focus"] = industry_profile.get("analysis_focus", "")
    system_vars["industry_key_metrics"] = ", ".join(
        industry_profile.get("key_metrics", [])
    )

# 新增: 查询个股分析配置
stock_profile = db.stock_analysis_profiles.find_one(
    {"stock_symbol": stock_code}
)
if stock_profile:
    dimensions = stock_profile.get("analysis_dimensions", [])
    system_vars["stock_dimensions"] = "\n".join(
        f"- **{d['name']}**: {d['description']}" for d in dimensions
    )
    system_vars["stock_special_notes"] = stock_profile.get("special_notes", "")
```

---

### 3.2 AI 辅助提示词修改（Intelligent Prompt Modification）

#### 核心思路：Prompt Architect Agent

不取代手动编辑，而是**在手动编辑旁边加一个 AI 助手**，帮助用户：

1. **自然语言 → 提示词**：用户说"我想让基本面分析师更关注现金流"，AI 自动修改提示词
2. **分析质量反馈**：用户对分析报告说"这个分析太浅了"，AI 自动优化提示词
3. **行业知识生成**：AI 自动为新行业生成 `industry_analysis_profiles`

#### 3.2.1 交互模式

```
模式 A: 直接修改（前端模板编辑页面新增 AI 按钮）
┌──────────────────────────────────────────┐
│  [当前 system_prompt 编辑器]              │
│  ┌──────────────────────────────────────┐ │
│  │ 你是一位专业的市场分析师...           │ │
│  │ ...                                  │ │
│  └──────────────────────────────────────┘ │
│                                          │
│  💡 AI 助手: [输入你想要的修改方向]       │
│  ┌──────────────────────────────────────┐ │
│  │ "更关注行业龙头的竞争格局分析"        │ │
│  └──────────────────────────────────────┘ │
│  [✨ AI 生成修改建议]  [应用]  [放弃]     │
└──────────────────────────────────────────┘

模式 B: 分析后反馈优化
┌──────────────────────────────────────────┐
│  [分析报告查看页面]                       │
│                                          │
│  报告评价: ⭐⭐⭐☆☆                      │
│  改进建议: "基本面分析缺少现金流分析，     │
│           行业对比数据不够充分"            │
│                                          │
│  [🔧 根据反馈优化提示词]                  │
│  → AI 自动定位到相关 Agent 的提示词        │
│  → 生成优化建议 → 用户确认后应用          │
└──────────────────────────────────────────┘

模式 C: 自动生成行业配置
┌──────────────────────────────────────────┐
│  首次分析 "比亚迪"（汽车行业）            │
│                                          │
│  系统检测到：没有 "汽车" 行业的分析配置    │
│                                          │
│  💡 是否让 AI 自动生成汽车行业分析维度？   │
│  [✨ 自动生成]  [跳过，使用通用模板]       │
│                                          │
│  AI 生成结果：                            │
│  - 月销量数据 (critical)                  │
│  - 新能源渗透率 (high)                    │
│  - 产能利用率 (high)                      │
│  - ...                                   │
│  [保存] [编辑后保存] [放弃]               │
└──────────────────────────────────────────┘
```

#### 3.2.2 Prompt Architect API

```python
# 新增 API: POST /api/v1/templates/ai-optimize
{
    "template_id": "xxx",              # 要优化的模板 ID
    "instruction": "更关注现金流分析",   # 用户的自然语言指令
    "mode": "suggest"                   # suggest (建议) | apply (直接应用)
}

# 返回
{
    "original": { "system_prompt": "...", ... },
    "suggested": { "system_prompt": "...", ... },
    "changes_summary": "在分析要求中增加了自由现金流和经营性现金流分析维度",
    "diff": [...]                       # 变更详情
}
```

```python
# 新增 API: POST /api/v1/templates/ai-generate-industry
{
    "industry": "汽车",                # 行业名称
    "reference_stocks": ["002594.SZ"]  # 参考股票（可选）
}

# 返回
{
    "industry": "汽车",
    "analysis_dimensions": [...],
    "analysis_focus": "...",
    "key_metrics": [...]
}
```

#### 3.2.3 反馈闭环

```python
# 新增 API: POST /api/v1/analysis/feedback
{
    "task_id": "xxx",                  # 分析任务 ID
    "rating": 3,                       # 1-5 星评价
    "feedback": "基本面分析缺少现金流", # 改进建议
    "auto_optimize": true              # 是否自动优化提示词
}

# 系统行为:
# 1. 保存评价到 analysis_feedback 集合
# 2. 如果 auto_optimize=true:
#    - 分析 feedback 对应哪个 Agent 的提示词需要改进
#    - 调用 Prompt Architect 生成优化建议
#    - 返回优化建议让用户确认
```

---

## 四、实现优先级建议

### Phase 1: 上下文感知（低成本，高价值）

**预计工作量**: 2-3 天

1. 新建 `industry_analysis_profiles` 集合
2. 在 `_prepare_system_variables()` 中查询并注入行业维度
3. 在现有模板的 `analysis_requirements` 中添加 `{{industry_dimensions}}` 变量
4. 预置 10-15 个常见行业的分析配置（银行、白酒、半导体、新能源、医药等）

**效果**：分析银行股时，提示词自动包含 NIM、不良率等关键指标，分析报告质量立即提升。

### Phase 2: AI 生成行业配置（中等成本，高价值）

**预计工作量**: 3-5 天

1. 实现 `POST /api/v1/templates/ai-generate-industry` API
2. 首次分析某行业时，自动检测并提示生成行业配置
3. 前端增加行业配置管理页面

**效果**：用户分析任何行业的股票时，系统自动学习并积累行业知识。

### Phase 3: AI 辅助修改提示词（中等成本，中等价值）

**预计工作量**: 5-7 天

1. 实现 `POST /api/v1/templates/ai-optimize` API
2. 前端模板编辑页面增加 AI 助手按钮
3. 实现 Prompt Architect Agent

**效果**：降低提示词修改门槛，不懂提示词工程的用户也能优化分析质量。

### Phase 4: 反馈闭环（较高成本，长期价值）

**预计工作量**: 7-10 天

1. 实现分析报告评价系统
2. 实现反馈 → 提示词优化的自动闭环
3. 积累反馈数据，持续改进

**效果**：系统从用户反馈中持续学习，分析质量随使用越来越好。

---

## 五、与现有架构的关系

### 不需要改的

- ✅ `PromptTemplate` 数据模型 — 不需要新增字段
- ✅ `_get_prompt_from_template()` — 加载逻辑不变
- ✅ 模板优先级 — Debug > Workflow > User > System 不变
- ✅ 前端模板管理页面 — 手动编辑继续保留

### 需要扩展的

- 🔧 `_prepare_system_variables()` — 新增行业/个股维度注入
- 🔧 现有提示词模板内容 — 在 `analysis_requirements` 中加入 `{{industry_dimensions}}`
- 🆕 `industry_analysis_profiles` 集合 — 行业分析知识
- 🆕 `stock_analysis_profiles` 集合 — 个股分析知识
- 🆕 AI 提示词优化 API — Prompt Architect
- 🆕 分析反馈 API — 质量评价和闭环

### 与 v4.0 知识系统的关系

行业分析配置 (`industry_analysis_profiles`) 和个股分析配置 (`stock_analysis_profiles`) 本质上是**结构化的领域知识**。在 v4.0 的 Cognee 知识图谱落地后，这些配置可以：

- 从知识图谱中自动生成和更新
- 与用户的投资笔记、历史分析关联
- 形成"越用越懂你"的个性化分析体验

---

## 六、总结

| 维度 | 当前状态 | Phase 1 后 | Phase 4 后 |
|------|---------|-----------|-----------|
| 提示词修改 | 纯手动 | 纯手动 + 行业自动注入 | AI 辅助 + 自动反馈优化 |
| 行业适配 | 无 | 自动注入行业分析维度 | AI 自动学习新行业 |
| 个股适配 | 无 | 支持个股专属维度 | 从历史分析中自动积累 |
| 用户门槛 | 高（需要懂提示词） | 中（行业维度自动生效） | 低（自然语言修改） |
| 分析质量 | 通用水平 | 行业针对性提升 | 持续自我改进 |

**建议优先实施 Phase 1**：投入最小（2-3 天），效果最明显，且为后续 Phase 打好基础。
