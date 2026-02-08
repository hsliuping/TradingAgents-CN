# 智能助手设计（Agent 自主编排模式）

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 需求设计 |
| 日期 | 2026-02-07 |
| 优先级 | 中 |

---

## 🎯 背景与需求

### 核心痛点

现有 v2.0 工作流引擎采用**固定流程编排**，所有分析任务走相同的预定义步骤。但以下场景无法用固定流程处理：

1. **事件驱动分析**：突发事件对股票的影响分析
2. **探索性查询**：初步选股、板块筛选等轻量需求
3. **临时问答**：用户随机提问，不需要完整报告

### 典型场景

```
场景1 - 热点事件：
  "DeepSeek 发布了新模型，对 A 股 AI 板块有什么影响？"
  → 无法预设固定流程（不知道涉及哪些股票、需要哪些维度）

场景2 - 初步选股：
  "帮我从白酒板块里初步筛选几只值得关注的"
  → 不需要完整的多 Agent 深度分析，只要快速筛选

场景3 - 临时追问：
  "美联储降息了，哪些板块受益？"
  → 需要跨板块的宏观分析，现有工作流是单股票分析

这些场景的共同特点：
  ❌ 无法预设固定流程（事件千变万化）
  ❌ 不知道要分析哪些股票（需要先判断关联性）
  ❌ 分析维度不确定
  ✅ 但现有的数据和工具都有，只是组合方式不固定
```

---

## 🏗️ 技术架构

### 核心机制：Function Calling / Tool Use

```
┌─────────────────────────────────────────────┐
│              智能助手 Agent                    │
│                                             │
│  输入：用户自然语言问题                        │
│                                             │
│  处理过程（ReAct 模式）：                      │
│    1. 理解用户意图                            │
│    2. 规划需要哪些步骤                         │
│    3. 选择合适的工具                           │
│    4. 执行工具调用                            │
│    5. 根据结果决定下一步                       │
│    6. 汇总生成回答                            │
│                                             │
│  输出：自然语言回答 + 结构化数据（可选）         │
│                                             │
└─────────────────────────────────────────────┘
```

### 工具列表（包装现有能力）

```python
# 数据查询类工具
tools = [
    {
        "name": "get_stock_list",
        "description": "获取指定板块/行业的股票列表",
        "when_to_use": "当用户提到某个板块或行业，需要知道包含哪些股票时",
        "parameters": {"sector": "板块名称，如'白酒'、'半导体'"}
    },
    {
        "name": "get_financial_summary",
        "description": "获取股票核心财务指标（PE/PB/ROE/营收增长率等）",
        "when_to_use": "当需要判断股票基本面、估值水平时",
        "parameters": {"code": "股票代码"}
    },
    {
        "name": "get_technical_summary",
        "description": "获取股票技术面摘要（均线/MACD/KDJ/成交量等）",
        "when_to_use": "当需要判断短期走势、买卖信号时",
        "parameters": {"code": "股票代码"}
    },
    {
        "name": "search_news",
        "description": "搜索与关键词相关的最新新闻",
        "when_to_use": "当需要了解某个事件的详情或影响时",
        "parameters": {"keyword": "搜索关键词"}
    },
    {
        "name": "get_market_quotes",
        "description": "获取股票实时/最新行情数据",
        "when_to_use": "当需要查看股票当前价格、涨跌幅时",
        "parameters": {"codes": "股票代码列表"}
    },
    # 分析类工具
    {
        "name": "compare_stocks",
        "description": "多只股票的多维度对比分析",
        "when_to_use": "当用户要对比多只股票的优劣时",
        "parameters": {"codes": "股票代码列表", "dimensions": "对比维度"}

### 执行流程示例

```
用户: "中芯国际被美国制裁了，影响哪些股票？"
         │
         ▼
Agent 思考（ReAct）:
  "用户关心制裁事件对关联股票的影响，我需要：
   1. 先了解事件详情
   2. 找到关联的半导体板块股票
   3. 分析哪些公司对中芯依赖度高
   4. 查看这些股票的当前技术面位置
   5. 综合给出影响分析"
         │
         ▼
Agent 自主调用工具:
  → search_news("中芯国际 制裁")         → 了解事件详情
  → get_stock_list("半导体")              → 获取关联股票
  → get_financial_summary(["长电科技"...]) → 看依赖度
  → get_technical_summary(["长电科技"...]) → 看当前位置
         │
         ▼
Agent 汇总回答:
  "中芯国际被制裁，直接影响的是这几家供应商...
   其中长电科技营收占比最高约30%，短期冲击较大...
   但北方华创作为国产替代受益方，反而可能..."
```

### 与现有工作流的协作

```
轻问题 → 智能助手直接回答（秒级响应）
  "光伏板块最近怎么样？" → 快速查数据，直接回答

重分析 → 智能助手触发工作流（分钟级响应）
  "帮我详细分析一下隆基绿能" → 触发完整多Agent分析
  "我帮你启动了隆基绿能的深度分析，预计 5 分钟出结果"
```

---

## 💻 技术实现

### 新增模块

| 文件/目录 | 说明 |
|----------|------|
| `app/services/intelligent_assistant_service.py` | 核心编排逻辑 |
| `app/routers/intelligent_assistant.py` | API 路由（对话接口） |
| `app/schemas/intelligent_assistant.py` | 请求/响应模型 |
| `core/agents/assistant/` | 助手 Agent 实现 |
| `core/agents/assistant/tool_registry.py` | 工具注册和描述 |

### 核心类设计

```python
class IntelligentAssistantService:
    """智能助手服务 - Agent 自主编排模式"""

    def __init__(self, llm_client, tool_registry, db):
        self.llm_client = llm_client        # 统一 LLM 客户端
        self.tool_registry = tool_registry   # 工具注册表
        self.db = db                         # MongoDB

    async def chat(self, user_message: str, context: dict) -> dict:
        """
        处理用户对话

        1. 将用户消息 + 工具列表发给 LLM
        2. LLM 返回工具调用请求（Function Calling）
        3. 执行工具调用，获取结果
        4. 将结果反馈给 LLM
        5. 重复 2-4 直到 LLM 给出最终回答
        6. 返回回答 + 引用的数据
        """
        pass
```

### API 设计

```
POST /api/assistant/chat
  请求: { "message": "用户问题", "conversation_id": "会话ID" }
  响应: { "reply": "助手回答", "tools_used": [...], "data_refs": [...] }

GET /api/assistant/conversations
  → 获取历史会话列表

GET /api/assistant/conversations/{id}
  → 获取单个会话详情
```

### 前端改动

| 位置 | 改动 |
|------|------|
| 全局 | 新增"智能助手"对话入口（悬浮按钮或侧边栏） |
| 对话界面 | 支持多轮对话、工具调用过程展示、数据卡片 |
| 报告详情页 | 解读功能集成到助手对话（复用同一入口） |

---

## 🔐 合规约束

与报告解读系统共享相同的合规约束：
- 不提供买卖建议、目标价、仓位建议
- System Prompt 中嵌入合规要求
- 所有工具返回的数据不含投资建议

---

## 🧪 LLM 选型

| 能力 | 要求 |
|------|------|
| Function Calling 支持 | ✅ 必须（核心能力） |
| 多轮对话 | ✅ 必须 |
| 中文理解 | ✅ 必须 |
| 推理能力 | ❌ 不需要推理 LLM |

**推荐模型**：
- GPT-4o（Function Calling 最成熟）
- Claude Sonnet（Tool Use 能力强）
- DeepSeek-V3（中文优秀，成本低）

**不需要推理 LLM 的原因**：
智能助手的主要工作是意图理解 + 工具选择 + 结果汇总，属于信息组织，不是复杂逻辑推理。

---

## 📊 开发计划

```
Phase 1: 基础框架（1-2 周）
  → 工具注册表 + LLM Function Calling 集成
  → 单轮问答（无对话历史）

Phase 2: 对话能力（1 周）
  → 多轮对话 + 会话管理
  → 上下文保持

Phase 3: 工作流桥接（1 周）
  → trigger_full_analysis 工具
  → 异步任务状态回传

Phase 4: 前端 UI（1-2 周）
  → 对话界面
  → 工具调用可视化
```

---

## 🔗 相关文档

- [双方向架构设计](./two-direction-architecture.md)
- [工具描述增强规范](./tool-description-enhancement.md)
- [报告解读系统设计](./report-interpretation-system.md)
- [v2.1 Agent Skill 评估](../v2.1/agent-skill-technology-assessment.md)

---

**创建日期**: 2026-02-07
**最后更新**: 2026-02-07
