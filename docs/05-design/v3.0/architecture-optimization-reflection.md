# 架构优化反思与路线图

> 版本：v3.0 | 日期：2026-07-26 | 依据：吴恩达 Agentic AI 四大设计模式评估 + 三子系统 HITL 分析 + 股票详情页改造实践

---

## 〇、关联文档与定位

本文档是**架构反思 + 路线图**，不是从零设计。以下已有文档与本反思存在重叠或互补，实施时应以本文档为索引，以已有文档为细节依据：

| 已有文档 | 关系 | 说明 |
|---|---|---|
| [memory-optimization-backlog.md](./memory-optimization-backlog.md) | 互补 | 记忆系统 P0/P1/P2 清单已落地，本文档"复盘回流"项应复用其 `TRADE_PATTERN` scope 和 `_store_trade_pattern_memory` 已有写入点，**不重复造轮子** |
| [agent-design-maturity-checklist.md](./agent-design-maturity-checklist.md) | 互补 | 已有 M0-M3 成熟度评估，本文档"四大设计模式成熟度"是不同视角（吴恩达模式视角 vs Agent 设计域视角），两者不冲突 |
| [unified-memory-layer-mem0.md](./unified-memory-layer-mem0.md) | 引用 | mem0 记忆层主设计文档，反射模式新设计（第九章）基于其 `MemoryService` 接口 |
| [v3.x-release-plan.md](./v3.x-release-plan.md) | 对齐 | v3.0.0~v3.4.0 已规划完毕，本文档路线图对应 v3.5.0+ |
| [v3.x-next-steps-plan.md](./v3.x-next-steps-plan.md) | 对齐 | 当前版本发布状态，本文档阶段一对应其后续版本 |
| [intelligent-assistant.md](./intelligent-assistant.md) | 引用 | 智能助手主设计文档，"伪 HITL"问题修复基于其现有架构 |
| [agent-builder-langgraph-workflow-design.md](./agent-builder-langgraph-workflow-design.md) | 引用 | Agent 工坊 checkpoint 模式，智能助手 HITL 修复复用其设计 |

**实施原则**：
1. 路线图中标记"复用已有"的项，先查看关联文档是否已部分实现
2. 不重复设计已有文档覆盖的内容，只补缺失环节
3. 测试脚本命名遵循 `scripts/validate_*.py` 既有规范

---

## 一、背景与反思范围

本文档基于以下工作产出，对 TradingAgents-CN v3.0 架构进行全面反思：

1. **吴恩达 Agentic AI 课程对照**：对照 4 大设计模式（工具使用、反射、规划、多智能体）评估系统成熟度
2. **股票详情页智能助手改造**：从"硬塞截断摘要"到"Agent 按需调工具取完整报告"的架构升级
3. **三子系统 HITL 分析**：智能助手、Agent 工坊、Skill 工坊的 Human-in-the-loop 实现对比
4. **LangGraph 版本评估**：1.2.6 是否值得迁移到 1.2.9 / 新 API 风格

---

## 二、现状总览：四大设计模式成熟度

| 设计模式 | 成熟度 | 吴恩达课程对应 | 核心评价 |
|---|---|---|---|
| **工具使用** | ⭐⭐⭐⭐⭐ | 模块3：Tool Use + MCP | 完整实现，含工具注册、MCP、循环调用、按需取报告 |
| **反射** | ⭐⭐ | 模块2：Reflection | 旧架构有但废弃，新架构缺失。记忆系统"存"不"炼" |
| **规划** | ⭐⭐⭐⭐⭐ | 模块5：Planning | 三级保障（种子流程→LLM规划→ReAct回退），业界领先 |
| **多智能体** | ⭐⭐⭐⭐⭐ | 模块5：Multi-Agent | 17+ Agent 角色，多轮辩论，并行执行，完整生态 |

**核心结论**：工具使用、规划、多智能体三个模式已达到生产级成熟度。反射模式是唯一的结构性短板。

---

## 三、逐项反思

### 3.1 反射（Reflection）—— 最大的架构债务

#### 3.1.1 旧架构有但已废弃

`tradingagents/graph/reflection.py` 的 `Reflector` 类实现了完整的事后反思：

- 4 维度反思：Reasoning → Improvement → Summary → Query
- 反思结果写入 ChromaDB 向量记忆
- 5 个角色逐一反思（多空研究员、交易员、投资经理、风险经理）

但 **3 个原因导致无法复用**：

1. **架构耦合**：旧 Reflector 强依赖 `judge_decision` 字段（旧架构有"裁判"角色），新架构用 `research_manager` 替代
2. **场景不匹配**：旧架构面向回测（有事后收益作为反馈输入），新架构面向实盘分析（无事后收益跟踪）
3. **调用被注释**：`main.py:26` 的 `ta.reflect_and_remember(1000)` 被注释掉，默认不启用

#### 3.1.2 新架构的实际缺口（已部分修复，缺反思提炼）

新架构的记忆系统经过 [memory-optimization-backlog.md](./memory-optimization-backlog.md) P0 轮优化后，**已经不是"半套"**，但仍缺"反思提炼"环节：

| 功能 | 旧架构 | 新架构现状 | 缺口 |
|---|---|---|---|
| 存（研究员报告） | 提炼后的经验教训 | `_save_to_memory()` 原文写入（`researcher.py:267-306`） | ❌ 无提炼，只存原文 |
| 存（股票分析） | - | ✅ `MemoryService.store_stock_analysis()` 结构化写入（summary/recommendation/evidence/next_checks，`service.py:229-267`） | 已完备 |
| 存（复盘结果） | - | ✅ `_store_trade_pattern_memory()` 写入 TRADE_PATTERN scope（`trade_review_service.py:76-148`） | ❌ `infer=False` 不提炼，只存原文 |
| 取 | 检索相似情境的经验 | ✅ `_get_memory_context()` + `MemoryService.recall_formatted()` 正常工作 | 已完备 |
| 反思 | ✅ 4 维度反思（Reasoning/Improvement/Summary/Query） | ❌ 无 | **核心缺口** |

**实际后果**：
1. 研究员报告和复盘结果虽然写入了 mem0，但只是原文搬运，没有提炼成"可复用的经验"
2. mem0 的 `infer=True` 模式可以自动提炼事实，但当前写入点都用了 `infer=False`（避免 LLM 提取噪声）
3. 系统每次分析同一只股票，召回的是历史报告原文，而不是"上次分析哪里对了、哪里错了"的结构化教训
4. 缺少"反思→提炼→写入"这一环，导致记忆系统"存"而不"炼"

**修复方向**：不是再造一套反思系统，而是在现有写入点之后增加一个"反思提炼"节点，把原文转化为结构化经验。详见第九章。

#### 3.1.3 分析师报告无自我检查（P0 项详细展开）

这是用户直接遇到过的 Bug：新闻分析师报告为空 → 系统回填兜底文案"工具执行或模型生成未完成，当前结论仍待验证"。

**实际代码行为**（`core/agents/base.py:528-1043` `invoke_with_tools()`）：

```
LLM 调工具 → 工具返回数据 → 添加 analysis_prompt → LLM 生成报告（不绑定工具）
                                              ↓
                                    base.py:1022  content = final_response.content
                                              ↓
                                    base.py:1025-1034  检查 content 是否为空
                                              ↓
                                    ⚠️ 只 log warning，不做兜底处理
                                              ↓
                                    base.py:1034  return content  ← 空报告直接返回
```

**关键问题**：
1. `base.py:1025-1034` 有空报告检测逻辑，但**只 log warning 不做兜底**
2. `base.py:1041-1043` 达到最大迭代次数返回固定文案"分析未能完成（达到最大迭代次数 X）"
3. `base.py:1020` 第二次调用仍返回 tool_calls 时返回"分析报告生成失败：LLM 持续返回工具调用"
4. 兜底文案"工具执行或模型生成未完成，当前结论仍待验证"不在 base.py，由上层（workflow engine 或 analyst agent）回填

**P0 修复设计：分析师报告完整性检查**

检查逻辑应加在 `invoke_with_tools()` 返回后、`AnalystAgent.execute()` 返回前，作为独立的质量门禁函数：

```python
# 新增文件：core/agents/quality_gate.py
def validate_analyst_report(content: str, agent_id: str, ticker: str) -> tuple[bool, str]:
    """分析师报告质量门禁。

    返回 (is_valid, reason)。is_valid=False 时调用方应重试或降级。
    """
    # 维度1：长度检查
    if not content or len(content.strip()) < 50:
        return False, "报告内容过短或为空"

    # 维度2：兜底文案黑名单（识别已知失败模式）
    FALLBACK_BLACKLIST = [
        "工具执行或模型生成未完成，当前结论仍待验证",
        "分析未能完成（达到最大迭代次数",
        "分析报告生成失败：LLM 持续返回工具调用",
    ]
    for pattern in FALLBACK_BLACKLIST:
        if pattern in content:
            return False, f"命中兜底文案黑名单: {pattern}"

    # 维度3：结论存在性检查（至少包含一个判断性关键词）
    CONCLUSION_KEYWORDS = ["建议", "结论", "判断", "观点", "风险", "机会", "看涨", "看跌", "持有", "买入", "卖出"]
    if not any(kw in content for kw in CONCLUSION_KEYWORDS):
        return False, "报告缺少结论性关键词"

    # 维度4：数据引用检查（可选，根据 agent 类型调整）
    # 新闻分析师应引用新闻，基本面分析师应引用财务数据
    # 此维度首版可跳过，避免误杀

    return True, ""
```

**失败处理策略**（分层降级）：

| 失败次数 | 处理方式 | 实现位置 |
|---|---|---|
| 第1次失败 | 重新调用 LLM 生成报告（保留工具结果，换 prompt 重试） | `AnalystAgent.execute()` 内重试1次 |
| 第2次失败 | 记录质量告警日志，标记报告为 `low_quality=True`，继续流程 | state 中追加 `quality_flags` 字段 |
| 第3次失败 | 写入 `analysis_quality_alerts` MongoDB 集合，供仪表盘展示 | 新增 `app/services/quality_alert_service.py` |

**代码落点**：

| 修改文件 | 修改点 | 说明 |
|---|---|---|
| `core/agents/quality_gate.py` | 新增文件 | `validate_analyst_report()` 函数 |
| `core/agents/base.py:1034` | `return content` 前调用 `validate_analyst_report()` | 不通过时返回特殊标记 |
| `core/agents/analyst.py` | `execute()` 中检测特殊标记，触发重试 | 最多重试1次 |
| `core/workflow/builder.py` | 分析师节点后追加 `quality_check` 节点 | 失败时记录 `quality_flags` |
| `app/services/quality_alert_service.py` | 新增文件 | 告警写入 MongoDB + 仪表盘查询接口 |

**不做什么**：
- ❌ 不在 `invoke_with_tools()` 内部做检查（保持工具调用循环的单一职责）
- ❌ 不阻塞整个工作流（分析师报告质量差时标记而非中断）
- ❌ 不首版做数据引用检查（避免误杀，先做长度+黑名单+结论关键词）

#### 3.1.4 辩论机制有对抗但无反思

多空研究员辩论（`core/agents/researcher.py`）和风险三方辩论（风险/防御/基准）是"对抗式反思"的实现，但：
- 辩论结束靠轮数控制，不评估辩论质量
- 辩论结果不回流到记忆系统
- 没有"辩论是否有新观点"的判断

---

### 3.2 工具使用（Tool Use）—— 已成熟，有优化空间

#### 3.2.1 已实现的能力

| 能力 | 实现位置 | 说明 |
|---|---|---|
| 工具基类 | `core/tools/base.py` | `BaseTool` 抽象基类，含元数据、超时、限流 |
| 工具注册 | `core/tools/registry.py` | `ToolRegistry` 单例，支持动态加载 |
| LLM 工具 schema | `core/tools/config.py` | `tool_metadata_list_to_openai()` 转换 |
| 循环调用 | `core/agents/base.py:527-840` | `invoke_with_tools()` 最多 3 轮，含重试退避 |
| MCP Server | `core/mcp/server.py` | 把本地工具暴露给外部 |
| MCP Client | `core/tools/mcp/client_manager.py` | 接入外部 MCP 工具 |
| 智能助手按需取报告 | `core/tools/implementations/assistant_ops/report_query.py` | `get_report_detail` 支持 `module_key` |

#### 3.2.2 优化空间

1. **工具描述质量**：`when_to_use` 提示已有（`core/agents/planner.py:180-185`），但部分工具描述不够精确，LLM 可能选错工具
2. **代码执行工具**：系统没有让 LLM 写代码并执行的能力（如 LLM 写 Python 算自定义财务指标）

---

### 3.3 规划（Planning）—— 业界领先

三级保障体系：

| 层级 | 机制 | 可靠性 | 实现位置 |
|---|---|---|---|
| 第一级 | 种子流程语义匹配 | ⭐⭐⭐⭐⭐ | `core/agents/planner.py:230-269` |
| 第二级 | LLM 自主规划 | ⭐⭐⭐⭐ | `core/agents/planner.py:445-488` |
| 第三级 | ReAct 回退 | ⭐⭐⭐ | `app/services/planned_analysis_service.py` |

**亮点**：Plan → Execute → Synthesize 完整流程，流式 SSE 事件推送，LLM 根据问题类型自动选工具组合。

**优化空间**：规划失败回退 ReAct 后，可以尝试"修正规划"而非直接降级。

---

### 3.4 多智能体（Multi-Agent）—— 完整生态

```
START
  │
  ▼
[6个分析师并行] ── index/sector/market/fundamentals/news/social
  │
  ▼
[merge] 等待所有分析师完成
  │
  ▼
[多空辩论] bull_researcher ←→ bear_researcher（多轮）
  │
  ▼
[研究经理] 综合多空证据
  │
  ▼
[风险三方辩论] risky ←→ safe ←→ neutral（多轮）
  │
  ▼
[风险管理者] 裁决
  │
  ▼
[交易员] 生成用户简报
  │
  ▼
END
```

**亮点**：
- 17+ Agent 角色，9 个分析师并行执行
- 多轮辩论，对抗式反思
- 独立消息历史（`_market_messages`、`_fundamentals_messages`），避免并行混乱
- 共享 State + 自定义 Reducer（`keep_non_empty`、`merge_dict`、`keep_latest_list`）

**缺口**：
- 无 Human-in-the-loop（不适合批量分析场景，但适合 Agent 工坊）
- Agent 数量固定，不根据股票类型动态裁剪
- 多智能体流程无可视化

---

## 四、三子系统 HITL 评估

### 4.1 实现对比

| 维度 | 智能助手 | Agent 工坊 | Skill 工坊 |
|---|---|---|---|
| **HITL 类型** | ❌ 无 HITL（伪 HITL） | ✅ 真正的 HITL | ❌ 无 HITL |
| **运行模式** | 全自动 ReAct 循环 | 多阶段暂停等待 | 全自动自迭代管线 |
| **暂停机制** | 无 | MongoDB checkpoint | 无 |
| **恢复机制** | 无 | LLM 意图分类 + 条件路由 | 无 |
| **等待节点数** | 0 | 6 个 | 0 |
| **用户参与点** | 无（伪 HITL 靠 LLM 自己判断） | 需求确认、方案选择、测试标的、评估决策 | 仅初始提交 spec |

### 4.2 Agent 工坊的 HITL 设计亮点

1. **MongoDB checkpoint 跨进程持久化**：不依赖 LangGraph 内置 `interrupt()`（进程内内存），服务重启不丢失状态
2. **LLM 意图分类**：用 LLM 理解用户短回复（"好的"、"换一个"、"方案B"），比正则匹配灵活
3. **澄清提示防重复**：`clarification_needed` 标记防止同一轮反复输出相同内容
4. **wait 节点不调 LLM**：纯状态标记，不浪费 token

### 4.3 智能助手的"伪 HITL"问题

智能助手 `intelligent_assistant_service.py` 的 system prompt 里有"确认后执行"指令，但这是**让 LLM 行为上表现得像等待确认**，不是真正的流程控制。LLM 可能"忘记"自己说过要等确认，或者用户没确认它就直接执行了。

### 4.4 Skill 工坊的 HITL 缺口

全自动迭代管线，失败后无人介入。迭代达到阈值后直接放弃，不会通知用户"要不要人工看一下"。

### 4.5 Skill 生成三种路径的 HITL 评估

经核查，Skill 生成实际存在三种调用路径，HITL 程度差异巨大：

| 路径 | 触发方式 | spec 确认环节 | 实际确认人 | 自动绑定到 Agent |
|---|---|---|---|---|
| **路径A：Skill 工坊独立生成** | 用户手动提交 spec | `preview_spec()` → 用户看预览 → `confirm_spec()` | ✅ 真实用户 | ❌ 不自动绑定 |
| **路径B：Agent 工坊自动补齐** | `resolve_agent_workshop_blocking_gaps` 工具 | 工具内部自动完成 preview → confirm | ❌ Nanobot（LLM）代劳 | ⚠️ 成功即自动绑定 |
| **路径C：AI 工作流批量生成** | `create_missing_skills()` | "自动确认 spec（AI 已在蓝图阶段分析好需求）" | ❌ 完全无确认 | ⚠️ 自动绑定 |

**路径B 是"伪 HITL"的典型**：

[agent-studio-skill-auto-completion.md:3.2](./agent-studio-skill-auto-completion.md) 自己承认了这个风险：

> "如果缺口描述不够清楚，**自动 respond/preview/confirm 可能把需求收窄错**。"

设计文档 11.2 节虽然规划了"新增能力必须用户确认"，但实际实现中 `resolve_agent_workshop_blocking_gaps` 是**阻塞式聚合工具**——Nanobot 调用它时，工具内部一次性完成 preview + confirm + 等待生成，用户根本没机会看到 SkillSpec 预览。用户只在"是否补齐缺口"这一层确认过，SkillSpec 的具体内容（输入输出、边界、实现方式）是 Nanobot 自动 confirm 的。

**路径C 完全无确认**：

[ai-workflow-generation.md:915-920](./ai-workflow-generation.md) 明确写了 `create_missing_skills()` 是"自动确认 spec（AI 已在蓝图阶段分析好需求）"，批量生成后直接绑定到 Agent，用户全程不参与。

**后果**：

1. 如果 LLM 对需求理解有偏差，会静默生成一个"看起来能用但实际不符合用户意图"的 Skill
2. 生成的 Skill 自动注册到 ToolRegistry 并绑定到 Agent，用户可能在 Agent 测试时才发现"这个 Agent 怎么会用错数据"
3. 用户既没看过 SkillSpec，也没看过代码和测试结果，对自动生成的能力完全没有掌控感

**与第 4.3 节智能助手"伪 HITL"的呼应**：Agent 工坊整体有 HITL（checkpoint），但 Skill 生成这个**子环节**是伪 HITL——这是"伪 HITL"问题在 Skill 生成场景的再次体现。修复方案见第六章阶段二项6。

---

## 五、架构债务清单

按严重程度排列：

| 优先级 | 债务项 | 影响范围 | 修复方向 |
|---|---|---|---|
| 🔴 P0 | 分析师报告无自我检查 | 可能产出空报告，污染下游分析 | `invoke_with_tools()` 后加轻量质量门禁 |
| 🔴 P0 | 历史经验不回流传 | 系统不会从错误中学习 | 复盘结果→记忆系统自动回流 |
| 🟡 P1 | 智能助手关键操作无确认 | 删除/触发分析等操作可能误执行 | 复用 Agent 工坊 checkpoint 模式 |
| 🟡 P1 | 报告质量无法量化 | 不知道分析质量好不好 | 自动化质量指标仪表盘 |
| 🟡 P1 | Skill 工坊无人工介入（路径A） | 迭代失败后无人接手 | 迭代阈值后暂停，展示失败原因 |
| 🟡 P1 | 路径B/C 自动生成 Skill 无 spec 级确认 | LLM 理解偏差会静默生成错误 Skill 并自动绑定到 Agent | 生成后审核才绑定（方案2），详见第六章阶段二项6 |
| 🟢 P2 | 辩论质量无衡量 | 可能浪费轮数 | 加辩论质量评估逻辑 |
| 🟢 P2 | 多智能体流程无可视化 | 用户看不到 Agent 协作过程 | 前端展示 Agent 数据流向图 |
| 🟢 P2 | Agent 数量不动态裁剪 | ETF 股票也跑筹码分析 | 根据股票类型跳过无关 Agent |

---

## 六、优化路线图

### 版本号对应关系

依据 [v3.x-release-plan.md](./v3.x-release-plan.md)，v3.0.0~v3.4.0 已规划完毕。本路线图对应：

| 阶段 | 目标版本 | 主题 | 预估工作量 |
|---|---|---|---|
| 阶段一 | **v3.5.0** | 反射修复 + 质量门禁 | 8-12 人日 |
| 阶段二 | **v3.6.0** | 可靠性量化 + 人工介入 | 6-10 人日 |
| 阶段三 | **v4.0** | 体验与效率（远期） | 待评估 |

### 阶段一：修复结构性短板（v3.5.0）

**目标**：消除已知 Bug，补上反射模式核心缺口

| # | 优化项 | 实现方式 | 完成标准 | 验收方式 | 工作量 | 依赖 |
|---|---|---|---|---|---|---|
| 1 | 分析师报告完整性检查 | 新增 `core/agents/quality_gate.py`，在 `invoke_with_tools()` 返回后校验（详见 3.1.3 节） | 空报告/兜底文案报告在 P0 流程中被拦截并重试1次；失败后标记 `low_quality` | `scripts/validate_quality_gate.py` 注入空报告/兜底文案，断言被拦截 | 2-3 人日 | 无 |
| 2 | 复盘结果反思提炼 | 在 `_store_trade_pattern_memory()` 后追加反思节点，用 LLM 提炼结构化经验，写入 TRADE_PATTERN scope（`infer=True`） | 复盘完成后 mem0 中出现结构化经验条目（非原文），包含"做得好/不足/改进"字段 | `scripts/validate_trade_review_reflection.py` 跑完复盘后召回，断言召回内容包含结构化字段 | 2-3 人日 | 复用 [memory-optimization-backlog.md](./memory-optimization-backlog.md) P0 已有写入点 |
| 3 | 研究员报告反思提炼 | 在 `_save_to_memory()` 后追加反思节点，提炼"上次分析结论 vs 实际走势"的经验 | 同一股票第二次分析时，`_get_memory_context()` 返回结构化教训而非原文 | `scripts/validate_researcher_reflection.py` 跑两次同股票分析，断言第二次召回含教训 | 2-3 人日 | 依赖项2的反思提炼框架 |
| 4 | 智能助手关键操作确认暂停 | 复用 Agent 工坊 checkpoint 模式（`agent_builder_store.py`），在触发分析/删除配置前硬性暂停 | 关键操作执行前 `awaiting_user=True`，前端展示确认弹窗；用户拒绝则不执行 | `scripts/validate_assistant_hitl.py` 模拟关键操作，断言流程暂停 | 2-3 人日 | 复用 [agent-builder-langgraph-workflow-design.md](./agent-builder-langgraph-workflow-design.md) checkpoint |

**阶段一总体验收**：
- `run_acceptance.ps1 api 3.5` 全部通过
- 新增 4 个 `scripts/validate_*.py` 脚本全部通过
- 无新增 P0 Bug

### 阶段二：提升系统可靠性（v3.6.0）

**目标**：量化质量，减少人工排查成本

| # | 优化项 | 实现方式 | 完成标准 | 验收方式 | 工作量 | 依赖 |
|---|---|---|---|---|---|---|
| 5 | 报告质量自动化指标 | 新增 `app/services/quality_metrics_service.py`，统计报告长度/数据引用/LLM耗时/成本，写入 `analysis_quality_metrics` 集合 | 仪表盘 API 可按日期/股票/Agent类型查询质量指标 | `scripts/validate_quality_metrics.py` 跑分析后查询指标，断言字段完整 | 2-3 人日 | 依赖阶段一项1的 quality_gate 数据 |
| 6 | Skill 生成 HITL 修复（三种路径） | 路径A：迭代3轮失败暂停；路径B/C：生成后审核才绑定（方案2，详见 6.1 节） | 路径B/C 生成的 Skill 不自动绑定，用户审核后才绑定 | `scripts/validate_skill_generation_hitl.py` 模拟三种路径，断言 HITL 行为 | 3-4 人日 | 无 |
| 7 | 规划失败后修正重试 | `app/services/planned_analysis_service.py` 规划失败时不直接降级 ReAct，先调用 LLM 修正规划1次 | 规划成功率提升（基线 vs 修复后对比） | `scripts/validate_planning_recovery.py` 注入规划失败，断言修正重试 | 1-2 人日 | 无 |
| 8 | 辩论结果回流记忆 | 多空辩论/风险辩论结束后，提炼"辩论新观点"写入 AGENT_EXPERIENCE scope | 辩论完成后的经验可被下次同股票分析召回 | `scripts/validate_debate_reflection.py` 跑两次分析，断言第二次召回辩论经验 | 2-3 人日 | 依赖阶段一项2的反思框架 |

### 6.1 项6 详细设计：Skill 生成 HITL 修复（方案2：生成后审核才绑定）

#### 设计决策

经产品体验对比（详见下表），选择**方案2：生成后审核才绑定**，核心理由是符合用户心智模型——用户关心的是"我的 Agent 能不能用"，而不是"Skill 规格对不对"。

| 方案 | 用户看到什么 | 技术门槛 | 交互次数 | 心智断层 | 失败成本 | 实现复杂度 |
|---|---|---|---|---|---|---|
| 方案1：preview 前置确认 | 抽象的 SkillSpec | 高 | +1（生成前） | 大 | 低 | 中 |
| **方案2：生成后审核才绑定** ✅ | 具体的代码+测试结果 | 中 | +1（生成后） | 小 | 中 | 低 |
| 方案3：按 severity 分级 | 混合 | 不确定 | 不确定 | 看分级 | 看分级 | 高（依赖 LLM 分级） |

**不选方案1**的原因：要求用户审核 SkillSpec 是体验断层，技术门槛太高——就像网购下单前让你审核商品工程图纸。

**不选方案3**的原因：severity 分级本身依赖 LLM 判断，可能误判；实现复杂度高；当前阶段不如方案2 直接。

#### 三种路径的修复方案

| 路径 | 当前行为 | 修复后行为 | 代码落点 |
|---|---|---|---|
| **路径A**（Skill 工坊独立） | 迭代3轮失败后自动放弃 | 迭代3轮失败后暂停，写入 `skill_iteration_alerts` 集合，前端展示失败原因，等待人工决策 | `core/tools/external/iteration_controller.py` |
| **路径B**（Agent 工坊自动补齐） | `resolve_agent_workshop_blocking_gaps` 自动 confirm + 自动绑定 | 生成完成后**不自动绑定**，先展示 Skill 代码和测试结果，用户确认后才绑定 | `core/tools/implementations/agent_builder_ops/gap_resolution.py` |
| **路径C**（AI 工作流批量） | `create_missing_skills()` 自动确认 + 自动绑定 | 批量生成完成后**统一审核**才绑定，展示所有生成结果，用户批量确认或逐个拒绝 | `core/workflow/generator/workflow_spec.py` 的 `create_missing_skills` |

#### 路径B 修复后的完整体验流程

```
用户在 Agent 工坊描述需求
  ↓
Nanobot: "我检查了一下，当前缺少【龙虎榜数据查询】能力，
        需要为你创建。我会在后台生成，你可以继续描述 Agent 需求。"
  ↓
用户继续聊 Agent（不阻塞，异步生成）
  ↓
后台: Skill 生成 → 质量门禁（StaticValidator + Judge + 沙箱）→ 测试
  ↓
失败 → 重试3轮 → 仍失败 → 通知用户"创建失败，原因 X，要不要手动调整"
成功 ↓
  ↓
Nanobot: "【龙虎榜数据查询】能力已创建，测试通过。
        [查看代码] [查看测试结果]
        是否绑定到当前 Agent？"
  ↓
用户点"确认绑定" → 绑定到 Agent 版本，继续构建流程
用户点"拒绝" → Skill 留在 Skill 工坊（可后续优化），不绑定
用户点"先看看代码" → 展开代码详情，再决定
```

#### 两层质量门禁

方案2 结合质量门禁分两层，确保用户看到的都是"基本能用"的 Skill：

| 层级 | 执行者 | 检查内容 | 失败处理 |
|---|---|---|---|
| 第一层（自动） | StaticValidator + Judge + 沙箱 | 语法/安全/依赖/输出质量评分 | 自动重试3轮，不展示给用户 |
| 第二层（用户） | 真实用户 | 代码可读性 + 测试结果 + 是否符合意图 | 用户拒绝则不绑定，Skill 留在工坊 |

#### 代码落点

| 修改文件 | 修改点 | 说明 |
|---|---|---|
| `core/tools/implementations/agent_builder_ops/gap_resolution.py` | `resolve_agent_workshop_blocking_gaps` 返回值新增 `pending_user_review` 字段 | 生成完成后不自动调用 `bind_skills_to_agents`，而是标记待审核 |
| `core/workflow/generator/workflow_spec.py` | `create_missing_skills` 返回值新增 `pending_user_review` 字段 | 同上，批量生成后标记待审核 |
| `app/routers/agent_builder.py` | 新增 `POST /api/agent-builder/skill-review/{session_id}/confirm` 接口 | 用户确认绑定 |
| `app/routers/agent_builder.py` | 新增 `POST /api/agent-builder/skill-review/{session_id}/reject` 接口 | 用户拒绝绑定，Skill 留在工坊 |
| `frontend/src/views/AgentStudio/` | 新增 SkillReviewCard 组件 | 展示生成的 Skill 代码、测试结果、确认/拒绝按钮 |
| `core/tools/external/iteration_controller.py` | 迭代3轮失败后写入 `skill_iteration_alerts` 集合 | 路径A 的人工介入入口 |

#### 不做什么

- ❌ 不要求用户审核 SkillSpec（方案1，技术门槛太高）
- ❌ 不按 severity 分级（方案3，依赖 LLM 判断可能误判）
- ❌ 不阻塞 Agent 创建主流程（Skill 生成异步进行，用户可继续聊）
- ❌ 不自动删除被拒绝的 Skill（留在工坊可后续优化或手动复用）
- ❌ 不首版做"批量审核的批量操作"（先逐个确认，批量操作留待 v4.0）

### 阶段三：体验与效率优化（v4.0 远期）

**目标**：提升用户体验与系统效率（非 v3.x 必做项）

| # | 优化项 | 实现方式 | 完成标准 | 工作量 |
|---|---|---|---|---|
| 9 | 多智能体流程可视化 | 前端展示 Agent 协作过程图（基于 workflow 执行事件流） | 用户可在前端看到 Agent 数据流向 | 5-8 人日 |
| 10 | Agent 数量动态裁剪 | 根据股票类型（ETF/个股/北交所）跳过无关 Agent | ETF 股票不再跑筹码分析等无关节点 | 2-3 人日 |
| 11 | 辩论质量评估 | 加辩论质量评估逻辑（新观点数/证据引用数/立场偏移） | 辩论轮数可根据质量动态调整 | 3-5 人日 |
| 12 | LangGraph 新特性评估 | 仅当老 API 成为瓶颈时考虑迁移 Command 对象/interrupt() | 满足第七章迁移触发条件 | 待评估 |

### 路线图依赖关系图

```
阶段一（v3.5.0）
  ├─ 项1 分析师报告完整性检查 ─── 无依赖
  ├─ 项2 复盘结果反思提炼 ────── 复用 memory-optimization-backlog P0
  ├─ 项3 研究员报告反思提炼 ──── 依赖项2
  └─ 项4 智能助手HITL ────────── 复用 agent-builder checkpoint

阶段二（v3.6.0）
  ├─ 项5 报告质量指标 ────────── 依赖阶段一项1
  ├─ 项6 Skill生成HITL修复 ──── 无依赖（覆盖三种路径，详见 6.1 节）
  ├─ 项7 规划失败修正重试 ────── 无依赖
  └─ 项8 辩论结果回流 ────────── 依赖阶段一项2

阶段三（v4.0）
  └─ 全部为独立优化项，无跨阶段依赖
```

---

## 七、LangGraph 版本策略

**决策：保持现状，不迁移。**

| 维度 | 结论 |
|---|---|
| 当前版本 | LangGraph 1.2.6（最新 1.2.9，仅落后 3 个补丁版本） |
| 1.0+ 新 API | Command 对象、Functional API、interrupt() 均未使用 |
| 向后兼容性 | 1.2.9 对老 API 全兼容，不迁移也能升级 |
| 迁移风险 | 高——`builder.py` 2300+ 行，辩论机制、工具循环都是精心调试过的 |
| 迁移收益 | 低——当前无痛点 |

**迁移触发条件**（满足任一即可考虑）：
1. LangGraph 官方宣布废弃老 API
2. 需要做 Human-in-the-loop（用 `interrupt()` 比自研 MongoDB checkpoint 更优雅）
3. 辩论路由逻辑复杂到条件边函数难以维护

---

## 八、关键文件索引

### 反射相关
- 旧架构反思：`tradingagents/graph/reflection.py`（已废弃）
- 新架构记忆存取：`core/agents/researcher.py`（`_save_to_memory` / `_get_memory_context`）
- 辩论机制：`core/agents/researcher.py`（多空研究员多轮辩论）

### 工具使用相关
- 工具基类：`core/tools/base.py`
- 工具注册：`core/tools/registry.py`
- 工具调用循环：`core/agents/base.py:527-840`
- 智能助手报告查询：`core/tools/implementations/assistant_ops/report_query.py`

### HITL 相关
- Agent 工坊 checkpoint：`core/embedded_nanobot/workflows/agent_builder_store.py`
- Agent 工坊图定义：`core/embedded_nanobot/workflows/agent_builder_graph.py`
- Agent 工坊节点：`core/embedded_nanobot/workflows/agent_builder_nodes.py`
- Agent 工坊条件路由：`core/embedded_nanobot/workflows/agent_builder_conditions.py`
- Agent 工坊状态：`core/embedded_nanobot/workflows/agent_builder_state.py`
- 智能助手服务：`app/services/intelligent_assistant_service.py`
- Skill 工坊迭代控制器：`core/tools/external/iteration_controller.py`

### 规划相关
- 规划器：`core/agents/planner.py`
- 种子流程：`core/agents/seed_flows.py`
- 规划执行服务：`app/services/planned_analysis_service.py`

### 多智能体相关
- 工作流构建器：`core/workflow/builder.py`
- 工作流引擎：`core/workflow/engine.py`
- State 定义：`core/state/state.py`
- Reducer 定义：`core/state/reducers.py`

### 设计文档
- 智能助手设计：`docs/05-design/v3.0/intelligent-assistant.md`
- Agent 工坊工作流设计：`docs/05-design/v3.0/agent-builder-langgraph-workflow-design.md`
- Agent 工坊工作流参考：`docs/05-design/v3.0/agent-builder-workflow-reference.md`
- Skill 生成系统设计：`docs/05-design/v3.0/skill-generation-system.md`
- Skill 生成 Agentic 引擎：`docs/05-design/v3.0/skill-generation-agentic-engine.md`
- 统一记忆层设计：`docs/05-design/v3.0/unified-memory-layer-mem0.md`

---

## 九、反射模式新设计方案

> 本章是路线图阶段一项2/3/8 的共同设计基础，给出新反射机制的具体方案。

### 9.1 设计目标

不是复活旧 `Reflector`，而是在现有 mem0 写入点之上增加"反思提炼"节点：

```
当前流程：报告生成 → 原文写入 mem0（infer=False）
                              ↓
新增环节：              反思提炼节点（LLM 提炼结构化经验）
                              ↓
                       结构化经验写入 mem0（infer=False，已提炼无需再提取）
```

### 9.2 与旧 Reflector 的关系

| 维度 | 旧 Reflector | 新反射机制 |
|---|---|---|
| 触发时机 | 回测结束后（有事后收益） | 实盘分析后 + 复盘后 |
| 输入 | `judge_decision` + `returns_losses` | 报告原文 + 复盘结论（无事后收益依赖） |
| 4 维度 | Reasoning / Improvement / Summary / Query | 复用，但去掉"收益"维度，改为"结论 vs 走势" |
| 存储 | ChromaDB `add_situations` | mem0 `MemoryService.store()` |
| 调用 | `ta.reflect_and_remember(1000)` 已注释 | 由工作流节点自动触发 |

**不复用旧代码的原因**：旧 `Reflector` 强依赖 `judge_decision` 字段和 `returns_losses` 参数，新架构用 `research_manager` 替代了裁判角色，且实盘分析无事后收益。复用代码会导致接口不兼容。

**复用旧 prompt 的部分**：旧 `_get_reflection_prompt()` 的 4 维度框架（Reasoning/Improvement/Summary/Query）仍然适用，去掉"收益"相关描述即可。

### 9.3 反射机制的三种触发场景

#### 场景A：复盘完成后（阶段一项2）

**触发点**：`trade_review_service.py` 的 `_store_trade_pattern_memory()` 调用后

**输入**：
- 复盘结论（summary / strengths / weaknesses / suggestions / plan_deviation）
- 交易盈亏（trade_info 中的 first_buy_date / last_sell_date / pnl）
- 标的代码

**输出**（结构化经验，写入 TRADE_PATTERN scope）：

```python
# 新增 helper：app/services/trade_review_service.py
async def _reflect_and_store_lesson(
    db, user_id: str, trade_info, ai_review, review_id: str
) -> None:
    """复盘反思提炼：把原文复盘结论转化为结构化经验。"""
    # 1. 构建反思 prompt（基于旧 Reflector 4 维度，去掉收益依赖）
    reflection_prompt = _build_trade_reflection_prompt(trade_info, ai_review)

    # 2. 调用 LLM 提炼
    lessons = await llm_client.achat([
        {"role": "system", "content": REFLECTION_SYSTEM_PROMPT},
        {"role": "user", "content": reflection_prompt},
    ])
    # lessons 是结构化 JSON：{reasoning, improvement, summary, query}

    # 3. 写入 mem0（infer=False，已提炼无需再提取）
    from core.memory.service import get_memory_service
    from core.memory.models import MemoryScope
    svc = get_memory_service(db)
    await svc.store(
        [{"role": "assistant", "content": json.dumps(lessons, ensure_ascii=False)}],
        user_id=user_id,
        agent_id="trade_review_reflection",
        scope=MemoryScope.TRADE_PATTERN,
        metadata={
            "review_id": review_id,
            "symbol": str(trade_info.code).upper(),
            "memory_kind": "trade_lesson",  # 区别于原文的 "trade_pattern"
            "source": "reflection",
        },
        infer=False,
    )
```

**消费点**：下次同股票分析时，`_get_memory_context()` 召回 TRADE_PATTERN scope，优先返回 `memory_kind=trade_lesson` 的结构化经验。

#### 场景B：研究员报告生成后（阶段一项3）

**触发点**：`researcher.py` 的 `_save_to_memory()` 调用后

**输入**：
- 研究员报告（bull_report / bear_report）
- 标的代码
- 分析日期

**输出**（结构化教训，写入 ANALYSIS_INSIGHT scope）：

```python
# 新增 helper：core/agents/researcher.py
async def _reflect_on_analysis(
    self, ticker: str, report: Dict[str, Any], analysis_date: str
) -> None:
    """研究员报告反思：提炼'本次分析的核心观点和依据'。"""
    reflection_prompt = self._build_analysis_reflection_prompt(ticker, report, analysis_date)

    lessons = await self._llm.ainvoke([
        SystemMessage(content=ANALYSIS_REFLECTION_SYSTEM_PROMPT),
        HumanMessage(content=reflection_prompt),
    ])

    # 写入 mem0（infer=False）
    from core.memory.service import get_memory_service
    from core.memory.models import MemoryScope
    svc = get_memory_service()
    await svc.store(
        [{"role": "assistant", "content": lessons.content}],
        user_id=self._user_id,
        agent_id=self.agent_id,
        scope=MemoryScope.ANALYSIS_INSIGHT,
        metadata={
            "symbol": str(ticker).upper(),
            "analysis_date": analysis_date,
            "memory_kind": "analysis_lesson",  # 区别于原文的 "stock_analysis"
            "stance": self.stance,
            "source": "reflection",
        },
        infer=False,
    )
```

**消费点**：下次同股票分析时，`_get_memory_context()` 召回 ANALYSIS_INSIGHT scope，优先返回 `memory_kind=analysis_lesson` 的结构化教训。

#### 场景C：辩论结束后（阶段二项8）

**触发点**：多空辩论 / 风险辩论达到最大轮数后

**输入**：
- 辩论历史（bull_history / bear_history）
- 辩论结论（research_manager / risk_manager 的裁决）

**输出**（辩论新观点，写入 AGENT_EXPERIENCE scope）：

```python
# 新增 helper：core/agents/researcher.py
async def _reflect_on_debate(
    self, ticker: str, debate_history: List, conclusion: str
) -> None:
    """辩论反思：提炼辩论中的新观点和被忽略的风险。"""
    reflection_prompt = _build_debate_reflection_prompt(ticker, debate_history, conclusion)

    lessons = await self._llm.ainvoke([
        SystemMessage(content=DEBATE_REFLECTION_SYSTEM_PROMPT),
        HumanMessage(content=reflection_prompt),
    ])

    from core.memory.service import get_memory_service
    from core.memory.models import MemoryScope
    svc = get_memory_service()
    await svc.store(
        [{"role": "assistant", "content": lessons.content}],
        user_id=self._user_id,
        agent_id=self.agent_id,
        scope=MemoryScope.AGENT_EXPERIENCE,
        metadata={
            "symbol": str(ticker).upper(),
            "memory_kind": "debate_lesson",
            "debate_type": self.debate_state_field,  # investment_debate / risk_debate
            "source": "reflection",
        },
        infer=False,
    )
```

### 9.4 反思 prompt 模板（基于旧 Reflector 改造）

```python
# 新增文件：core/agents/reflection_prompts.py

TRADE_REFLECTION_SYSTEM_PROMPT = """
你是交易反思专家。基于以下复盘结论，提炼可复用的结构化经验。

## 输出格式（严格 JSON）
{
  "reasoning": "本次交易的核心逻辑是什么？哪些判断被市场验证了？",
  "improvement": "哪些判断错了？下次应该怎么改进？",
  "summary": "一句话总结这次交易的教训",
  "query": "可用于向量检索的关键词（10-20字）"
}

只输出 JSON，不要其他内容。
"""

ANALYSIS_REFLECTION_SYSTEM_PROMPT = """
你是投研反思专家。基于以下分析报告，提炼可复用的结构化教训。

## 输出格式（严格 JSON）
{
  "reasoning": "本次分析的核心观点是什么？依据是什么？",
  "improvement": "分析中可能遗漏了哪些维度？下次应该补充什么？",
  "summary": "一句话总结本次分析的教训",
  "query": "可用于向量检索的关键词（10-20字）"
}

只输出 JSON，不要其他内容。
"""

DEBATE_REFLECTION_SYSTEM_PROMPT = """
你是辩论反思专家。基于以下辩论历史和最终裁决，提炼辩论中的新观点。

## 输出格式（严格 JSON）
{
  "reasoning": "辩论中提出了哪些有价值的新观点？",
  "improvement": "哪些观点被忽略了？辩论是否充分？",
  "summary": "一句话总结本次辩论的教训",
  "query": "可用于向量检索的关键词（10-20字）"
}

只输出 JSON，不要其他内容。
"""
```

### 9.5 与 mem0 集成的关键点

1. **`infer=False`**：反思节点已经用 LLM 提炼了结构化经验，写入 mem0 时不再调用 mem0 内部的事实提取，避免二次提取噪声
2. **`memory_kind` 元数据**：用 `trade_lesson` / `analysis_lesson` / `debate_lesson` 区分反思经验与原文，召回时可优先返回教训
3. **召回优先级**：`MemoryService.recall_formatted()` 已支持 `ranking_profile`，未来可扩展 `reflection_first` profile，让反思经验排在原文之前
4. **降级容错**：反思节点失败时（LLM 超时/返回非 JSON），fallback 到原文写入（即当前行为），不阻塞主流程

### 9.6 反射机制与辩论机制的协同

| 维度 | 辩论机制 | 反射机制 |
|---|---|---|
| 时机 | 分析过程中（实时） | 分析/复盘后（事后） |
| 输入 | 当前分析数据 | 辩论历史 + 最终结论 |
| 作用 | 防止单一立场偏差 | 提炼经验供下次复用 |
| 关系 | 辩论是"对抗式反思"的实时形式 | 反射是"总结式反思"的事后形式 |

**协同方式**：辩论结束后触发场景C反思，把辩论中的新观点提炼为结构化经验，供下次同股票分析召回。这样辩论不再只是"对抗"，还能"积累"。

### 9.7 不做什么

- ❌ 不复活旧 `Reflector` 类（接口不兼容）
- ❌ 不依赖事后收益（实盘分析场景无此数据）
- ❌ 不在每次分析师报告后都反思（只对研究员报告和复盘结果反思，避免 token 浪费）
- ❌ 不阻塞主流程（反思节点失败时降级为原文写入）
- ❌ 不首版做"结论 vs 实际走势"的自动对比（需要行情数据回流，留待 v4.0）

---

## 十、测试与验收策略

### 10.1 测试分层

每个优化项需通过三层验证，避免"写进去了但根本没用"的假闭环：

| 层级 | 目的 | 脚本位置 | 命名规范 |
|---|---|---|---|
| L1 写入测试 | 验证数据按预期写入正确 scope 和 metadata | `tests/services/test_*.py` | `test_<service>_<feature>.py` |
| L2 召回测试 | 验证写入的数据能被正确召回 | `tests/core/memory/test_*.py` | `test_recall_<scenario>.py` |
| L3 消费测试 | 验证召回结果真正进入 prompt 或影响输出 | `scripts/validate_*.py` | `validate_<feature>_loop.py` |

参考 [memory-optimization-backlog.md](./memory-optimization-backlog.md) P0-3 节的"消费闭环"验证模式。

### 10.2 各优化项的验证脚本

#### 阶段一（v3.5.0）

| 项 | 脚本 | 验证逻辑 | 断言 |
|---|---|---|---|
| 1 质量门禁 | `scripts/validate_quality_gate.py` | 注入空报告/兜底文案/正常报告三种 content | 空报告和兜底文案被拦截（is_valid=False），正常报告通过 |
| 2 复盘反思 | `scripts/validate_trade_review_reflection.py` | 跑完一次复盘后召回 TRADE_PATTERN scope | 召回内容包含 `memory_kind=trade_lesson` 的结构化字段（reasoning/improvement/summary/query） |
| 3 研究员反思 | `scripts/validate_researcher_reflection.py` | 跑两次同股票分析，第二次召回 ANALYSIS_INSIGHT scope | 第二次召回内容包含 `memory_kind=analysis_lesson`，且内容与第一次报告不同（是提炼后的教训） |
| 4 助手HITL | `scripts/validate_assistant_hitl.py` | 模拟触发分析/删除配置的关键操作 | `awaiting_user=True`，checkpoint 已保存，用户拒绝后操作未执行 |

#### 阶段二（v3.6.0）

| 项 | 脚本 | 验证逻辑 | 断言 |
|---|---|---|---|
| 5 质量指标 | `scripts/validate_quality_metrics.py` | 跑分析后查询 `analysis_quality_metrics` 集合 | 指标字段完整（报告长度/数据引用/LLM耗时/成本） |
| 6 Skill生成HITL | `scripts/validate_skill_generation_hitl.py` | 模拟三种路径：路径A迭代3轮失败；路径B `resolve_agent_workshop_blocking_gaps` 生成成功；路径C `create_missing_skills` 批量生成 | 路径A：流程暂停，`skill_iteration_alerts` 集合有记录；路径B：生成后返回 `pending_user_review=True`，未自动绑定；路径C：批量生成后全部 `pending_user_review=True`，未自动绑定；调用 confirm 接口后才绑定，调用 reject 接口后 Skill 留在工坊 |
| 7 规划修正 | `scripts/validate_planning_recovery.py` | 注入规划失败 | 修正重试1次后才降级 ReAct |
| 8 辩论回流 | `scripts/validate_debate_reflection.py` | 跑两次同股票分析 | 第二次召回 AGENT_EXPERIENCE scope 含 `memory_kind=debate_lesson` |

### 10.3 回归测试

每个版本发布前必须通过：

```powershell
# 现有验收测试（确保不破坏已有功能）
.\start_dev.ps1 all <版本号>      # 如 3.5 / 3.6
.\run_acceptance.ps1 all <版本号>

# 阶段一（v3.5.0）验证脚本
env\Scripts\python.exe scripts\validate_quality_gate.py
env\Scripts\python.exe scripts\validate_trade_review_reflection.py
env\Scripts\python.exe scripts\validate_researcher_reflection.py
env\Scripts\python.exe scripts\validate_assistant_hitl.py

# 阶段二（v3.6.0）验证脚本
env\Scripts\python.exe scripts\validate_quality_metrics.py
env\Scripts\python.exe scripts\validate_skill_generation_hitl.py
env\Scripts\python.exe scripts\validate_planning_recovery.py
env\Scripts\python.exe scripts\validate_debate_reflection.py
```

### 10.4 降级容错测试

每个反思节点和 HITL 节点必须验证降级路径：

| 场景 | 注入方式 | 期望行为 |
|---|---|---|
| LLM 超时 | mock `llm.ainvoke` 抛 timeout | 反思节点跳过，fallback 到原文写入，主流程继续 |
| LLM 返回非 JSON | mock 返回 `"这不是JSON"` | 反思节点跳过，fallback 到原文写入，主流程继续 |
| mem0 不可用 | 设置 `MEM0_ENABLED=false` | 所有记忆写入跳过，主流程继续 |
| checkpoint 保存失败 | mock `store.save_checkpoint` 抛异常 | 操作拒绝执行，返回错误提示（不阻塞用户） |
| Skill 生成后用户长时间不审核 | `pending_user_review` 超过 24h | Skill 保留在工坊，Agent 构建流程提示"有待审核 Skill"，不自动绑定 |
| 路径B 用户拒绝绑定 | 调用 reject 接口 | Skill 留在 `external_skills` 集合（`status=unbound`），不绑定到 Agent，可后续手动复用 |

### 10.5 质量基线对比

阶段二项5（报告质量指标）落地后，应建立质量基线：

| 指标 | 基线采集方式 | 改进目标 |
|---|---|---|
| 空报告率 | 跑 50 次分析，统计 `low_quality=True` 比例 | < 5%（基线待测） |
| 兜底文案命中率 | 跑 50 次分析，统计命中黑名单比例 | < 2%（基线待测） |
| 反思经验召回率 | 跑 10 只股票各分析2次，第二次是否召回教训 | > 80% |
| 复盘经验召回率 | 跑 10 次复盘后分析，是否召回 trade_lesson | > 80% |

### 10.6 不做什么

- ❌ 不做"分析质量提升"的端到端断言（质量提升难以量化，只验证闭环成立）
- ❌ 不做压力测试（个人使用场景，不考虑并发）
- ❌ 不做 A/B 对比（无对照组，只用前后基线对比）