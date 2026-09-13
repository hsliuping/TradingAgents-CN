# 智能助手质量架构重构设计（A11）

> 状态：设计定稿 v2（契约型关卡修订版）；阶段 0/1/2/3 已实施（详见 §5.2）
> 排期：2026-09-16 Demo 后启动；Demo 前冻结主链路
> 关联：docs/05-design/v3.0/valuation-excel-deliverable-design.md（估值 Excel 交付物，触发本次架构反思的系列工作之一）

> **v2 修订说明**：v1 的 ReplyGate 含文本重叠率/链接数等启发式检查与逐项豁免机制，评审发现两者都会失效（重叠率既误伤合理引用又放过重排透传；豁免面大到关卡对回复主体失效）。v2 改为**契约型关卡**（路径类型契约强制，不做文本猜测），Evidence 提至首批实施，降级链收敛为两级，LLM 裁判类工作改为数据驱动、不在本方案承诺。

---

## 1. 背景与动机

### 1.1 触发事件

2026-09-13 用户实测发现：智能助手中提问"最近赛力斯有没有新车发布之类的计划，销量下跌的原因是什么"，收到的是 **10 条裸搜索标题+链接列表**，而非回答。

根因：`chat()`/`chat_stream()` 中的"近期搜索快路径"把 `search_recent_information` 工具返回值（SearXNG 分支仅含标题+链接）直接作为回复透传，**LLM 完全没有参与**。已修复（`_summarize_search_result`），但修复过程暴露的是系统性缺陷，不是个案。

### 1.2 核心矛盾

现有质量保障是**按事故打补丁**，不是按**不变量设计**：

- 每次出问题 → 在出问题的地方加一道检查 → 别的地方照样裸奔
- 防线只挂在主路径出口，前置旁路是"逃生通道"，命中即 return，绕过一切防线
- 新增旁路时没有任何机制提醒"这里需要过质量关卡"

**本方案要终结的不是某类 bug，而是"发现一个修一个"这个模式本身。**

### 1.3 为什么这是产品级工作，而非内部装修

本方案的必要性不依赖于"代码整洁"，而是三个产品事实：

1. **Evidence/data_refs 兑现的是对外承诺的功能。** Demo 环节 3 的卖点是"每条结论**高亮回链**到原始工具返回与数据源"。系统现在只有"防编造"（内部拦截），没有"展示依据"（用户可见的溯源）——`data_refs` 全部返回 None，该承诺在产品上未兑现。证据集结构化是"可展示溯源"的后端前提。
2. **框架结构本身就是产品货架。** 对外（字节/京东云/开源贡献者）讲的是"多 Agent 生产级工程、溯源防线"。一个旁路乱穿、防线只守正门的助手，与该叙事矛盾——代码即橱窗。统一质量关卡是"可靠 Agent 框架"的组成部分。
3. **开源与平台运营带来确定的制度性需求。** 贡献者会加工具、加路径，注册表是"防止旁路绕过质量"的制度约束，越早立规矩成本越低；京东云版由外部运营，没有质量埋点则线上拦截率/降级率不可见，故障只能靠用户上报。

---

## 2. 现状诊断

### 2.1 架构现状全景

```
入口层     chat() + chat_stream()        ← 两套平行代码，约500行逻辑重复
   ↓
前置规则层  关键词/正则旁路×5+：
   ├─ HITL 确认解析（try_resolve_pending_action）
   ├─ 品种检查（_check_unsupported_asset）
   ├─ 搜索快路径（_should_use_recent_search）  ← 9.13 缺陷点
   ├─ 数据同步预检查（_extract_stock_code + _STOCK_DATA_KEYWORDS）
   └─ 消息改写（_rewrite_number_selection_reply）
   ↓
上下文组装  system prompt（3000+字，补丁式膨胀）+ RAG + 事实记忆 + 历史
   ↓
执行层     LLM function calling：276工具 × 最多8轮 + HITL 工具拦截
   ↓
后置防线   4道检查 ← 只挂主路径 _do_chat 出口：
   ├─ _has_fabricated_tool_json（编造工具JSON）
   ├─ _has_fabricated_tool_refs（伪造工具引用）
   ├─ _has_unsourced_numbers（未调工具但含数字）
   └─ _has_untraced_risky_numbers（无法溯源高风险数字）
   ↓
返回层     reply + tools_used + data_refs ← data_refs 12处全部返回 None，从未实现
```

### 2.2 回复质量问题分类（贯穿本方案的语言）

| 类别 | 定义 | 举例 | 现有覆盖 |
|------|------|------|---------|
| **A 编造类** | 回复含证据集中不存在的数字/痕迹 | 编数字、编工具调用、"约35元"式包装 | ✅ 最全（4道防线，踩坑最多） |
| **B 降级类** | 该加工没加工 | 裸透传工具结果、链接堆砌 | ⚠️ 快路径修复是第一例 |
| **C 意图类** | 回应错需求 | 答非所问、该调工具没调、路由错 | ❌ 基本裸奔 |
| **D 呈现类** | 格式问题 | 链接堆砌、超长、markdown 截断 | ❌ 无 |

### 2.3 结构性问题清单（本次重构的对象）

| # | 问题 | 证据 |
|---|------|------|
| S1 | 旁路绕过防线，无统一质量出口 | 快路径缺陷；data 预检查等 5 条旁路各写各的 |
| S2 | chat/chat_stream 双份平行实现 | 修快路径缺陷需要同步改两处 |
| S3 | 规则层做"意图猜测"抢 LLM 决策权 | 关键词交集判断整句话路由，无法分解复合意图 |
| S4 | 关键词词典硬编码且分散 | 股票名单至少 2 处重复硬编码（9 只股票）；问"中远海控"名称解析失败 |
| S5 | 路由优先级 = 代码书写顺序 | 多层规则关键词高度重叠，谁写前面谁赢，不可预测 |
| S6 | data_refs 声明未实现 | 12 处返回点全部 None；"结论回链数据源"卖点无后端支撑 |
| S7 | 防线内联在 _do_chat，不可复用 | 快路径修复时需手工拼 fast_tool_results 复刻防线入参 |
| S8 | system prompt 补丁式膨胀 | 3000+ 字，工具使用原则至少 3 处重复，改哪段无从判断 |
| S9 | 无质量度量 | 拦截率/降级率/旁路命中率零统计，问题靠用户发现 |
| S10 | 无回归测试集 | 每次修复靠手工验证，修 A 坏 B 无从发现 |

### 2.4 资产盘点（必须保留的真金白银）

| 资产 | 价值 | 处置 |
|------|------|------|
| 4 道后置防线函数 | 实战验证有效，产品差异化能力 | 收编进 ReplyGate，代码搬家不改逻辑 |
| 276 工具 + when_to_use 元数据 | 功能底座 | 不动 |
| system prompt 的领域规则**内容** | 踩坑换来的（防编造细则/合规边界/单位换算） | 内容保留，组织方式另行治理（见 §7） |
| HITL 确认机制（入口解析 + 工具拦截） | 正确的安全设计 | 收编为路径策略 + 工具层拦截保留 |
| 记忆/RAG 集成 | 架构位置正确 | 不动，evidence 增补 memory 来源类型 |
| 快路径的"预执行搜索"思路 | 避免 LLM 首轮不触发工具，方向正确 | 保留为 answer 型路径（搜索预取 + LLM 总结），出口过 gate |

---

## 3. 目标架构

### 3.1 总览

```
入口层（唯一）ChatOrchestrator
   ↓
消息改写    rewrite_number_selection（保留）
   ↓
路由层      PathStrategy 注册表（显式 priority + 显式路径类型契约）
   ↓
执行层      策略对象各自执行，统一产出 ReplyCandidate（含 evidence + 路径类型）
   ↓
质量关卡    ReplyGate（唯一出口，契约型）：
            ├─ 契约校验：answer 型必须经 LLM 处理（B类的根治方式：政策强制，非文本猜测）
            └─ A类收编：4道数字/痕迹溯源检查（仅对 answer 型生效）
   ↓
降级处理    反馈重答一次 → 回退证据+局限说明（两级）
   ↓
返回层      reply + tools_used + data_refs（真实现，可展示溯源）+ 质量埋点
```

核心思想一句话：**定义"合格回复"的不变量，在唯一出口按路径契约强制校验；旁路不是逃生通道，只是不同的执行策略，殊途同归。**

### 3.2 数据结构：证据集一等公民

```python
# core/assistant/models.py（新模块）

@dataclass
class Evidence:
    source_type: str    # "tool" | "search" | "user_message" | "history_tool" | "memory"
    source_id: str      # 工具名 / "searxng" / "mem0" / ...
    content: str        # 原文（数字溯源可信候选集的来源）
    locator: str | None # 可选：数据源定位（报告ID/工具调用记录），供前端回链

@dataclass
class ReplyCandidate:
    reply: str                    # 候选回复文本
    evidence: list[Evidence]      # 生成依据（谁产的回复谁负责附上）
    tools_used: list[str]
    route_id: str                 # "hitl" | "unsupported_asset" | "data_precheck"
                                  # | "fast_search" | "main_llm"
    route_type: str               # "answer"（面向用户问题的回答）
                                  # | "passthrough_allowed"（登记过的系统直出）
    llm_processed: bool           # answer 型必须为 True；由策略据实填写，gate 校验
    meta: dict                    # LLM响应对象、重试次数等

@dataclass
class CheckFailure:
    check: str          # 检查名
    reason: str         # 人读的原因

@dataclass
class GateResult:
    passed: bool
    failures: list[CheckFailure]
```

**设计要点**：

1. 现有防线已经在消费事实上的证据（tool_results / history_tool_contents / user_message），但没有被抽象成统一概念、各路径自己拼装。Evidence 使其成为显式契约——**每个策略产出回复时必须声明依据**，同时为 data_refs（§5 阶段 1）供料。
2. `route_type` 是 v2 的核心：**路径能否直出由注册契约决定，不由关卡分析文本来猜**（理由见 §3.3）。

### 3.3 ReplyGate：契约型唯一质量出口

```python
# core/assistant/reply_gate.py

class ReplyGate:
    def run(self, c: ReplyCandidate, user_message: str) -> GateResult:
        # ① 契约校验（治 B 类）
        if c.route_type == "answer":
            assert c.llm_processed is True        # answer 型契约上禁止裸直出
            # ② A 类溯源检查（仅 answer 型；收编现有4道，代码搬家不改逻辑）
            run(fabricated_tool_json,
                fabricated_tool_refs,
                unsourced_numbers,
                untraced_risky_numbers)
        else:  # passthrough_allowed：仅限注册表中登记的系统直出路径
            assert c.route_id in REGISTERED_PASSTHROUGH
```

**为什么用契约而不用文本启发式（v1 → v2 的关键修订）**：

v1 曾设计 `raw_passthrough`（回复与 evidence 文本重叠率 >70%）和 `link_dumping`（URL >3 个）两道检查，评审结论是**放弃进入阻断链路**：

- 重叠率既误伤"正常引用/总结"（天然高重叠，估值表等本就要求原样呈现），又放过"换行重排后的透传"——阈值给多少都修不准，这是启发式的固有脆弱性；
- 豁免机制会自我瓦解：要求原样呈现的是回复主体而非例外，豁免面大到关卡对主体失效，退化成仪式感。

**B 类的正确根治方式是政策强制**：快路径缺陷的本质是"回答型路径未经 LLM 直出"。注册表规定 `answer` 型必须经 LLM（快路径已改为"搜索预取 + LLM 总结"），直出只允许 `passthrough_allowed` 型且必须登记。gate 校验的是契约事实（bool + 白名单），不需要分析回复文本。

**passthrough_allowed 初始白名单**（登记制，新增需评审）：

| route_id | 直出内容性质 |
|---|---|
| hitl | 确认/拒绝的操作回执 |
| unsupported_asset | 品种不支持的系统提示 |
| data_precheck | 数据同步引导提示 |

> 文本统计类信号（重叠率、链接数、截断检测）不进阻断链路，降级为 §5 阶段 4 的**离线质量分析**，用于观察分布、为后续决策供数据，绝不在线误杀。

### 3.4 降级处理：两级，保功能可用

关卡不通过不等于拦截了事：

```
关卡失败
  → ① 反馈重答（一次）：失败原因反馈 LLM 重答
      （推广现有 _UNTRACED_RETRY 机制，实战已验证有效；快路径修复同型）
  → ② 回退证据：返回证据原文 + 如实说明局限
      （保功能可用——永不因关卡让用户拿不到任何东西）
```

v1 的第三级 "block" 不单独建模：两次处理后仍失败时，②的"局限说明"即包含道歉与引导拆分问题（沿用现有兜底文案），无需额外机制。

### 3.5 路径注册表：旁路从逃生通道变注册策略

```python
# core/assistant/paths.py

class PathStrategy(Protocol):
    route_id: str
    route_type: str                   # "answer" | "passthrough_allowed"
    priority: int                     # 显式优先级，替代代码书写顺序（S5）
    def match(self, msg: str, ctx: dict) -> bool
    async def execute(self, msg: str, ctx: dict) -> ReplyCandidate

REGISTRY: list[PathStrategy] = [
    HITLResolve(p=10, type="passthrough_allowed"),  # 确认/拒绝解析
    UnsupportedAssetCheck(p=20, type="passthrough_allowed"),
    DataSyncPrecheck(p=30, type="passthrough_allowed"),
    RecentSearchFastPath(p=40, type="answer"),      # 搜索预取 + LLM 总结（9.13 已修）
    MainLLMPath(p=100, type="answer"),              # LLM+工具循环（含 _do_chat 全部逻辑）
]
```

**新增路径的成本从"随便 return"变为**：实现接口 + 注册 + 声明 route_type + answer 型必经 LLM 与 gate。架构上不可能绕过（S1 的根治），也无法偷偷直出（B 类的根治）。

### 3.6 ChatOrchestrator：唯一管道

```python
async def handle(msg: str, ctx) -> dict:
    msg = rewrite_number_selection(msg, ctx.history)       # 保留
    for strategy in sorted(REGISTRY, key=lambda s: s.priority):
        if strategy.match(msg, ctx):
            candidate = await strategy.execute(msg, ctx)
            break
    result = ReplyGate().run(candidate, msg)               # 唯一出口
    if not result.passed:
        candidate = await degrade(candidate, result)       # 两级降级
    emit_metrics(candidate, result)                        # 埋点（S9）
    return {
        "reply": candidate.reply,
        "tools_used": candidate.tools_used,
        "data_refs": extract_refs(candidate.evidence),     # 真实现（S6）
    }
```

**chat_stream 合并**：不再是平行实现，而是同一 orchestrator 的输出适配器——pipeline 产出最终 reply 后按段落分块 yield（9.13 快路径流式修复已验证该输出形态可行）。

---

## 4. 关键设计决策记录（评审结论）

| # | 决策 | 理由 |
|---|------|------|
| D1 | B 类用**路径类型契约**根治，不用文本重叠率启发式 | 重叠率阈值固有脆弱（误伤+漏放）；契约是政策问题不是文本问题 |
| D2 | 不用逐项豁免机制，改用 `answer` / `passthrough_allowed` 两类契约 | 豁免面=回复主体时关卡失效；白名单登记制可评审、可审计 |
| D3 | 降级两级（重答→回退证据），不建三级 block | 第三级与现有兜底文案重复，建模无收益 |
| D4 | Evidence + data_refs 提到首批实施 | 它兑现"结论回链数据源"的对外功能承诺，不是内部重构 |
| D5 | 文本统计信号仅离线分析，不在线阻断 | 避免启发式误杀真实回复；先观测分布 |
| D6 | LLM-as-judge / LLM 意图分类 / 质量看板**不在本方案承诺** | 投机性最强；先做埋点拿到真实失败分布，数据证明值得再投，顺序不能反 |

---

## 5. 实施计划（按产品价值排序）

| 阶段 | 内容 | 解决 | 产品价值 |
|------|------|------|---------|
| **0 安全网** | 回归测试集（§5.1 的 10 条）先于任何代码改造 | S10 | 一切改造的前提，防修 A 坏 B |
| **1 证据集** | models.py（Evidence/ReplyCandidate 契约）+ 主/快路径产出 evidence + **data_refs 真实现**（前端可展示来源） | S6 | **直接兑现"结论高亮回链数据源"卖点** |
| **2 统一出口** | reply_gate.py（4 道防线抽离收编 + 契约校验）；chat() 全部出口过 gate；两级降级 | S1(chat侧)/S7 | 快路径类问题结构性不再发生 |
| **3 收口** | paths.py 注册表（priority + route_type）+ Orchestrator + chat_stream 合并为输出适配器 | S1(全部)/S2/S5 | 框架橱窗；贡献者加路径的制度约束 |
| **4 意图与度量** | 股票名走 stock_basic_info 全量+TTL缓存（替代硬编码），词典收敛单处；埋点落库（route 命中/gate 拦截/降级路径/文本信号离线统计）；意图关键词规则去留待埋点数据决策，暂保留 service 现状 | S4/S3部分/S9 | 平台化运营可见性；路由规则可审计 |
| **并行** | system prompt 治理（§7） | S8 | 不治理则持续制造 S3 类问题 |

**依赖**：阶段 0 必须最先；阶段 1 与 2 可紧接（2 消费 1 的契约）；3 依赖 2；4 可在 3 后。每阶段独立提交、可回退；只抽新模块 + 改出口，不整体搬迁 5000 行单文件。

### 5.1 回归测试集案例清单（阶段 0 交付物）

历史踩坑案例全部入库，每条含：输入、期望行为、历史缺陷描述：

1. "最近赛力斯有没有新车发布之类的计划，销量下跌的原因是什么" → answer 型路径，必须经 LLM 总结回答，不得裸透传搜索列表（9.13 快路径缺陷；由契约 `llm_processed=True` 强制）
2. 估值 Excel 生成请求 → 工具结果原样呈现（含下载链接），evidence 完整、data_refs 含文件来源（主路径 answer 型，原样呈现是 LLM 输出契约，不需要豁免）
3. 追问"它市占率是多少"（工具未返回该数据）→ 拦截 + 重答，不得编造
4. "牧原股份值得入手吗" → 合规话术（不给买卖建议），列出研究维度
5. 裸数字"2"回复 → 重写为选项选择，不二次确认
6. 数据未同步的股票数据问题 → data_precheck（passthrough_allowed 登记路径）提示同步，不调 LLM
7. 编造精确数字检测（"约35.20元"式包装）→ A 类拦截
8. 多轮引用历史工具数字 → 不误判为编造（history_tool 来源可信）
9. 风险自我辩论三观点互异（A9-P1 回归项，联动）
10. web_search 摘要无数值时问行业成本 → "搜索结果未包含该数值"+链接，不得填记忆数字

### 5.2 实施进度（阶段 0/1/2/3/4 已落地）

| 阶段 | 状态 | 落点 |
|------|------|------|
| 0 安全网 | ✅ 已落地 | `tests/unit/test_assistant_quality.py`（23 条纯单测：路径契约 / 四道防线 / 两级降级 / data_refs 去重 / 路径注册表）；§5.1 中依赖真实 LLM 的案例 4/5/6/9 属集成层，另行验证 |
| 1 证据集 | ✅ 已落地 | `core/assistant/models.py`（Evidence / ReplyCandidate / extract_data_refs）；主路径与快路径产出 evidence；返回体 `data_refs` 由真实证据导出（仅 tool/search 来源、按三元组去重） |
| 2 统一出口 | ✅ 已落地 | `core/assistant/defense.py`（四道防线+数字溯源从 service 物理收编为唯一事实源，净减约 481 行重复实现）；`core/assistant/reply_gate.py`（契约校验 + fallback_evidence 降级） |
| 3 收口 | ✅ 已落地 | `core/assistant/paths.py`（AssistantRequest / RegisteredPath / PathRegistry，priority 显式 + 同 priority 按 route_id 稳定排序 + register 查重 + resolve 首命中/全不命中抛错）；service 内六路径 handler（hitl 10 / unsupported_asset 20 / llm_unavailable 30 / fast_search 40 / data_precheck 50 / main_llm 100）+ `_route_candidate`/`_through_gate`/`_finalize_result` 单一管道；`chat()` 与 `chat_stream()` 降为 JSON/SSE 两个输出适配器（双实现再净减约 199 行）。双模式防线行为拉齐：流式补齐 untraced 重试；透明化附注统一在 gate 之后经 `meta["transparency_note"]` 追加；流式 done 事件新增真实 `data_refs`（封装层外层 done 透传） |
| 4 意图与度量 | ✅ 已落地（意图规则演进 ⏸ 待埋点数据决策） | `core/assistant/lexicon.py`（StockDirectory：stock_basic_info **全量**名称→代码 + TTL 6h 缓存 + asyncio.Lock 防击穿 + 刷新失败沿用旧缓存，替代硬编码 9 名单与每请求 regex 查库；A 股代码正则单一事实源；港股/美股词表与 `detect_unsupported_asset` 从 planned 物理收编，service/planned 共用）；`core/assistant/metrics.py`（`assistant_quality_events` 落库：route_id/priority/type、gate 通过与失败项、quality_signals（unsourced/untraced/fabricated 等纠错信号）、streaming、耗时，fire-and-forget 绝不影响主链路；管道 `_record_metrics` 在 chat/chat_stream 双适配器出口采集，含超时/取消/异常分支）；`database.py` 启动建索引。**意图关键词规则（快路径/预检查）保持 service 现状不动**，去留（保留 / 前置小模型 / 归还主 agent 工具选择）凭 1~2 周埋点数据决策（D6） |

**chat() 出口契约**：answer 型须 `llm_processed=True` 且过四道防线，失败自动回退为已登记的 `fallback_evidence`（局限说明 + 证据摘录）；passthrough 型 route_id 必须命中 `REGISTERED_PASSTHROUGH` 白名单（hitl / unsupported_asset / data_precheck / llm_unavailable / timeout / error / fallback_evidence）。

**既存失败（非本次引入，另案处理）**：`tests/services/test_intelligent_assistant_memory_filters.py`（收集期 ImportError：`_extract_memory_metadata_filters` 缺失）与 `tests/unit/app/test_intelligent_assistant_thread_summary.py` 中 1 例失败，均来自更早提交 `8c73d64f7`（项目记忆闭环：测试与实现签名在本分支不一致）；相关函数相对本次改动零变更。

---

## 6. 有效性评估（方案 → 问题对照）

| # | 问题 | 覆盖 | 结论 |
|---|------|------|------|
| S1 旁路绕过防线 | 阶段2+3 | ✅ 根治：所有路径必经 gate，架构上不存在绕过 |
| S2 双实现 | 阶段3 | ✅ 合并为单一管道 |
| S3 规则层抢决策权 | 阶段4 部分 | ⚠️ 路由集中可审计、词典全量化、埋点已上线；决策权是否进一步交给 LLM（意图规则演进），凭埋点 1~2 周真实失败分布决策（D6） |
| S4 词典硬编码 | 阶段4 | ✅ 全量索引+缓存 |
| S5 优先级=代码顺序 | 阶段3 | ✅ priority 显式化 |
| S6 data_refs 空壳 | 阶段1 | ✅ evidence 结构化后导出，兑现可展示溯源 |
| S7 防线不可复用 | 阶段2 | ✅ 抽为独立模块 |
| S8 prompt 膨胀 | 并行治理 | 🟡 独立工作项（§7），不做会持续复发 |
| S9 无度量 | 阶段4 | ✅ 埋点；文本信号离线化 |
| S10 无回归测试 | 阶段0 | ✅ 测试集先行 |

**B 类（降级/裸透传）结论**：契约型根治。answer 型路径未经 LLM 在关卡处不可能通过（`llm_processed` 是策略填写的契约事实 + route_id 白名单），不依赖脆弱的文本判断。

**C 类（意图）结论——已知边界**："回复是否回应了问题"没有廉价的确定性校验（行业性难题）。本方案做到路由集中可审计、词典全量化、埋点可见异常率；**是否引入 LLM 裁判取决于阶段 4 采集的真实失败分布，不在当前承诺内**。只能缓解，是否继续投入由数据决定。

**总评**：10 项问题中 8 项根治、1 项数据驱动缓解（S3）、1 项并行治理（S8）。"发现一个修一个"模式在阶段 2+3 完成后被结构性终结；同时阶段 1 独立交付一个用户可见的产品能力（可展示溯源）。

---

## 7. 配套工作：system prompt 治理（与阶段 1 并行）

独立于本方案但必须并行，否则 3000+ 字 prompt 持续膨胀并持续制造 S3 类问题：

1. **分层重组**：核心身份 → 领域边界 → 数据纪律（防编造细则合并去重，与 A 类检查项对齐）→ 合规 → 工具指引
2. **规则去重**：工具使用原则 3 处重复合并为 1 处
3. **动态注入保持**：当前日期/交易日/股票上下文/报告清单等动态段维持现有注入机制
4. **验收**：字数缩减 ≥30%，语义零丢失（对照 §5.1 回归测试集逐条验证）

---

## 8. 风险与对策

| 风险 | 对策 |
|------|------|
| 重构 5000+ 行单文件引入新缺陷 | 只抽新模块+改出口，不搬全文件；每阶段独立提交可回退；阶段 0 测试集先行 |
| 策略误填 `llm_processed=True` 绕过契约 | 该字段只能由路径基类在真实调用 LLM 后置位，业务代码不可直接赋值；code review + 测试断言 |
| passthrough 白名单膨胀变后门 | 登记制 + 新增需评审 + 埋点记录各 route 命中率，白名单变更在决策记录留痕 |
| C 类残留 | 接受数据驱动缓解；阶段 4 埋点监控，误路由率高到值得时再按 D6 立项 |
| Demo 前误改主链路 | 已冻结：仅文档与独立新模块可先行，出口改造 Demo 后动 |

---

## 9. 决策记录

- **2026-09-13 v1**：方案初稿（启发式关卡 + 逐项豁免 + 三级降级）。
- **2026-09-13 v2**：评审修订。① B 类改契约强制、删除文本启发式与豁免机制（D1/D2）；② 降级收敛两级（D3）；③ Evidence/data_refs 提至首批（D4）；④ 文本信号离线化（D5）；⑤ LLM 裁判类移出承诺、改数据驱动（D6）。
- 快路径缺陷（触发事件）修复 `_summarize_search_result` 已先行落地，不依赖本方案。
- 排期决策：Demo（9-16）前冻结主链路；Demo 后按阶段 0→1→2 启动。
- 本方案属 A11 工作线（智能助手质量架构），与 A10（估值交付物）、A9-P1（风险辩论）、A3（并行开局）互不阻塞。

---

## 附：术语表

| 术语 | 定义 |
|------|------|
| 旁路/快路径 | 前置规则层中命中即返回、不进入主 LLM 循环的分支 |
| 证据集（evidence） | 一条回复生成所依据的全部原文（工具返回/搜索结果/用户消息/历史工具/记忆） |
| 路径类型契约 | 路径注册时声明 `answer`（必经 LLM + 全套溯源检查）或 `passthrough_allowed`（登记制系统直出） |
| 不变量 | 对任何 answer 型路径产出的回复都成立的合格条件（经 LLM 加工、数字可溯源） |
| 降级处理 | 关卡不通过时的两级处理：反馈重答一次 → 回退证据+局限说明 |
