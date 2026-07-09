# Skill 缺口感知与通知系统设计文档

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 设计中 |
| 日期 | 2026-02 |
| 目标 | Agent 运行时自动检测工具缺口，分析问题并通知用户决策，而非自动创建 |

---

## 1. 概述

### 1.1 背景

在 Agent 执行分析任务时，可能遇到以下情况：
- **工具未找到**：LLM 尝试调用的工具不存在于当前 Agent 的工具列表中
- **工具执行失败**：工具存在但运行时报错（API 失效、参数不匹配等）

当前系统对这些情况仅做日志记录，Agent 会降级处理（LLM 尝试用其他方式完成分析），但**用户对此完全无感知**。

### 1.2 设计理念

借鉴 OpenClaw/NanoBot 的"Agent 自我完善"理念，但采取**保守策略**：

> **Agent 只负责"发现问题"，用户决定"是否创建"**

- ✅ 自动检测缺口
- ✅ 后台分析问题原因和建议方案
- ✅ 通知用户（WebSocket + 通知中心）
- ❌ 不自动创建 Skill（稳定性和可控性优先）

---

## 2. 系统架构

```
Agent 执行工具调用
    │
    ├── 工具未找到 ──┐
    │                │
    ├── 工具执行失败 ─┤
    │                ▼
    │        SkillGapDetector（异步、非阻塞）
    │            │
    │            ├── 去重检查（30 分钟内同一工具不重复上报）
    │            ├── 已忽略检查（用户 dismiss 后 30 天不再上报）
    │            │
    │            ▼
    │        SkillGapService
    │            │
    │            ├── 保存缺口报告到 MongoDB
    │            ├── [可选] LLM 分析问题 + 生成 Skill 建议
    │            │
    │            ▼
    │        NotificationsService
    │            │
    │            ├── WebSocket 实时推送
    │            └── 通知中心存储
    │
    ▼
Agent 继续执行（不阻塞）
```

---

## 3. 检测点

两个检测点位于 `core/agents/base.py` 的 `_execute_tool_calls()` 方法中：

### 检测点 1: 工具未找到

```python
# base.py line ~990
if tool_result is None:
    tool_result = f"未找到工具: {tool_name}"
    logger.warning(f"⚠️ [{self.agent_id}] {tool_result}")
    # >>> 新增：上报缺口
    await SkillGapDetector.report_gap(
        gap_type="tool_not_found",
        tool_name=tool_name,
        agent_id=self.agent_id,
        context=state
    )
```

### 检测点 2: 工具执行失败

```python
# base.py line ~983
except Exception as e:
    logger.error(f"❌ [{self.agent_id}] 工具 {tool_name} 执行失败: {e}")
    tool_result = f"工具执行失败: {str(e)}"
    # >>> 新增：上报缺口
    await SkillGapDetector.report_gap(
        gap_type="tool_execution_error",
        tool_name=tool_name,
        agent_id=self.agent_id,
        error=str(e),
        context=state
    )
```

**关键设计**：`report_gap()` 是 fire-and-forget，不阻塞当前分析任务。

---

## 4. 数据模型

### 4.1 MongoDB 集合: `skill_gap_reports`

```python
{
    "report_id": "gap_20260225_001",           # 唯一 ID
    "user_id": "admin",                         # 所属用户
    "status": "pending",                        # pending → reviewed → creating → resolved → dismissed

    # 缺口来源
    "source": {
        "agent_id": "market_analyst",           # 哪个 Agent 遇到的
        "agent_name": "市场分析师",
        "workflow_id": "wf_xxx",                # 哪个工作流
        "workflow_name": "默认股票分析",
        "task_id": "task_xxx",                  # 哪个分析任务
        "node_id": "node_xxx",                  # 哪个节点
    },

    # 缺口详情
    "gap": {
        "type": "tool_not_found",               # tool_not_found | tool_execution_error
        "tool_name": "get_insider_trading",      # LLM 尝试调用的工具名
        "error_message": "",                     # 错误信息（execution_error 时）
        "tool_call_args": {},                    # LLM 传入的参数
        "context_summary": "分析 600519 时...",   # 上下文摘要
    },

    # LLM 分析结果（第二期）
    "analysis": {
        "problem_description": "Agent 需要内幕交易数据...",
        "suggested_skill": {
            "name": "内幕交易数据查询",
            "description": "查询指定股票的内幕交易记录",
            "input_params": ["symbol: str"],
            "output_format": "dict",
            "data_source_suggestion": "AkShare ak.stock_inner_trade_xq()",
        },
        "alternative_solutions": [
            "将 get_insider_trading 工具绑定到该 Agent",
            "使用现有的 get_stock_news 工具替代"
        ],
        "confidence": 0.85,
    },

    # 时间戳
    "created_at": "2026-02-25T10:30:00Z",
    "updated_at": "2026-02-25T10:30:00Z",
    "resolved_at": null,
    "expires_at": "2026-03-04T10:30:00Z",       # 7 天后自动过期
}
```

---

## 5. 核心模块

### 5.1 SkillGapDetector（单例）

**位置**: `core/tools/external/skill_gap_detector.py`

```python
class SkillGapDetector:
    """Skill 缺口检测器（单例）"""

    _instance = None
    _recent_reports: Dict[str, datetime]  # 去重缓存: tool_name → 最近上报时间
    _dismissed_tools: Dict[str, datetime] # 已忽略缓存: tool_name → 忽略时间

    @classmethod
    async def report_gap(
        cls,
        gap_type: str,           # "tool_not_found" | "tool_execution_error"
        tool_name: str,
        agent_id: str,
        error: str = "",
        context: dict = None,
    ) -> None:
        """
        上报工具缺口（fire-and-forget）

        特性：
        - 异步非阻塞，不影响当前任务执行
        - 30 分钟内同一 tool_name 不重复上报
        - 用户已 dismiss 的 tool_name 30 天内不再上报
        """
        ...

    async def _should_report(self, tool_name: str) -> bool:
        """去重 + 忽略检查"""
        ...

    async def _create_report(self, gap_type, tool_name, agent_id, error, context):
        """创建缺口报告并触发通知"""
        ...
```

### 5.2 SkillGapService

**位置**: `app/services/skill_gap_service.py`

```python
class SkillGapService:
    """Skill 缺口管理服务"""

    async def list_gaps(self, user_id: str, status: str = None) -> List[dict]:
        """获取缺口报告列表"""

    async def get_gap(self, report_id: str) -> dict:
        """获取单个缺口报告详情"""

    async def dismiss_gap(self, report_id: str) -> None:
        """忽略缺口（标记 dismissed，30 天内不再上报同名工具）"""

    async def resolve_gap(self, report_id: str, skill_id: str = None) -> None:
        """标记缺口已解决（关联创建的 Skill ID）"""

    async def analyze_gap(self, report_id: str) -> dict:
        """[第二期] LLM 深度分析缺口，生成 Skill 建议方案"""

    async def create_skill_from_gap(self, report_id: str) -> str:
        """从缺口报告预填参数，跳转到 Skill 生成工坊"""
```

---

## 6. REST API

**端点前缀**: `/api/skill-gaps`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | 获取缺口报告列表（支持 status 筛选） |
| GET | `/{report_id}` | 获取单个报告详情 |
| POST | `/{report_id}/dismiss` | 忽略此缺口 |
| POST | `/{report_id}/resolve` | 标记已解决 |
| POST | `/{report_id}/analyze` | [第二期] 触发 LLM 深度分析 |
| POST | `/{report_id}/create-skill` | 从缺口创建 Skill（跳转到 Skill 工坊） |
| GET | `/stats` | 缺口统计（按 Agent / 按类型 / 按状态） |

---

## 7. 通知集成

复用现有通知基础设施：

```python
# 通知格式
notification = {
    "type": "alert",
    "source": "skill_gap_detector",
    "title": "🔧 发现工具缺口",
    "message": "市场分析师在执行「默认股票分析」时需要工具 get_insider_trading，但该工具不存在。",
    "data": {
        "report_id": "gap_20260225_001",
        "action_url": "/workflow/skill-gaps/gap_20260225_001",
    },
    "level": "warning",
}

# 通过 NotificationsService 发送
await NotificationsService.create_and_publish(db, notification)
```

**通知渠道**：

| 渠道 | 实现 | 说明 |
|------|------|------|
| WebSocket | `NotificationsService` 内置 | 实时推送到前端 |
| 通知中心 | `notifications` 集合 | 持久化存储，用户可查看历史 |
| 邮件 | [第二期] | 通过 SMTP 配置发送 |

---

## 8. 用户交互流程

```
1. Agent 执行分析任务
   └── 检测到工具缺口 → 后台上报（不阻塞）

2. 用户收到 WebSocket 通知
   └── 通知中心出现红点 + 弹窗提醒

3. 用户查看缺口详情
   ├── 问题描述：哪个 Agent 在什么场景下需要什么工具
   ├── [第二期] Skill 建议方案：建议创建什么功能的 Skill
   └── 可选操作：
       ├── 「创建 Skill」→ 跳转到 Skill 工坊，参数预填
       ├── 「忽略」→ 30 天内不再提醒同名工具
       └── 「查看替代方案」→ 显示可能的替代工具

4. 用户选择创建 Skill
   └── Skill 工坊打开，预填：
       ├── 工具名称
       ├── 功能描述
       ├── 输入参数
       └── 来源 Agent 和工作流信息
```

---

## 9. 安全和性能考虑

| 考虑点 | 方案 |
|--------|------|
| **不阻塞分析** | `report_gap()` 是 fire-and-forget，不影响当前任务执行 |
| **防止通知风暴** | 同一 `tool_name` 30 分钟内只上报一次 |
| **LLM 调用成本** | 分析使用最小模型（如 deepseek-chat），单次 ~200 token |
| **后台 LLM 失败** | 降级：保存原始缺口信息，通知不包含 Skill 建议方案 |
| **用户不处理** | pending 状态的报告 7 天后自动标记为 expired |
| **重复缺口** | 用户 dismiss 后 30 天内不再上报同名工具 |

---

## 10. 实现计划

### 第一期（核心闭环）

1. `SkillGapDetector` — 在 `_execute_tool_calls()` 中挂载检测
2. `skill_gap_reports` MongoDB 集合
3. 通知推送（WebSocket + 通知中心）
4. REST API（列表 / 详情 / 忽略 / 创建）
5. 前端缺口列表页

### 第二期（增强）

6. LLM 深度分析（生成 Skill 建议方案）
7. 预填 Skill 工坊参数
8. 缺口统计仪表盘
9. 邮件通知
10. 自动聚合相似缺口

---

## 11. 与现有系统的集成

| 模块 | 集成方式 |
|------|----------|
| `core/agents/base.py` | 在 `_execute_tool_calls()` 两个错误分支中调用 `SkillGapDetector.report_gap()` |
| `NotificationsService` | 复用 `create_and_publish()` 推送通知 |
| `WebSocket` | 自动通过 `NotificationsService` 内部的 WebSocket 推送 |
| `SkillGenerationService` | 从缺口报告预填 `start_session()` 参数 |
| `notifications` 集合 | 复用，`type="alert"`, `source="skill_gap_detector"` |
| `skill_gap_reports` 集合 | **新增**，存储缺口分析报告 |

---

## 12. 相关文档

- [Skill 生成系统](./skill-generation-system.md) — Skill 创建管线
- [MCP 支持](./mcp-support.md) — 外部工具接入
- [AI 工作流生成](./ai-workflow-generation.md) — 工作流级别的 Agent/工具编排

---

## 13. 实施现状与已知限制（2026-06-24 更新）

### ✅ 已生效的检测点

- **`core/agents/base.py` 的工具调用层**：在 `_execute_tool_calls()` 中已接入 `SkillGapDetector.report_gap()`，捕获 `tool_not_found` 和 `tool_execution_error` 两种场景。**仅对走 base.py 链路的多智能体研究流程（单股研究、批量分析、Agent 工坊试跑）生效。**
- **`core/llm/tool_normalizer.py`**：在 `ToolCallNormalizer.aexecute_tool_call()` 中已接入缺口上报和执行日志，覆盖**智能助手发起 tool_call 但工具不存在/执行失败/超时**的场景。

### ❌ 已尝试但未生效的方案（已移除）

针对**「智能助手运行时，LLM 没有发起 tool_call，直接在文本回复里坦白没有相关工具」** 的场景（典型例子：用户问"今天的龙虎榜"，LLM 直接回复"系统没有龙虎榜个股席位明细查询工具"），我们曾尝试两种方案，**均未达预期效果，现已全部回滚**：

#### 方案 A：正则启发式回扫 LLM 回复（已移除）

实现位置：曾在 `app/services/intelligent_assistant_service.py` 的 `_maybe_report_capability_gap()`。

做法：在 `_do_chat` / `_chat_stream` 末尾，对最终 reply 用关键短语列表（"暂不支持"、"我无法直接"、"目前没有"…）+ 正则（`(没有|缺少)...(工具|接口|能力)`、`(无法|不能).*(查询|获取)`）做模式匹配，命中则上报。

失败原因：
1. **召回率低**：LLM 表达极其多样（"坦诚说"、"实话说"、"做不到"、emoji 拼接……），关键短语库永远不全。
2. **精准率也低**：很多正常回答里也会出现"无法预测"、"暂时没有合适的"等组合，造成误报。
3. 即便加大模式覆盖，依然漏掉本场景中"⚠️ 坦诚说：目前系统没有直接的「龙虎榜个股席位明细」查询工具"这类多层修饰的真实样例。

#### 方案 B：注入"能力缺口上报"元工具让 LLM 主动调用（已移除）

实现位置：曾在 `app/services/intelligent_assistant_service.py` 注入元工具 `report_capability_gap(capability_name, user_request, reason)`，并在 system prompt 中要求 LLM 「判断缺少能力时必须先调用此元工具」。

失败原因：
1. **LLM 不愿调用**：模型倾向于"温柔地"完成回答（推荐替代方案、给板块龙头清单），而不是承认能力缺失并触发"额外动作"。
2. **指令权重低**：在已经塞满工具列表 + 多页系统提示的上下文里，单条"必须调用 X"的指引很容易被忽略。
3. **越是高质量模型越倾向自圆其说**：模型自己就能"补救"用户需求，会绕过这条规则。

### 结论

智能助手运行时的"零工具调用 + 软拒答"缺口感知，**当前没有可靠的自动化方案**。已确认无效的方案包括：
- 正则匹配 LLM 回复文本
- 通过 system prompt 强制 LLM 主动调元工具上报

### 候选后续方向（暂未实施）

如果未来要再尝试，方向应该是：
1. **离线人工巡检**：定期人工扫描智能助手对话日志（已通过执行日志 / 消息历史落库），从中挑出"软拒答"样本，手工创建缺口报告。
2. **二阶段 LLM 评判（成本较高）**：每次智能助手回复后，再用一个轻量 LLM 调用专门判定"本次回复是否暗示能力缺失"，命中则上报。但要权衡延迟 / token 成本 / 误报率。
3. **用户侧反馈**：允许用户在不满意的回复下点击"这功能缺失"按钮，把缺口当作用户反馈显式上报。

```

