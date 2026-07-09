# TradingAgents-CN v3.0 — Skill 自动生成系统设计文档

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 设计完成，待实现 |
| 日期 | 2026-02-21 |
| 作者 | TradingAgents-CN Pro Team |
| 前置文档 | [v2.3 Skill 机制评估](../v2.3/skill-mechanism-reassessment.md)、[v2.1 插件平台概念](../v2.1/plugin-platform-concept.md) |

---

## 1. 概述

### 1.1 背景

在 v2.3 阶段，我们评估了 OpenClaw 的 ClawHub 生态（9000+ Skills），发现：

- **~60%** 为纯提示词型（依赖 OpenClaw 内置能力如 `exec`、`web_search`，无法直接复用）
- **~20%** 为 Python 脚本（可直接执行）
- **~12%** 为 Shell/curl 脚本（可转换为 `GenericHttpTool`）
- **~8%** 为 JS/Node 脚本（需要转写或跳过）
- **金融/交易/A 股领域几乎空白**

结论：ClawHub 作为通用 Skill 来源的价值有限，**自建 Skill 生成能力是 v3.0 的核心方向**。

### 1.2 目标

构建一套**闭环的 Skill 生成-验证-迭代系统**，使用户能够通过自然语言描述需求，系统自动：

1. 通过多轮对话澄清需求（1-3 轮）
2. 检测并控制 Skill 边界（单一职责原则）
3. LLM 生成 Python 工具代码 + 元数据 + 测试用例
4. 静态验证（语法、安全、依赖、签名）
5. 沙箱执行验证（子进程隔离）
6. Judge LLM 评估输出质量（0-10 分）
7. 自动迭代修复（最多 3 轮）
8. 注册到 `ToolRegistry` 供 Agent 调用

### 1.3 与现有系统的关系

| 现有系统 | 本方案的集成方式 |
|---------|---------------|
| `ToolRegistry` (单例) | 新增 `register_external()` 方法，从 MongoDB 加载外部 Skill |
| `ToolMetadata` | 新增 `source` 字段标记来源：`builtin` / `generated` / `clawhub` |
| `ToolCategory` | 新增 `EXTERNAL = "external"` 类别 |
| `BaseAgent.load_tools_from_config()` | 扩展支持加载 `external_skills` 集合中的工具 |
| `ToolCallNormalizer.execute_tool_call()` | 外部 Skill 走 `SkillExecutor` 沙箱执行 |
| `BindingManager` | 支持外部 Skill 绑定到 Agent |
| `GenericHttpTool` | Shell/curl 类 Skill 转换为 HTTP 工具复用此机制 |
| `PromptTemplate` | Skill 生成的系统提示词走现有模板管理 |

### 1.4 不在本文档范围内

- OpenClaw 深度集成（ClawHub 仅作辅助参考，不是主要 Skill 来源）
- Souls 人格模板集成（后期考虑）
- 前端完整 UI 实现（本文档只定义交互规范和 API）

---

## 2. 系统架构总览

### 2.1 完整管线

```
用户输入需求（自然语言）
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  阶段 1: 需求沟通（RequirementAnalyzer）                   │
│  ├── ClarityAnalyzer: 评估需求清晰度 (1-5分)              │
│  ├── BoundaryDetector: 检测是否越过 Skill 边界             │
│  ├── 多轮对话: 1-3 轮需求澄清                             │
│  └── 输出: 锁定的 SkillSpec（用户已确认）                  │
├──────────────────────────────────────────────────────────┤
│  阶段 2: 代码生成（CodeGenerator）                         │
│  ├── 模板检索: 从已有 Skill 模板库匹配参考代码              │
│  ├── LLM 生成: Python 函数代码 + ToolMetadata + 测试用例   │
│  └── 输出: GeneratedCode（代码 + 元数据 + 测试）           │
├──────────────────────────────────────────────────────────┤
│  阶段 3: 静态验证（StaticValidator）                       │
│  ├── ast.parse() 语法检查                                 │
│  ├── 安全扫描（黑名单检测: os.system, subprocess 等）       │
│  ├── 依赖检查（import 白名单验证）                         │
│  └── 签名一致性（函数参数 vs ToolMetadata 参数）            │
├──────────────────────────────────────────────────────────┤
│  阶段 4: 沙箱执行（SandboxRunner）                         │
│  ├── 构造测试输入（从 SkillSpec.test_input）                │
│  ├── 子进程执行（timeout=30s, 内存限制）                    │
│  └── 捕获 stdout + return value                           │
├──────────────────────────────────────────────────────────┤
│  阶段 5: 输出评估（OutputEvaluator）                       │
│  ├── 基础检查（非空、JSON 合法、字段完整）— 零成本           │
│  ├── Judge LLM 深度评估（真实性、相关性、质量）— 调用 LLM    │
│  └── 输出: 评分 (0-10) + 问题列表 + 修复建议               │
├──────────────────────────────────────────────────────────┤
│  阶段 6: 迭代决策（IterationController）                   │
│  ├── 评分 >= 7 → ✅ 通过，注册上线                         │
│  ├── 评分 < 7 且 迭代 < 3 → 🔄 带反馈重新生成              │
│  └── 评分 < 7 且 迭代 >= 3 → ❌ 标记失败，人工介入          │
└──────────────────────────────────────────────────────────┘
    │
    ▼
┌──────────────────────────────────────────────────────────┐
│  注册上线                                                 │
│  ├── 存入 MongoDB external_skills 集合                     │
│  ├── 注册到 ToolRegistry（运行时可调用）                    │
│  └── 可通过 BindingManager 绑定到指定 Agent                │
└──────────────────────────────────────────────────────────┘
```

### 2.2 核心模块分布

```
core/tools/external/                    # 新增目录
├── __init__.py
├── requirement_analyzer.py            # 阶段1: 需求分析器
├── boundary_detector.py               # 阶段1: 边界检测器

---

## 3. 阶段 1: 需求沟通（RequirementAnalyzer）

### 3.1 设计理念

用户给出的需求通常是模糊的自然语言，直接交给 LLM 生成代码会导致：
- 数据源选错（东方财富 vs 新浪 vs 财联社？）
- 参数缺失（只要A股还是也要港股？）
- 输出格式不对（Agent 无法解析）
- 功能越界（把分析逻辑也塞进了 Skill）

因此需要 **多轮对话式需求澄清**，在生成代码之前把需求锁定。

### 3.2 清晰度评估

AI 首先评估需求的清晰程度，决定需要几轮对话：

| 清晰度 | 分值 | 对话轮数 | 例子 |
|--------|------|---------|------|
| HIGH | 4-5/5 | 1 轮（直接出规格确认） | "用 AKShare 获取北向资金数据，按日期查，返回 JSON" |
| MEDIUM | 3/5 | 2 轮（技术细化 + 确认） | "获取某只股票的最新新闻" |
| LOW | 1-2/5 | 3 轮（完整流程） | "获取股票新闻" |

```python
class ClarityLevel(str, Enum):
    HIGH = "high"       # 4-5分，1轮确认
    MEDIUM = "medium"   # 3分，2轮
    LOW = "low"         # 1-2分，3轮完整流程

class RequirementAnalyzer:
    """需求分析器 — 多轮对话式需求澄清"""

    async def analyze_clarity(self, user_input: str) -> ClarityLevel:
        """评估需求清晰度"""
        prompt = """
评估以下需求描述的清晰度，给出 1-5 分：
- 5分: 数据源、参数、输出格式全部明确
- 4分: 大方向明确，个别细节需确认
- 3分: 知道要做什么，但缺少关键细节
- 2分: 方向模糊，需要大量澄清
- 1分: 完全不清楚要做什么

需求: {user_input}

输出格式: {{"score": 3, "reason": "..."}}
"""
        result = await self.llm.invoke(prompt.format(user_input=user_input))
        score = result["score"]
        if score >= 4:
            return ClarityLevel.HIGH
        elif score >= 3:
            return ClarityLevel.MEDIUM
        else:
            return ClarityLevel.LOW
```

### 3.3 三轮对话流程

#### 第 1 轮: 初步理解 — "我听懂了吗？"

AI 做三件事：**复述理解 → 拆解功能点 → 主动提问**

**示例交互：**

> **用户:** "我需要一个工具能获取股票相关新闻"
>
> **AI 回复:**
>
> 我理解你需要一个**股票新闻获取工具**。以下是我的理解，请确认和补充：
>
> | # | 功能 | 我的理解 | 需要你确认 |
> |---|------|---------|-----------|
> | 1 | 目标市场 | A 股（沪深） | 是否也需要港股/美股？ |
> | 2 | 数据源 | 东方财富（免费、数据全） | 有偏好的数据源吗？ |
> | 3 | 输入参数 | 股票代码 + 新闻条数 | 是否需要按日期范围筛选？ |
> | 4 | 返回字段 | 标题、链接、时间、来源 | 是否需要新闻正文/摘要？ |
> | 5 | 调用方式 | 按需查询 | 还是需要定时自动抓取？ |
> | 6 | 使用场景 | 供 news_analyst Agent 用 | 还是前端直接展示？ |
>
> **❓ 我还需要确认：**
> - 只需要财经新闻，还是也包括公告、研报？
> - 对新闻的时效性要求如何？

#### 第 2 轮: 技术细化 — "具体怎么做？"

用户确认大方向后，AI 整理技术方案，**给出推荐方案让用户选**：

> **AI 回复:**
>
> **🔧 技术方案**
>
> **数据源 1: 东方财富** — 移动端 API，无需 Key，字段全
> **数据源 2: 财联社快讯** — 实时性强，纯文本
>
> | 选项 | 方案 A（推荐） | 方案 B |
> |------|--------------|--------|
> | 数据源关系 | **合并为一个工具** | 拆成两个独立工具 |
> | 失败处理 | **自动切换** | 直接报错 |
> | 返回格式 | **统一 JSON** | 各自不同格式 |
>
> 不确定的话选方案 A 就行。

#### 第 3 轮: 规格确认 — "这就是最终版，确认吗？"

AI 输出完整的**结构化需求规格书**（SkillSpec），用户确认后锁定：

```
📄 工具规格书

基本信息
- 工具 ID: get_stock_news_combined
- 名称: 股票新闻聚合
- 分类: news
- 使用者: news_analyst Agent

输入参数
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| stock_code | string | ✅ | A 股代码，如 "600519" |
| source | string | ❌ | "eastmoney" / "cls" / "all"，默认 "all" |
| limit | integer | ❌ | 返回条数，默认 10 |

输出格式
[{"title": "...", "summary": "...", "url": "...",
  "publish_time": "...", "source": "...", "source_media": "..."}]

行为规则
- 只返回当天新闻
- source="all" 时合并两个源，按时间倒序
- 单个源失败自动切换，两个都失败才报错

测试用例
- 输入: {"stock_code": "600519", "limit": 5}
- 期望: ≥1 条新闻，每条含 title/summary/url/publish_time/source
```

### 3.4 对话状态管理

```python
class SessionStatus(str, Enum):
    GATHERING = "gathering"      # 收集需求中
    CONFIRMED = "confirmed"      # 规格已确认
    GENERATING = "generating"    # 代码生成中
    COMPLETED = "completed"      # 完成
    FAILED = "failed"            # 失败

class ConversationRound(BaseModel):
    """对话轮次"""
    round_number: int
    ai_message: str              # AI 的提问/总结
    user_response: str           # 用户的回答
    extracted_info: dict         # 从回答中提取的结构化信息
    spec_updates: dict           # 本轮对 SkillSpec 的增量更新

class SkillCreationSession(BaseModel):
    """Skill 创建会话"""
    id: str                              # 会话 ID
    user_id: str                         # 用户 ID
    status: SessionStatus                # 会话状态
    rounds: List[ConversationRound]      # 对话历史
    current_round: int                   # 当前轮次
    clarity_level: ClarityLevel          # 需求清晰度
    spec: Optional[SkillSpec]            # 渐进式构建的规格
    spec_confirmed: bool                 # 用户是否已确认
    generation_result: Optional[dict]    # 生成结果
    created_at: datetime
    updated_at: datetime
```

---

## 4. Skill 边界原则

### 4.1 核心原则：一个 Skill = 一个数据操作

```
✅ 一个 Skill 应该做的事（单一数据操作）:
├── 从一个数据源获取数据
├── 对数据做格式化（JSON 输出）
├── 基础过滤和排序（按日期、条数）
├── 错误处理和重试
└── 代码通常 < 100 行

❌ 一个 Skill 不应该做的事:
├── 调用 LLM（那是 Agent 的事）
├── 组合多个数据源（拆成多个 Skill，Agent 来组合）
├── 包含业务判断逻辑（"如果涨幅>5% 就..."）
├── 生成结论或建议（那是 Agent/Workflow 的事）
├── 代码超过 200 行（说明做的事太多了）
└── 需要多步骤串联（那是 Workflow 的事）
```

### 4.2 三层架构边界

| 层级 | 职责 | 边界 | 例子 |
|------|------|------|------|
| **Skill（工具）** | 获取一类数据 / 执行一个操作 | 不含业务判断、不调用 LLM | `get_eastmoney_news(code)` → 新闻列表 |
| **Agent（智能体）** | 调用多个 Skill + LLM 分析 | 专注一个分析维度 | `news_analyst` 调用新闻 Skill → LLM 分析 |
| **Workflow（工作流）** | 编排多个 Agent 协作 | 任务流程编排 | `综合研判` 编排多 Agent → 输出建议 |

### 4.3 复杂度评分标准

| 分数 | 描述 | 处理方式 |
|------|------|---------|
| **1** | 单数据源、单操作 | ✅ 直接生成 |
| **2** | 单数据源、带筛选/排序 | ✅ 直接生成 |
| **3** | 多参数组合、需要数据转换 | ⚠️ 确认后生成 |
| **4** | 多数据源或含简单逻辑 | ⚠️ 建议拆分 |
| **5** | 含分析/决策/多步串联 | ❌ 强制拆分 |

### 4.4 边界检测器

```python
class BoundaryDetector:
    """检测需求是否越过 Skill 边界"""

    ANALYSIS_KEYWORDS = ["分析", "判断", "评估", "建议", "推荐",
                         "预测", "总结", "对比分析"]
    MULTI_SOURCE_KEYWORDS = ["同时获取", "结合", "综合", "汇总多个"]
    DECISION_KEYWORDS = ["如果...就", "当...时", "买入", "卖出",
                         "操作建议", "决策"]

    async def check_boundary(self, user_input: str) -> BoundaryResult:
        """
        返回:
        - within_boundary: 是否在 Skill 范围内
        - complexity_score: 1-5 复杂度评分
        - violations: 越界的具体问题
        - suggested_skills: 建议拆分成的多个 Skill
        - already_covered_by: 已有的 Agent/Workflow 可以覆盖的部分
        """
        prompt = f"""
分析以下需求，判断它是否适合作为单个 Skill（数据获取工具）：

需求: {user_input}

Skill 的边界:
- ✅ 只做数据获取和格式化
- ❌ 不做 AI 分析（那是 Agent 的事）
- ❌ 不做多源数据组合（拆成多个 Skill）
- ❌ 不做业务决策（那是 Workflow 的事）

输出 JSON:
{{
  "within_boundary": true/false,
  "complexity_score": 1-5,
  "violations": ["越界点1", "越界点2"],
  "suggested_skills": [
    {{"name": "skill_name", "description": "只做什么", "type": "skill"}}
  ],
  "already_covered_by": [
    {{"name": "news_analyst", "type": "agent", "reason": "情感分析已有"}}
  ]
}}
"""
        return await self.llm.invoke(prompt)
```

### 4.5 越界处理策略

当 BoundaryDetector 检测到越界时，AI 不是拒绝，而是 **帮用户拆分**：

```
用户: "获取股票新闻，分析情感，结合行情给出买入建议"
                        │
                        ▼
         BoundaryDetector: complexity_score = 5
                        │
                        ▼
         AI 自动拆分建议:
         ┌──────────────────────────────────────┐
         │ Skill: get_stock_news   → 获取新闻    │  ← 需要生成
         │ Skill: get_stock_quotes → 获取行情    │  ← 需要生成
         │ Agent: news_analyst     → 情感分析    │  ← 已有
         │ Agent: market_analyst   → 趋势分析    │  ← 已有
         │ Workflow: 综合研判       → 编排决策    │  ← 已有
         └──────────────────────────────────────┘
         AI: "其中 Agent 和 Workflow 已有，我只需生成数据获取的 Skill"
```

---

## 5. 阶段 2: 代码生成（CodeGenerator）

### 5.1 设计目标

从锁定的 SkillSpec 生成**三样东西**（不只是代码）：

| 生成物 | 作用 | 格式 |
|--------|------|------|
| **函数代码** | 实际的 Python 实现 | `def func_name(param1, param2) -> dict` |
| **ToolMetadata** | 工具元数据 | 兼容现有 `core/tools/config.py` 格式 |
| **测试用例** | 验证代码正确性 | `test_input` + `expected_output_schema` |

### 5.2 模板参考体系

生成代码前，CodeGenerator 从**两个来源**检索参考模板：

```
模板参考来源
├── ① 内置工具（core/tools/implementations/）—— 编码规范样本
│   ├── 按类别匹配: news → stock_news.py, market → stock_market_data.py
│   ├── 按数据源匹配: akshare → AKShare 类工具, api → HTTP 类工具
│   └── 按返回格式匹配: string → Markdown 报告类, dict → 结构化数据类
│
└── ② 已生成 Skill（external_skills 集合）—— 同类成功案例
    └── 按类别 + 数据源相似度检索
```

#### 5.2.1 内置工具模板库

内置工具是经过验证的"最佳实践"，从中提取 **7 种编码模式** 供 LLM 学习：

| 模式 | 提取自 | 描述 | 示例 |
|------|--------|------|------|
| **双装饰器** | 所有统一工具 | `@tool` + `@register_tool()` 双装饰器 | `stock_news.py` |
| **类型注解** | 所有工具 | `Annotated[str, "描述"]` 参数注解 | `stock_market_data.py` |
| **Markdown 返回** | 数据获取类工具 | 返回 `str` 格式的 Markdown 报告 | `financial_tools.py` |
| **结构化返回** | 内部处理类工具 | 返回 `Dict[str, Any]` 结构化数据 | `trade_info.py` |
| **错误降级** | 所有在线工具 | `try/except` + `logger.error` + 降级消息 | `stock_fundamentals.py` |
| **多源降级** | 新闻/行情工具 | MongoDB → AKShare → 外部 API 多层降级 | `stock_news.py` |
| **市场检测** | 统一入口工具 | 自动识别 A股/港股/美股 分支处理 | `stock_market_data.py` |

#### 5.2.2 模板匹配算法

```python
class CodeGenerator:
    """代码生成器 — 从 SkillSpec 生成可执行代码"""

    # 内置工具 → 类别映射（预加载，不需要每次查数据库）
    BUILTIN_TEMPLATES = {
        "news": {
            "file": "core/tools/implementations/news/stock_news.py",
            "tool_id": "get_stock_news_unified",
            "patterns": ["multi_source_fallback", "markdown_return", "market_detection"],
            "description": "新闻获取工具：多数据源降级、Markdown 返回、市场自动检测",
        },
        "market": {
            "file": "core/tools/implementations/market/stock_market_data.py",
            "tool_id": "get_stock_market_data_unified",
            "patterns": ["market_detection", "date_expansion", "markdown_return"],
            "description": "行情数据工具：市场检测、日期自动扩展、Markdown 返回",
        },
        "fundamentals": {
            "file": "core/tools/implementations/fundamentals/financial_tools.py",
            "tool_id": "get_income_analysis",
            "patterns": ["cache_or_api", "markdown_return", "period_param"],
            "description": "财务分析工具：缓存/API 降级、多期数据、Markdown 报告",
        },
        "social": {
            "file": "core/tools/implementations/social/stock_sentiment.py",
            "tool_id": "get_stock_sentiment_unified",
            "patterns": ["multi_source_fallback", "markdown_return"],
            "description": "社交情绪工具：多源降级、Markdown 返回",
        },
        "trade_review": {
            "file": "core/tools/implementations/trade_review/trade_info.py",
            "tool_id": "build_trade_info",
            "patterns": ["dict_return", "internal_data", "statistics"],
            "description": "交易复盘工具：Dict 返回、内部数据处理、统计计算",
        },
        "utility": {
            "file": "core/tools/implementations/fundamentals/financial_tools.py",
            "tool_id": "get_income_analysis",
            "patterns": ["cache_or_api", "markdown_return"],
            "description": "通用工具：缓存/API 模式",
        },
    }

    def get_builtin_template(self, spec: SkillSpec) -> dict:
        """根据 SkillSpec 类别选择最匹配的内置工具模板"""
        # 1. 按类别精确匹配
        template = self.BUILTIN_TEMPLATES.get(spec.category)

        # 2. 按数据源特征匹配（如果类别不匹配）
        if not template:
            if "akshare" in spec.data_source.lower():
                template = self.BUILTIN_TEMPLATES["market"]
            elif "api" in spec.data_source.lower() or "http" in spec.data_source.lower():
                template = self.BUILTIN_TEMPLATES["news"]
            else:
                template = self.BUILTIN_TEMPLATES["utility"]  # 默认

        # 3. 读取模板文件代码（启动时预加载到内存）
        return {
            "code": self._load_template_code(template["file"]),
            "patterns": template["patterns"],
            "description": template["description"],
        }

    def _load_template_code(self, file_path: str) -> str:
        """加载模板文件代码（去掉业务逻辑，只保留结构）"""
        # 实际实现中会缓存到内存
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    async def find_similar_skills(self, spec: SkillSpec) -> List[dict]:
        """从已有 external_skills 集合中检索相似的已生成 Skill"""
        query = {
            "status": "active",
            "$or": [
                {"metadata.category": spec.category},
                {"metadata.description": {"$regex": spec.data_source, "$options": "i"}}
            ]
        }
        return await self.db.external_skills.find(query).limit(3).to_list(3)
```

#### 5.2.3 模板注入策略

CodeGenerator 生成 Prompt 时，将模板信息注入为两部分：

1. **编码规范摘要**（从内置工具中提取的模式规则，始终注入）
2. **参考代码片段**（从内置工具或已生成 Skill 中选取，按相似度注入）

```python
# 编码规范（始终注入到 Prompt）
CODING_PATTERNS = """
## 编码规范（必须遵循）

### 装饰器
- 使用 `@register_tool()` 装饰器注册工具
- 如需 Function Calling，额外添加 `@tool` 装饰器（@tool 在上，@register_tool 在下）

### 参数注解
- 使用 `Annotated[type, "中文描述"]` 为每个参数添加说明
- 示例: `ticker: Annotated[str, "股票代码（如 600519、000001）"]`

### 错误处理
- 所有外部调用必须包在 try/except 中
- 失败时返回描述性错误信息，不要抛出异常
- 使用 logger.error() 记录错误详情

### 返回格式
- 数据获取类工具: 返回 str (Markdown 格式报告)
- 数据处理类工具: 返回 Dict[str, Any] (结构化数据)
- 失败时: 返回 {"error": "描述", "data": []} 或 "❌ 获取失败: {error}"

### 日志
- 使用 logging 模块，emoji 前缀: 📊📰🇨🇳✅❌⚠️
- 入口日志: logger.info(f"📊 [工具名] 开始处理: {param}")
- 错误日志: logger.error(f"❌ 操作失败: {e}")

### 导入
- 标准库 import 放在顶部
- 第三方库放在函数内部 import（延迟加载，减少启动开销）
- 项目内部模块放在函数内部 import
"""
```

### 5.3 LLM 生成 Prompt

```python
    async def generate(self, spec: SkillSpec) -> GeneratedCode:
        """生成代码 — 综合内置模板 + 已生成 Skill 作为参考"""

        # 1. 获取内置工具模板（编码规范 + 参考代码）
        builtin_template = self.get_builtin_template(spec)

        # 2. 获取已生成的相似 Skill（如果有）
        similar_skills = await self.find_similar_skills(spec)

        # 3. 构建参考代码部分
        reference_section = self._build_reference_section(
            builtin_template, similar_skills
        )

        prompt = f"""
你是一个 Python 工具生成器。根据以下规格生成一个数据获取工具。

{CODING_PATTERNS}

## 规格
- 工具名: {spec.name}
- 工具 ID: {spec.tool_id}
- 描述: {spec.description}
- 数据源: {spec.data_source}
- 参数: {json.dumps(spec.parameters, ensure_ascii=False)}
- 期望输出: {json.dumps(spec.expected_output, ensure_ascii=False)}
- 行为规则: {spec.constraints}

{reference_section}

## 约束
1. 只能使用以下库: requests, json, re, datetime, pandas, akshare, bs4, lxml, aiohttp
2. 函数签名必须与参数定义一致，使用 Annotated 类型注解
3. 返回值必须是 dict 或 list[dict]，可 JSON 序列化
4. 必须包含错误处理（try/except），失败返回 {{"error": "描述", "data": []}}
5. 不允许: os.system(), subprocess, eval(), exec(), 文件写入操作
6. 代码不超过 150 行
7. 必须遵循上面"编码规范"中的装饰器、注解、日志、错误处理模式

## 输出格式（严格 JSON）
{{
  "code": "def {spec.tool_id}(...):\\n    ...",
  "metadata": {{
    "id": "{spec.tool_id}",
    "name": "{spec.display_name}",
    "description": "...",
    "category": "{spec.category}",
    "parameters": [...],
    "return_type": "..."
  }},
  "test_cases": [
    {{
      "input": {json.dumps(spec.test_input)},
      "expected_fields": [...],
      "expected_type": "list"
    }}
  ]
}}
"""
        result = await self.llm.invoke(prompt)
        return GeneratedCode(**result)

    def _build_reference_section(
        self, builtin_template: dict, similar_skills: List[dict]
    ) -> str:
        """构建 Prompt 中的参考代码部分"""
        sections = []

        # 内置工具参考（始终包含，截取关键片段，控制 token 用量）
        if builtin_template:
            code_snippet = self._extract_key_snippet(
                builtin_template["code"], max_lines=60
            )
            sections.append(f"""
## 参考：内置工具代码风格
以下是系统中已验证的同类工具代码，请严格模仿其编码风格：
- 使用的模式: {', '.join(builtin_template['patterns'])}
- 说明: {builtin_template['description']}

```python
{code_snippet}
```
""")

        # 已生成 Skill 参考（如果有匹配）
        if similar_skills:
            skill = similar_skills[0]
            sections.append(f"""
## 参考：已有相似 Skill
以下是之前成功生成并通过验证的类似工具：

```python
{skill['code'][:2000]}
```
""")

        return "\n".join(sections) if sections else ""

    def _extract_key_snippet(self, code: str, max_lines: int = 60) -> str:
        """从内置工具代码中提取关键片段（装饰器 + 函数签名 + 错误处理结构）"""
        lines = code.split("\n")
        # 优先提取: import 区、装饰器、函数签名、前几行逻辑
        key_sections = []
        in_function = False
        func_lines = 0
        for line in lines:
            if line.startswith("import ") or line.startswith("from "):
                key_sections.append(line)
            elif "@tool" in line or "@register_tool" in line:
                in_function = True
                key_sections.append(line)
            elif in_function:
                key_sections.append(line)
                func_lines += 1
                if func_lines >= max_lines - 10:
                    key_sections.append("    # ... (后续业务逻辑省略)")
                    break
        return "\n".join(key_sections[:max_lines])
```

### 5.4 数据模型

```python
class GeneratedCode(BaseModel):
    """代码生成结果"""
    code: str                    # Python 函数代码
    metadata: dict               # ToolMetadata 格式的元数据
    test_cases: List[dict]       # 测试用例
    generation_model: str        # 生成使用的 LLM 模型
    generation_time: float       # 生成耗时（秒）

class SkillSpec(BaseModel):
    """Skill 规格书（需求沟通的输出）"""
    tool_id: str                 # 如 "get_eastmoney_news"
    display_name: str            # 如 "东方财富个股新闻"
    description: str             # 功能描述
    category: str                # 分类: news, market, fundamentals 等
    data_source: str             # 数据源标识
    parameters: List[dict]       # 参数列表 [{name, type, required, default, description}]
    expected_output: dict        # 期望输出 {type, fields, description}
    constraints: List[str]       # 行为约束
    test_input: dict             # 测试输入
    test_expected: dict          # 测试期望（至少要满足的条件）
```


---

## 6. 阶段 3: 静态验证（StaticValidator）

### 6.1 四项检查

静态验证**零 LLM 开销**，纯程序化检查，毫秒级完成。

| 检查项 | 方法 | 失败处理 |
|--------|------|---------|
| **语法检查** | `ast.parse()` | 直接回退到代码生成重试 |
| **安全扫描** | AST 遍历黑名单调用 | 阻断，附安全违规详情 |
| **依赖检查** | 解析 import，对比白名单 | 阻断，附非法 import 列表 |
| **签名一致** | 函数参数 vs ToolMetadata 参数 | 回退重试，附不一致描述 |

### 6.2 实现

```python
class StaticValidator:
    """静态验证器 — 语法/安全/依赖/签名检查"""

    # 安全黑名单：禁止调用的函数/模块
    SECURITY_BLACKLIST = [
        "os.system", "os.popen", "os.exec", "os.spawn",
        "subprocess.call", "subprocess.run", "subprocess.Popen",
        "eval", "exec", "compile", "__import__",
        "open",          # 禁止文件操作（写入）
        "shutil.rmtree", "os.remove", "os.rmdir",
    ]

    # import 白名单：只允许这些库
    IMPORT_WHITELIST = [
        "requests", "aiohttp", "json", "re", "datetime", "time",
        "pandas", "numpy", "akshare", "bs4", "lxml",
        "urllib.parse", "hashlib", "math", "collections",
        "typing", "dataclasses", "enum",
    ]

    def validate(self, generated: GeneratedCode) -> ValidationResult:
        """执行全部静态检查"""
        errors = []

        # 1. 语法检查
        try:
            tree = ast.parse(generated.code)
        except SyntaxError as e:
            return ValidationResult(passed=False, errors=[f"语法错误: {e}"])

        # 2. 安全扫描
        security_issues = self._scan_security(tree)
        errors.extend(security_issues)

        # 3. 依赖检查
        import_issues = self._check_imports(tree)
        errors.extend(import_issues)

        # 4. 签名一致性
        sig_issues = self._check_signature(tree, generated.metadata)
        errors.extend(sig_issues)

        return ValidationResult(
            passed=len(errors) == 0,
            errors=errors,
            warnings=self._collect_warnings(tree)
        )

    def _scan_security(self, tree: ast.AST) -> List[str]:
        """遍历 AST 检查黑名单调用"""
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                if call_name in self.SECURITY_BLACKLIST:
                    issues.append(f"安全违规: 禁止调用 {call_name}")
            # 特殊检查: open() 只允许读模式
            if isinstance(node, ast.Call) and self._get_call_name(node) == "open":
                if not self._is_read_only_open(node):
                    issues.append("安全违规: open() 只允许只读模式")
        return issues

    def _check_imports(self, tree: ast.AST) -> List[str]:
        """检查 import 是否在白名单内"""
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                module = node.module if isinstance(node, ast.ImportFrom) else None
                names = [alias.name for alias in node.names]
                for name in ([module] if module else names):
                    root_module = name.split(".")[0] if name else ""
                    if root_module and root_module not in self.IMPORT_WHITELIST:
                        issues.append(f"非法依赖: {name} (不在白名单中)")
        return issues

    def _check_signature(self, tree: ast.AST, metadata: dict) -> List[str]:
        """检查函数签名与 ToolMetadata 参数定义是否一致"""
        issues = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_params = [arg.arg for arg in node.args.args]
                meta_params = [p["name"] for p in metadata.get("parameters", [])]
                if set(func_params) != set(meta_params):
                    issues.append(
                        f"签名不一致: 函数参数 {func_params} vs 元数据参数 {meta_params}"
                    )
                break  # 只检查第一个函数定义
        return issues

class ValidationResult(BaseModel):
    """验证结果"""
    passed: bool
    errors: List[str] = []
    warnings: List[str] = []
```

---

## 7. 阶段 4: 沙箱执行（SandboxRunner）

### 7.1 隔离策略

使用 **子进程 + 超时 + 资源限制** 进行隔离执行，不使用 Docker（过重）：

| 措施 | 实现 | 目的 |
|------|------|------|
| **进程隔离** | `subprocess.Popen` | 崩溃不影响主进程 |
| **超时控制** | 30 秒 hard timeout | 防止死循环/阻塞 |
| **输出限制** | stdout 截断 1MB | 防止刷屏 |
| **网络限制** | 暂不限制（需要访问 API） | 后期可加代理层 |
| **文件隔离** | 临时目录 + 清理 | 防止写入系统文件 |

### 7.2 实现

```python
class SandboxRunner:
    """沙箱执行器 — 在子进程中安全执行生成的代码"""

    TIMEOUT_SECONDS = 30
    MAX_OUTPUT_BYTES = 1 * 1024 * 1024  # 1MB

    async def run(self, generated: GeneratedCode) -> ExecutionResult:
        """在沙箱中执行代码"""
        test_case = generated.test_cases[0]
        test_input = test_case["input"]

        # 构造执行脚本
        runner_script = self._build_runner_script(
            code=generated.code,
            func_name=generated.metadata["id"],
            test_input=test_input,
        )

        # 写入临时文件
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as f:
            f.write(runner_script)
            script_path = f.name

        try:
            # 子进程执行
            proc = await asyncio.create_subprocess_exec(
                sys.executable, script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=tempfile.gettempdir(),
            )
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=self.TIMEOUT_SECONDS
                )
            except asyncio.TimeoutError:
                proc.kill()
                return ExecutionResult(
                    success=False,
                    error="执行超时 (30秒)",
                    exit_code=-1,
                )

            stdout_text = stdout.decode("utf-8", errors="replace")[:self.MAX_OUTPUT_BYTES]
            stderr_text = stderr.decode("utf-8", errors="replace")[:self.MAX_OUTPUT_BYTES]

            if proc.returncode != 0:
                return ExecutionResult(
                    success=False,
                    error=stderr_text,
                    exit_code=proc.returncode,
                    stdout=stdout_text,
                )

            # 解析输出
            output = json.loads(stdout_text)
            return ExecutionResult(
                success=True,
                output=output,
                exit_code=0,
                execution_time=output.get("_execution_time", 0),
            )
        finally:
            os.unlink(script_path)

    def _build_runner_script(self, code: str, func_name: str, test_input: dict) -> str:
        """构造执行脚本，注入计时和输出捕获"""
        return f'''
import json, time, sys
{code}

if __name__ == "__main__":
    start = time.time()
    try:
        result = {func_name}(**{json.dumps(test_input)})
        elapsed = time.time() - start
        output = {{"success": True, "data": result, "_execution_time": elapsed}}
    except Exception as e:
        elapsed = time.time() - start
        output = {{"success": False, "error": str(e), "_execution_time": elapsed}}
    print(json.dumps(output, ensure_ascii=False, default=str))
'''

class ExecutionResult(BaseModel):
    """执行结果"""
    success: bool
    output: Optional[dict] = None
    error: Optional[str] = None
    exit_code: int = 0
    stdout: Optional[str] = None
    execution_time: float = 0.0
```

---

## 8. 阶段 5: 输出评估（OutputEvaluator）

### 8.1 双层评估

| 层级 | 方法 | 成本 | 能力 |
|------|------|------|------|
| **基础检查** | 程序化校验 | 零 | 非空、JSON 合法、字段完整、类型正确 |
| **Judge LLM** | 深度语义评估 | 1 次 LLM 调用 | 数据真实性、相关性、质量 |

只有通过基础检查的才会调 Judge LLM，避免浪费 LLM 调用。

### 8.2 基础检查（零成本）

```python
class OutputEvaluator:
    """输出评估器 — 基础检查 + Judge LLM 深度评估"""

    def basic_check(self, exec_result: ExecutionResult, spec: SkillSpec) -> BasicCheckResult:
        """纯程序化的基础检查"""
        issues = []

        # 检查 1: 执行是否成功
        if not exec_result.success:
            return BasicCheckResult(passed=False, issues=[f"执行失败: {exec_result.error}"])

        data = exec_result.output.get("data")

        # 检查 2: 返回值非空
        if data is None or data == [] or data == {}:
            issues.append("返回值为空")

        # 检查 3: 类型正确
        expected_type = spec.expected_output.get("type", "")
        if "list" in expected_type and not isinstance(data, list):
            issues.append(f"期望 list，实际 {type(data).__name__}")
        elif "dict" in expected_type and not isinstance(data, dict):
            issues.append(f"期望 dict，实际 {type(data).__name__}")

        # 检查 4: 字段完整
        expected_fields = spec.expected_output.get("fields", [])
        if isinstance(data, list) and len(data) > 0:
            first_item = data[0]
            missing = [f for f in expected_fields if f not in first_item]
            if missing:
                issues.append(f"缺少字段: {missing}")
        elif isinstance(data, dict):
            missing = [f for f in expected_fields if f not in data]
            if missing:
                issues.append(f"缺少字段: {missing}")

        return BasicCheckResult(passed=len(issues) == 0, issues=issues)
```

### 8.3 Judge LLM 深度评估

```python
    async def judge_evaluate(
        self, spec: SkillSpec, exec_result: ExecutionResult
    ) -> JudgeResult:
        """使用 Judge LLM 对输出质量打分"""
        prompt = f"""
你是一个数据质量评估专家。请评估以下工具的执行输出。

## 工具规格
- 名称: {spec.display_name}
- 描述: {spec.description}
- 数据源: {spec.data_source}
- 期望输出: {json.dumps(spec.expected_output, ensure_ascii=False)}

## 测试输入
{json.dumps(spec.test_input, ensure_ascii=False)}

## 实际输出
{json.dumps(exec_result.output.get("data"), ensure_ascii=False, default=str)[:2000]}

## 评分维度（每项 0-10 分）
1. **可执行性** (executability): 是否成功执行、无异常
2. **数据真实性** (authenticity): 数据是否像真实数据（非伪造/随机）
3. **完整性** (completeness): 字段是否齐全、数据量是否合理
4. **相关性** (relevance): 数据是否与请求相关
5. **格式规范** (format): JSON 结构是否规范、字段命名是否合理

## 输出格式（严格 JSON）
{{
  "scores": {{
    "executability": 8,
    "authenticity": 7,
    "completeness": 9,
    "relevance": 8,
    "format": 9
  }},
  "overall_score": 8.2,
  "issues": ["数据时间字段格式不统一"],
  "suggestions": ["建议统一 publish_time 为 ISO 8601 格式"],
  "verdict": "pass"  // "pass" (>=7分) 或 "fail" (<7分)
}}
"""
        return await self.llm.invoke(prompt)

    PASS_THRESHOLD = 7.0  # 总分 >= 7 视为通过
```

---

## 9. 阶段 6: 迭代控制（IterationController）

### 9.1 决策逻辑

```
                      生成代码
                         │
                         ▼
              ┌─── 静态验证 ───┐
              │               │
            通过             失败
              │               │
              ▼               ▼
         沙箱执行      带错误信息重新生成
              │           (迭代+1)
              ▼
         输出评估
              │
    ┌─────┬──┴──┬─────┐
    │     │     │     │
  >=7分  <7分  <7分  <7分
    │   迭代<3 迭代=3  安全违规
    │     │     │     │
    ▼     ▼     ▼     ▼
  ✅通过 🔄重试 ❌失败 🚫阻断
  注册   带反馈  人工   终止
  上线   重生成  介入
```

### 9.2 实现

```python
class IterationController:
    """迭代控制器 — 管理 生成→验证→评估→重试 循环"""

    MAX_ITERATIONS = 3

    async def run_pipeline(self, spec: SkillSpec) -> PipelineResult:
        """执行完整的生成-验证-评估管线"""
        feedback = ""  # 初始无反馈

        for iteration in range(1, self.MAX_ITERATIONS + 1):
            # 1. 代码生成（带上一轮反馈）
            generated = await self.code_generator.generate(spec, feedback=feedback)

            # 2. 静态验证
            validation = self.static_validator.validate(generated)
            if not validation.passed:
                feedback = self._build_feedback("静态验证失败", validation.errors)
                continue

            # 3. 沙箱执行
            exec_result = await self.sandbox_runner.run(generated)
            if not exec_result.success:
                feedback = self._build_feedback("执行失败", [exec_result.error])
                continue

            # 4. 基础检查
            basic = self.output_evaluator.basic_check(exec_result, spec)
            if not basic.passed:
                feedback = self._build_feedback("输出检查失败", basic.issues)
                continue

            # 5. Judge LLM 评估
            judge = await self.output_evaluator.judge_evaluate(spec, exec_result)

            if judge["overall_score"] >= OutputEvaluator.PASS_THRESHOLD:
                # ✅ 通过！
                return PipelineResult(
                    success=True,
                    generated=generated,
                    eval_score=judge["overall_score"],
                    iterations=iteration,
                    eval_history=self._history,
                )

            # 未通过，构建反馈
            feedback = self._build_feedback(
                "质量评估未通过",
                judge.get("issues", []),
                judge.get("suggestions", []),
                judge["scores"],
            )

        # 所有迭代用完
        return PipelineResult(
            success=False,
            reason="达到最大迭代次数仍未通过",
            iterations=self.MAX_ITERATIONS,
            eval_history=self._history,
            needs_human_review=True,
        )

    def _build_feedback(self, stage: str, errors: list,
                        suggestions: list = None, scores: dict = None) -> str:
        """构建给 CodeGenerator 的反馈信息"""
        parts = [f"## 上一轮失败原因: {stage}"]
        parts.append(f"### 错误:\n" + "\n".join(f"- {e}" for e in errors))
        if suggestions:
            parts.append(f"### 修复建议:\n" + "\n".join(f"- {s}" for s in suggestions))
        if scores:
            parts.append(f"### 各维度评分:\n" +
                        "\n".join(f"- {k}: {v}/10" for k, v in scores.items()))
        return "\n\n".join(parts)

class PipelineResult(BaseModel):
    """管线执行结果"""
    success: bool
    generated: Optional[GeneratedCode] = None
    eval_score: float = 0.0
    iterations: int = 0
    eval_history: List[dict] = []
    reason: Optional[str] = None
    needs_human_review: bool = False
```

---

## 10. MongoDB Schema 设计

### 10.1 external_skills 集合

存储生成的外部 Skill，是运行时加载的数据源。

```javascript
{
  "_id": ObjectId(),
  "tool_id": "generated_get_eastmoney_news",      // 唯一标识
  "source": "generated",                           // "generated" | "clawhub" | "skillcn"
  "slug": null,                                    // ClawHub slug（仅 clawhub 来源）
  "display_name": "东方财富个股新闻",
  "description": "获取指定股票在东方财富上的最新新闻列表",

  // 工具元数据（兼容 ToolMetadata 格式）
  "metadata": {
    "id": "generated_get_eastmoney_news",
    "name": "东方财富个股新闻",
    "description": "...",
    "category": "news",
    "parameters": [
      {"name": "stock_code", "type": "string", "required": true, "description": "A股代码"},
      {"name": "limit", "type": "integer", "required": false, "default": 10}
    ],
    "return_type": "list[dict]"
  },

  // 代码和实现
  "code": "import requests\nimport json\n\ndef generated_get_eastmoney_news(stock_code, limit=10):\n    ...",
  "skill_md": "# 东方财富个股新闻\n\n获取指定股票...",      // 可选的 SKILL.md
  "implementation": {
    "runtime": "python",                           // "python" | "node" | "bash"
    "entry_point": null,                           // 文件入口（多文件时用）
    "dependencies": ["requests"]                   // 依赖的第三方库
  },

  // 评估记录
  "eval_history": [
    {
      "round": 1,
      "score": 4.2,
      "issues": ["执行超时", "返回格式错误"],
      "timestamp": ISODate("2026-02-21T10:00:00Z")
    },
    {
      "round": 2,
      "score": 8.5,
      "issues": [],
      "timestamp": ISODate("2026-02-21T10:01:00Z")
    }
  ],
  "test_results": [
    {
      "input": {"stock_code": "600519", "limit": 5},
      "output_sample": [{"title": "贵州茅台...", "url": "..."}],
      "passed": true,
      "execution_time": 2.3
    }
  ],

  // 状态和统计
  "status": "active",                              // "active" | "disabled" | "failed" | "pending_review"
  "created_by": "user_123",
  "created_at": ISODate("2026-02-21T10:01:00Z"),
  "last_used": ISODate("2026-02-21T15:30:00Z"),
  "use_count": 42,
  "error_count": 1,
  "avg_execution_time": 1.8,

  // 关联信息
  "spec": { /* 完整的 SkillSpec */ },
  "session_id": "session_abc123"                   // 关联的创建会话
}
```

**索引设计：**
```javascript
db.external_skills.createIndex({"tool_id": 1}, {unique: true})
db.external_skills.createIndex({"status": 1, "metadata.category": 1})
db.external_skills.createIndex({"source": 1})
db.external_skills.createIndex({"created_by": 1, "created_at": -1})
```

### 10.2 skill_creation_sessions 集合

存储 Skill 创建会话，包括需求沟通的完整对话历史。

```javascript
{
  "_id": ObjectId(),
  "session_id": "session_abc123",
  "user_id": "user_123",
  "status": "completed",                           // gathering | confirmed | generating | completed | failed

  // 对话历史
  "rounds": [
    {
      "round_number": 1,
      "ai_message": "我理解你需要一个股票新闻获取工具...",
      "user_response": "A股就行。东方财富和财联社都要...",
      "extracted_info": {"market": "A股", "sources": ["eastmoney", "cls"]},
      "spec_updates": {"data_source": "eastmoney+cls", "category": "news"},
      "timestamp": ISODate("2026-02-21T09:50:00Z")
    },
    {
      "round_number": 2,
      "ai_message": "技术方案：方案A合并为一个工具...",
      "user_response": "选方案A",
      "extracted_info": {"merge_strategy": "combined"},
      "spec_updates": {"tool_id": "get_stock_news_combined"},
      "timestamp": ISODate("2026-02-21T09:52:00Z")
    },
    {
      "round_number": 3,
      "ai_message": "📄 工具规格书...",
      "user_response": "确认",
      "extracted_info": {},
      "spec_updates": {},
      "timestamp": ISODate("2026-02-21T09:55:00Z")
    }
  ],
  "current_round": 3,
  "clarity_level": "low",                          // high | medium | low

  // 锁定的规格
  "spec": {
    "tool_id": "get_stock_news_combined",
    "display_name": "股票新闻聚合",
    "description": "...",
    "category": "news",
    "data_source": "eastmoney+cls",
    "parameters": [...],
    "expected_output": {...},
    "constraints": [...],
    "test_input": {"stock_code": "600519", "limit": 5},
    "test_expected": {"min_items": 1, "required_fields": ["title", "url", "publish_time"]}
  },
  "spec_confirmed": true,

  // 生成结果
  "generation_result": {
    "success": true,
    "skill_id": "generated_get_stock_news_combined",
    "iterations": 2,
    "final_score": 8.5
  },

  // 边界检测
  "boundary_check": {
    "within_boundary": true,
    "complexity_score": 3,
    "violations": [],
    "suggested_decomposition": null
  },

  "created_at": ISODate("2026-02-21T09:50:00Z"),
  "updated_at": ISODate("2026-02-21T10:01:00Z")
}
```

**索引设计：**
```javascript
db.skill_creation_sessions.createIndex({"session_id": 1}, {unique: true})
db.skill_creation_sessions.createIndex({"user_id": 1, "created_at": -1})
db.skill_creation_sessions.createIndex({"status": 1})
```

---

## 11. API 端点设计

所有端点位于 `app/routers/skill_generation.py`，前缀 `/api/skills`。

### 11.1 需求沟通阶段

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/skills/create/start` | 开始创建会话，提交初始需求 |
| `POST` | `/api/skills/create/{session_id}/respond` | 用户回复对话轮次 |
| `POST` | `/api/skills/create/{session_id}/confirm` | 确认 SkillSpec，触发代码生成 |
| `GET` | `/api/skills/create/{session_id}` | 获取会话状态和对话历史 |

**启动会话：**
```
POST /api/skills/create/start
Request:
{
  "description": "我需要一个工具能获取股票相关新闻"
}

Response:
{
  "session_id": "session_abc123",
  "clarity_level": "low",
  "boundary_check": {
    "within_boundary": true,
    "complexity_score": 2
  },
  "ai_message": "我理解你需要一个股票新闻获取工具...",
  "current_round": 1,
  "expected_rounds": 3
}
```

**用户回复：**
```
POST /api/skills/create/{session_id}/respond
Request:
{
  "response": "A股就行。东方财富和财联社都要。需要新闻摘要。当天的就行。"
}

Response:
{
  "ai_message": "收到，技术方案如下...",
  "current_round": 2,
  "spec_preview": { /* 当前 SkillSpec 草稿 */ },
  "is_final_round": false
}
```

**确认规格：**
```
POST /api/skills/create/{session_id}/confirm
Response:
{
  "status": "generating",
  "message": "规格已确认，开始生成代码...",
  "estimated_time": "30-90秒"
}
```

### 11.2 Skill 管理

| 方法 | 路径 | 说明 |
|------|------|------|
| `GET` | `/api/skills/external` | 列出所有外部 Skill |
| `GET` | `/api/skills/external/{skill_id}` | 获取 Skill 详情 |
| `POST` | `/api/skills/external/{skill_id}/test` | 手动测试 Skill |
| `PUT` | `/api/skills/external/{skill_id}/status` | 启用/禁用 Skill |
| `DELETE` | `/api/skills/external/{skill_id}` | 删除 Skill |
| `GET` | `/api/skills/external/{skill_id}/code` | 查看 Skill 源码 |

**列出外部 Skill：**
```
GET /api/skills/external?category=news&status=active&page=1&page_size=20

Response:
{
  "total": 5,
  "items": [
    {
      "tool_id": "generated_get_eastmoney_news",
      "display_name": "东方财富个股新闻",
      "category": "news",
      "source": "generated",
      "status": "active",
      "eval_score": 8.5,
      "use_count": 42,
      "created_at": "2026-02-21T10:01:00Z"
    }
  ]
}
```

### 11.3 生成进度（WebSocket）

代码生成过程通过 WebSocket 推送进度：

```
WS /api/skills/create/{session_id}/progress

服务端推送事件:
{"stage": "generating", "message": "正在生成代码...", "progress": 20}
{"stage": "validating", "message": "静态验证中...", "progress": 40}
{"stage": "executing", "message": "沙箱执行中...", "progress": 60}
{"stage": "evaluating", "message": "质量评估中...", "progress": 80}
{"stage": "completed", "message": "生成成功！评分 8.5/10", "progress": 100, "skill_id": "..."}

// 或失败重试
{"stage": "retrying", "message": "第1轮未通过(4.2分)，正在重试...", "iteration": 2, "progress": 30}
```

---

## 12. 前端交互设计

### 12.1 创建 Skill 页面流程

```
┌─────────────────────────────────────────────────────────┐
│  🛠️ 创建新工具                                          │
│                                                         │
│  ┌───────────┐  ┌───────────┐  ┌───────────┐  ┌──────┐ │
│  │ ① 需求沟通 │→│ ② 规格确认 │→│ ③ 代码生成 │→│ ④ 完成│ │
│  │   ████████ │  │  ░░░░░░░░ │  │  ░░░░░░░░ │  │ ░░░░ │ │
│  └───────────┘  └───────────┘  └───────────┘  └──────┘ │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  AI: 我理解你需要一个股票新闻获取工具。         │    │
│  │      以下是我的理解，请确认和补充：              │    │
│  │                                                 │    │
│  │  | 功能   | 我的理解     | 需要确认         |   │    │
│  │  |--------|-------------|------------------|   │    │
│  │  | 市场   | A 股        | 港股/美股？      |   │    │
│  │  | 数据源 | 东方财富     | 有偏好吗？       |   │    │
│  │  | ...    | ...         | ...              |   │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  输入你的回复...                                  │    │
│  │                                          [发送]  │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### 12.2 规格确认页面

```
┌─────────────────────────────────────────────────────────┐
│  📄 工具规格确认                                         │
│                                                         │
│  基本信息                                                │
│  ├─ 工具 ID: get_stock_news_combined                    │
│  ├─ 名称: 股票新闻聚合                                   │
│  ├─ 分类: news                                          │
│  └─ 数据源: 东方财富 + 财联社                             │
│                                                         │
│  输入参数                                                │
│  ┌────────────┬────────┬──────┬────────────────┐        │
│  │ 参数       │ 类型   │ 必填 │ 说明           │        │
│  ├────────────┼────────┼──────┼────────────────┤        │
│  │ stock_code │ string │ ✅   │ A股代码        │        │
│  │ source     │ string │ ❌   │ 数据源选择     │        │
│  │ limit      │ int    │ ❌   │ 返回条数       │        │
│  └────────────┴────────┴──────┴────────────────┘        │
│                                                         │
│  ⚠️ 边界检查: 复杂度 3/5，在 Skill 范围内                 │
│                                                         │
│  [✅ 确认并生成]     [✏️ 返回修改]                        │
└─────────────────────────────────────────────────────────┘
```

### 12.3 生成进度页面

```
┌─────────────────────────────────────────────────────────┐
│  ⚙️ 正在生成工具...                                      │
│                                                         │
│  ████████████████████████░░░░░░  60%                    │
│                                                         │
│  ✅ 代码生成完成 (3.2秒)                                  │
│  ✅ 静态验证通过                                          │
│  🔄 沙箱执行中...                                        │
│  ○ 质量评估                                              │
│  ○ 注册上线                                              │
│                                                         │
│  迭代: 第 1 轮 / 最多 3 轮                                │
└─────────────────────────────────────────────────────────┘
```

---

## 13. 与现有系统的集成

### 13.1 ToolRegistry 扩展

```python
# core/tools/registry.py — 新增方法

class ToolRegistry:
    # ... 现有代码 ...

    async def register_external(self, skill_doc: dict) -> None:
        """从 MongoDB external_skills 文档注册外部 Skill"""
        tool_id = skill_doc["tool_id"]
        metadata = ToolMetadata(**skill_doc["metadata"])
        metadata.source = skill_doc.get("source", "generated")

        # 动态编译代码为函数
        namespace = {}
        exec(skill_doc["code"], namespace)
        func = namespace.get(tool_id)
        if func is None:
            raise ValueError(f"代码中未找到函数 {tool_id}")

        self._tools[tool_id] = metadata
        self._functions[tool_id] = func

    async def load_external_skills(self, db) -> int:
        """启动时从 MongoDB 加载所有活跃的外部 Skill"""
        cursor = db.external_skills.find({"status": "active"})
        count = 0
        async for doc in cursor:
            try:
                await self.register_external(doc)
                count += 1
            except Exception as e:
                logger.warning(f"加载外部 Skill {doc['tool_id']} 失败: {e}")
        logger.info(f"已加载 {count} 个外部 Skill")
        return count
```

### 13.2 ToolCategory 扩展

```python
# core/tools/config.py — 新增类别

class ToolCategory(str, Enum):
    MARKET = "market"
    FUNDAMENTALS = "fundamentals"
    NEWS = "news"
    SOCIAL = "social"
    TECHNICAL = "technical"
    CHINA = "china"
    TRADE_REVIEW = "trade_review"
    UTILITY = "utility"
    KNOWLEDGE = "knowledge"
    EXTERNAL = "external"          # 新增：外部生成的 Skill
```

### 13.3 BaseAgent 工具加载扩展

```python
# core/agents/base.py — 扩展 load_tools_from_config()

class BaseAgent:
    async def load_tools_from_config(self, db=None):
        """加载工具配置，包括外部 Skill"""
        # ... 现有的内置工具加载逻辑 ...

        # 新增：加载绑定的外部 Skill
        if db:
            external_bindings = await db.tool_agent_bindings.find({
                "agent_id": self.agent_id,
                "tool_source": "external"
            }).to_list(100)

            for binding in external_bindings:
                tool_id = binding["tool_id"]
                func = ToolRegistry().get_function(tool_id)
                if func:
                    self.tools.append(func)
```

### 13.4 ToolCallNormalizer 路由

```python
# core/llm/tool_normalizer.py — 扩展执行路由

class ToolCallNormalizer:
    async def execute_tool_call(self, tool_name: str, arguments: dict) -> ToolResult:
        """执行工具调用，支持外部 Skill 路由"""
        registry = ToolRegistry()

        # 检查是否是外部 Skill
        metadata = registry.get_metadata(tool_name)
        if metadata and getattr(metadata, "source", None) in ("generated", "clawhub"):
            # 外部 Skill 走沙箱执行（可选，上线后可直接调用）
            func = registry.get_function(tool_name)
            result = func(**arguments)
            return ToolResult(name=tool_name, content=json.dumps(result))

        # 内置工具走原有逻辑
        return await self._execute_builtin(tool_name, arguments)
```

### 13.5 应用启动集成

```python
# app/main.py — 启动时加载外部 Skill

@app.on_event("startup")
async def startup():
    await init_database()
    db = get_mongo_db()

    # 加载外部 Skill
    from core.tools.registry import ToolRegistry
    registry = ToolRegistry()
    count = await registry.load_external_skills(db)
    logger.info(f"启动: 加载了 {count} 个外部 Skill")
```

---

## 14. 成本分析

### 14.1 LLM 调用明细

每个 Skill 从创建到上线的 LLM 调用：

| 阶段 | LLM 调用次数 | 说明 |
|------|-------------|------|
| 清晰度评估 | 1 次 | 评估需求模糊度 |
| 边界检测 | 1 次 | 检查是否越界 |
| 对话轮次 | 1-3 次 | 每轮生成 AI 回复 |
| 代码生成 | 1-3 次 | 含重试 |
| Judge 评估 | 1-3 次 | 含重试 |
| **总计** | **3-9 次** | 取决于需求清晰度和代码质量 |

### 14.2 成本估算（以 DeepSeek 为例）

DeepSeek V3/R1 定价：
- 输入: ¥1/百万 tokens（缓存命中 ¥0.1）
- 输出: ¥2/百万 tokens

| 场景 | 调用次数 | 约 tokens | 估算成本 |
|------|---------|-----------|---------|
| **最优** (HIGH 清晰度，1 轮通过) | 3 次 | ~6K | ~¥0.02 |
| **典型** (MEDIUM，2 轮通过) | 6 次 | ~15K | ~¥0.05 |
| **最差** (LOW，3 轮重试) | 9 次 | ~30K | ~¥0.10 |

> **结论：即使最差情况，单个 Skill 生成成本 < ¥0.1（DeepSeek）。** 这比人工开发一个数据获取函数（通常 30-60 分钟）的时间成本低几个数量级。

### 14.3 缓存策略

为进一步降低成本：

| 策略 | 效果 |
|------|------|
| **Skill 复用** | 生成过的 Skill 缓存在 `external_skills`，下次直接加载 |
| **模板检索** | 相似需求参考已有代码，减少生成失败率 |
| **Prompt 缓存** | DeepSeek 的输入缓存折扣（90% off） |
| **批量评估** | 基础检查零成本过滤，减少 Judge LLM 调用 |

---

## 15. 开发计划

### 15.1 分期实现

```
Phase 1 — 基础框架 (1 周)
├── core/tools/external/skill_spec.py        数据模型
├── core/tools/external/requirement_analyzer.py  需求分析（单轮简化版）
├── core/tools/external/boundary_detector.py     边界检测
└── MongoDB: skill_creation_sessions 集合

Phase 2 — 代码生成管线 (1 周)
├── core/tools/external/code_generator.py    代码生成器
├── core/tools/external/static_validator.py  静态验证器
├── core/tools/external/sandbox_runner.py    沙箱执行器
└── core/tools/external/output_evaluator.py  输出评估器

Phase 3 — 迭代控制和注册 (1 周)
├── core/tools/external/iteration_controller.py  迭代控制器
├── core/tools/external/skill_executor.py        运行时执行器
├── ToolRegistry 扩展                             外部 Skill 注册
└── MongoDB: external_skills 集合

Phase 4 — API 和多轮对话 (1 周)
├── app/routers/skill_generation.py          API 端点
├── app/services/skill_generation_service.py  业务逻辑
├── RequirementAnalyzer 完整版                多轮对话
└── WebSocket 进度推送

Phase 5 — 前端界面 (2 周)
├── frontend/src/views/skills/              Skill 管理页面
├── 创建向导（对话式 UI）
├── 规格确认页面
├── 生成进度页面
└── Skill 列表和详情页面

Phase 6 — 测试和文档 (1 周)
├── 单元测试（各模块）
├── 集成测试（端到端流程）
├── 性能测试（并发生成）
└── 用户文档
```

### 15.2 优先级排序

| 优先级 | 模块 | 理由 |
|--------|------|------|
| **P0** | CodeGenerator + StaticValidator + SandboxRunner | 核心管线，其他模块依赖它 |
| **P0** | IterationController + OutputEvaluator | 质量保证，没有它等于没有验证 |
| **P1** | RequirementAnalyzer (单轮版) | 用户入口，但初期可手动构造 SkillSpec |
| **P1** | API + 基础前端 | 用户可用性 |
| **P2** | RequirementAnalyzer (多轮版) | 体验优化 |
| **P2** | BoundaryDetector | 安全网，但初期用户量小可人工审核 |
| **P3** | ClawHub Client | 辅助功能，非核心路径 |
| **P3** | SkillCN 平台集成 | 远期生态建设 |

### 15.3 里程碑

| 里程碑 | 时间 | 标志 |
|--------|------|------|
| **M1: 管线可用** | +2 周 | 手动输入 SkillSpec → 自动生成+验证+注册 |
| **M2: API 可调** | +4 周 | 前端可调用 API 完成完整流程 |
| **M3: 多轮对话** | +5 周 | 用户自然语言描述 → AI 引导 → 生成上线 |
| **M4: 生产就绪** | +7 周 | 完整测试、文档、监控 |

---

## 16. 附录

### 16.1 完整生命周期示例

```
用户: "我需要一个工具能获取雪球上某只股票的讨论热度"
                    │
                    ▼
    ┌── RequirementAnalyzer ──┐
    │  清晰度: MEDIUM (3/5)    │
    │  边界: OK (score=2)      │
    │  ┌── 第1轮 ──────────┐  │
    │  │ AI: 目标市场？A股？ │  │
    │  │ 用户: A股就行       │  │
    │  └───────────────────┘  │
    │  ┌── 第2轮 ──────────┐  │
    │  │ AI: 规格确认       │  │
    │  │ 用户: 确认 ✅       │  │
    │  └───────────────────┘  │
    └── SkillSpec 锁定 ───────┘
                    │
                    ▼
    ┌── CodeGenerator ────────┐
    │  检索: 无相似 Skill      │
    │  LLM 生成 Python 代码    │
    │  + ToolMetadata          │
    │  + 测试用例              │
    └─────────────────────────┘
                    │
                    ▼
    ┌── StaticValidator ──────┐
    │  ✅ 语法正确             │
    │  ✅ 无安全违规           │
    │  ✅ 依赖在白名单内       │
    │  ✅ 签名一致             │
    └─────────────────────────┘
                    │
                    ▼
    ┌── SandboxRunner ────────┐
    │  输入: {stock_code:"SH600519"}│
    │  执行: 2.3 秒             │
    │  输出: [{title:..., ...}] │
    │  ✅ 无异常                │
    └─────────────────────────┘
                    │
                    ▼
    ┌── OutputEvaluator ──────┐
    │  基础检查: ✅ 通过        │
    │  Judge LLM:              │
    │  - 可执行性: 10          │
    │  - 真实性: 8             │
    │  - 完整性: 9             │
    │  - 相关性: 9             │
    │  - 格式: 8               │
    │  总分: 8.8 ✅ PASS       │
    └─────────────────────────┘
                    │
                    ▼
    ┌── 注册上线 ─────────────┐
    │  → external_skills 存储  │
    │  → ToolRegistry 注册     │
    │  → 可绑定到 Agent        │
    └─────────────────────────┘
```

### 16.2 与 v2.3 评估结论的衔接

v2.3 评估结论：
> "不建议在核心分析流程中引入 Agent Skill，因为核心分析流程是固定的、结构化的。"

本方案的定位：
- **不替代核心分析流程**（仍由 v2.0 工作流引擎驱动）
- **补充数据获取能力**（让用户按需扩展数据源）
- **为智能助手提供工具调用能力**（v2.3 智能助手场景）

两者不冲突：核心流程用固定工作流，数据获取用按需生成的 Skill。

---

**最后更新**: 2026-02-21
**版本**: v1.0
**关联文档**:
- [v2.3 Skill 机制评估](../v2.3/skill-mechanism-reassessment.md)
- [v2.1 插件平台概念](../v2.1/plugin-platform-concept.md)
- [v2.0 工具系统设计](../v2.0/tools/)