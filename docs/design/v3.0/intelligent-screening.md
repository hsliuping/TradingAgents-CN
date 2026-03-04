# 智能筛选（Intelligent Stock Screening）

## 📋 文档信息

| 项目 | 内容 |
|------|------|
| 版本 | v1.0 |
| 状态 | 设计完成，待实现 |
| 日期 | 2026-03 |
| 目标 | 在股票筛选页面新增"智能筛选"Tab，通过 LLM 多轮对话实现自然语言选股，每次返回 5 只股票 |

---

## 1. 概述

### 1.1 背景

现有股票筛选页面（`frontend/src/views/Screening/index.vue`）提供基于条件组合的传统筛选功能（行业、市值、PE、PB、ROE、涨跌幅等），用户需要手动配置多个筛选条件。

对于不熟悉财务指标的用户，或有模糊需求的场景（如"帮我找几只最近资金持续流入的低估值白马股"），传统筛选无法满足。

### 1.2 目标

在股票筛选页面新增 **智能筛选** Tab（与原有"传统筛选"并列），提供：

1. **自然语言选股**：用户用日常语言描述选股条件，LLM 理解后调用工具获取数据并推荐股票
2. **每次返回 5 只股票**：结构化展示，包含代码、名称、核心指标、推荐理由
3. **多轮对话记忆**：用户可追问调整条件（如"换成科技板块的""PE 再低一点"），系统保持上下文
4. **工具调用透明**：展示 LLM 调用了哪些工具获取数据，增强可信度

### 1.3 与智能助手的区别

| 维度 | 智能助手 | 智能筛选 |
|------|---------|---------|
| **定位** | 通用投资教练，回答任意问题 | 专注选股推荐 |
| **输出格式** | 自由文本 Markdown | 结构化股票卡片 + 理由 |
| **每次结果** | 不限 | 固定 5 只股票 |
| **需求确认** | 无 | **先分析需求 → 提出改进建议 → 用户确认后再筛选** |
| **对话记忆** | 当前无（仅持久化，不传给 LLM） | **完整多轮记忆**（历史传给 LLM） |
| **系统提示词** | 通用投资教练风格 | 专注选股的专家风格 |
| **会话存储** | `assistant_conversations` | `screening_conversations`（独立） |
| **后续操作** | 无 | 可直接发起分析、加自选 |

---

## 2. 系统架构

```
前端 Screening/index.vue
├── Tab: 传统筛选（现有功能，不变）
└── Tab: 智能筛选（新增）
     ├── 对话区域（类似智能助手的聊天 UI）
     ├── 股票结果卡片（每次 5 只，结构化展示）
     └── 操作按钮（分析、加自选、查看详情）

         │ POST /api/screening/intelligent/chat
         ▼
后端 IntelligentScreeningService
├── 构建系统提示词（选股专家 + 工具列表 + 当前日期）
├── 拼接对话历史（最近 N 轮）作为 context
├── 调用 UnifiedLLMClient.achat() + function calling
├── 解析 LLM 返回 → 提取结构化股票列表
└── 持久化对话到 screening_conversations
```

---

## 3. 后端设计

### 3.0 复用策略

智能筛选服务**大量复用**智能助手 (`app/services/intelligent_assistant_service.py`) 的基础设施：

| 模块 | 复用方式 | 来源 |
|------|---------|------|
| LLM 配置解析 | 直接 import | `_get_assistant_llm_config()` |
| 交易日计算 | 直接 import | `_get_latest_trade_date()` |
| 超时常量 | 直接 import | `ASSISTANT_TIMEOUT_SECONDS` |
| LLM 客户端 | 同样的 `UnifiedLLMClient.from_config()` 模式 | `core.llm` |
| 工具注册表 | 同样的 `get_tool_registry()` + `tool_metadata_list_to_openai()` | `core.tools` |
| 会话持久化 | 同样的 `$push` + `$slice` MongoDB 模式 | 参考 `save_assistant_message()` |
| 请求 Schema | 直接复用 `ChatRequest` | `app.schemas.intelligent_assistant` |

**不复用（需新建）的部分**：

| 模块 | 原因 |
|------|------|
| 两阶段 `chat()` 流程 | 核心差异：confirmation → result |
| `_is_new_screening_request()` | 新逻辑：判断是否走确认流程 |
| 系统提示词 | 完全不同：选股专家 vs 投资教练 |
| 多轮记忆 | 助手不传历史给 LLM，筛选必须传 |
| `_extract_stocks()` | 新逻辑：从回复中提取结构化股票 |
| `phase` + `stocks` 响应字段 | 新增字段 |
| 工具筛选（5 类） | 助手用全部工具，筛选只用选股相关的 |

### 3.1 服务模块

**文件**: `app/services/intelligent_screening_service.py`

```python
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from motor.motor_asyncio import AsyncIOMotorDatabase

# ========== 复用智能助手的基础设施 ==========
from app.services.intelligent_assistant_service import (
    _get_assistant_llm_config,       # LLM 配置解析（数据库 → LLMConfig）
    _get_latest_trade_date,           # A 股最近交易日
    ASSISTANT_TIMEOUT_SECONDS,        # 整体超时（默认 120s）
)
from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.llm import UnifiedLLMClient

logger = logging.getLogger(__name__)

# 会话历史最大条数（每用户）
SCREENING_CONVERSATION_LIMIT = 50
# 每次请求最多传给 LLM 的历史消息条数
MAX_CONTEXT_MESSAGES = 20


class IntelligentScreeningService:
    """
    智能筛选服务 — LLM 多轮对话选股

    复用智能助手的 LLM 配置、工具注册表、超时机制等基础设施，
    新增两阶段流程（需求确认 → 执行筛选）和多轮记忆。
    """

    def __init__(self, db: AsyncIOMotorDatabase):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._openai_tools: Optional[list] = None
        self._tool_functions: Optional[dict] = None

    async def _ensure_client(self) -> bool:
        """
        懒加载 LLM 客户端和工具（复用智能助手的 LLM 配置解析）

        与智能助手的区别：只加载选股相关的 5 类工具，而非全部工具。
        """
        if self._llm_client is not None:
            return True

        # 复用智能助手的 LLM 配置解析
        llm_config = await _get_assistant_llm_config(self._db)
        if not llm_config:
            return False

        try:
            self._llm_client = UnifiedLLMClient.from_config(llm_config)
        except Exception as e:
            logger.error(f"[智能筛选] 创建 LLM 客户端失败: {e}", exc_info=True)
            return False

        # 只加载选股相关的工具（区别于智能助手加载全部工具）
        registry = get_tool_registry()
        screening_categories = ["market", "fundamentals", "news", "china", "technical"]
        all_metadata = registry.list_all()
        screening_metadata = [
            m for m in all_metadata
            if m.fc_enabled and m.category in screening_categories
        ]
        self._openai_tools = tool_metadata_list_to_openai(screening_metadata)

        self._tool_functions = {}
        for tool in screening_metadata:
            if tool.parameters:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(f"[智能筛选] 已加载 {len(self._openai_tools)} 个选股工具")
        return True

    async def chat(self, user_id: str, message: str) -> dict:
        """
        核心方法：处理用户的选股请求（两阶段流程）

        阶段 1 — 需求确认（首次提出新需求时）：
        1. 获取对话历史
        2. 判断是否为"新需求"（首次对话 / 用户发起了新的选股主题）
        3. 如果是新需求：LLM 分析需求 → 返回理解 + 改进建议 → 等待用户确认
        4. 返回 phase="confirmation"，前端展示确认 UI

        阶段 2 — 执行筛选（用户确认后）：
        1. 用户选择"按原需求筛选"或"添加改进条件"
        2. LLM 调用工具获取数据 → 返回 5 只股票
        3. 返回 phase="result"

        后续追问（如"PE 再低点"）直接执行，不再走确认流程。
        """
        client = await self._ensure_client()

        # 1. 获取历史对话
        history = await self._get_context_messages(user_id)

        # 2. 系统提示词
        system_prompt = self._get_system_prompt()

        # 3. 构建消息列表（关键区别：包含历史！）
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(history)  # 历史对话
        messages.append({"role": "user", "content": message})

        # 4. 判断是否需要确认（新需求 = 无历史 或 用户明确发起新主题）
        is_new_request = self._is_new_screening_request(history, message)

        if is_new_request:
            # === 阶段 1：需求确认（不调用工具） ===
            result = await client.achat(
                messages=messages,
                tools=None,  # 确认阶段不调用工具
            )
            await self._save_message(user_id, message, result, [], [])
            return {
                "reply": result,
                "tools_used": [],
                "stocks": [],
                "phase": "confirmation",
            }
        else:
            # === 阶段 2：执行筛选（调用工具） ===
            tools_used = []
            result = await client.achat(
                messages=messages,
                tools=self._get_screening_tools(),
                auto_execute_tools=True,
                max_tool_rounds=8,
                tools_used=tools_used,
            )
            stocks = self._extract_stocks(result)
            await self._save_message(user_id, message, result, tools_used, stocks)
            return {
                "reply": result,
                "tools_used": tools_used,
                "stocks": stocks,
                "phase": "result",
            }

    def _is_new_screening_request(self, history: list, message: str) -> bool:
        """
        判断当前消息是否为新的选股需求（需要走确认流程）

        返回 True 的情况：
        1. 无对话历史（用户首次发起对话）
        2. 上一次对话已完成一轮筛选后，用户提出全新的选股主题

        返回 False 的情况（直接执行）：
        1. 用户回复的是确认指令（"按原需求筛选""添加改进条件"等）
        2. 用户在已有结果基础上追问调整（"PE 再低点""换个行业"）
        """
        # 无历史 → 新需求
        if not history:
            return True

        # 检查用户消息是否为确认指令
        confirm_keywords = ["按原需求", "就这样", "确认", "开始筛选", "可以了",
                           "添加改进", "加上", "按你的建议", "采纳建议"]
        for kw in confirm_keywords:
            if kw in message:
                return False

        # 检查上一条 assistant 消息是否为确认阶段的回复
        # （如果上一条是确认阶段，那用户的回复是对确认的响应，不是新需求）
        last_assistant = None
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant = msg
                break

        if last_assistant:
            # 如果上一条 assistant 消息包含股票推荐（有 stocks），
            # 说明已经完成过筛选，当前可能是追问调整
            if last_assistant.get("stocks"):
                # 追问调整 → 直接执行
                return False
            # 如果上一条是确认阶段的回复（无 stocks），用户是在响应确认
            return False

        return True

    async def _get_context_messages(self, user_id: str) -> list:
        """获取最近 N 条对话历史，用于传给 LLM 作为上下文"""
        doc = await self._db.screening_conversations.find_one(
            {"user_id": user_id}
        )
        if not doc or not doc.get("messages"):
            return []
        messages = doc["messages"]
        # 只取最近 MAX_CONTEXT_MESSAGES 条
        return messages[-self.MAX_CONTEXT_MESSAGES:]

    def _get_system_prompt(self) -> str:
        """构建选股专家的系统提示词"""
        curr_date = _get_latest_trade_date()
        return f"""你是一位专业的 A 股选股专家。用户会用自然语言描述选股需求。

## 工作模式

你有两种工作模式，根据对话上下文自动切换：

### 模式 1：需求确认（首次收到新的选股需求时）

当用户首次提出选股需求时，**不要直接调用工具和推荐股票**，而是：

1. **分析理解**：提炼用户需求的核心条件（行业、估值、风格、时间维度等）
2. **展示理解**：用清晰的列表形式告诉用户"我理解您的需求是..."
3. **改进建议**：基于你的专业判断，提出 2-3 条可选的改进建议（如增加筛选维度、调整阈值、补充考量因素等）
4. **等待确认**：明确询问用户是"按原需求筛选"还是"采纳建议后再筛选"

回复格式示例：
```
## 📋 需求分析

我理解您的选股需求如下：
- **行业范围**：xxx
- **核心条件**：xxx
- **筛选风格**：xxx

## 💡 改进建议

基于专业分析，我建议您可以考虑：
1. xxx（原因）
2. xxx（原因）
3. xxx（原因）

## ⏳ 请确认

请选择：
- **按原需求筛选** — 直接按您的条件执行
- **采纳建议后筛选** — 添加以上改进条件后再执行
```

### 模式 2：执行筛选（用户确认后 / 追问调整时）

当用户确认需求后，或在已有结果基础上追问调整时：

1. **调用工具**：使用可用的工具获取市场数据、财务数据、行情数据等
2. **精选推荐**：每次严格推荐 **5 只** 最符合条件的股票
3. **结构化输出**：按以下 JSON 格式输出推荐结果

## 输出格式要求（仅模式 2）

在回答的最后，必须包含一个 JSON 代码块，格式如下：

```json
{{
  "stocks": [
    {{
      "code": "600519",
      "name": "贵州茅台",
      "industry": "白酒",
      "price": 1680.00,
      "pe": 25.3,
      "pb": 8.5,
      "pct_change": 2.1,
      "reason": "白马股龙头，业绩稳定增长，估值处于历史中位"
    }}
  ]
}}
```

## 规则

- 当前日期：{curr_date}
- 模式 1 回复中**不要**包含 JSON 代码块和股票推荐
- 模式 2 每次推荐恰好 5 只股票，不多不少
- 推荐理由要具体，结合数据说话
- 如果用户要求调整（如"换个行业""PE 再低点"），直接在之前推荐的基础上调整（模式 2）
- 不给出具体的买入/卖出建议，只做选股推荐和分析
- 只推荐 A 股（沪深两市）
"""

    # 注意：工具加载已在 _ensure_client() 中完成（只加载 5 类选股工具）
    # 不再需要独立的 _get_screening_tools() 方法

    def _extract_stocks(self, reply: str) -> list:
        """从 LLM 回复中提取结构化股票列表"""
        import json, re
        # 尝试从 ```json ... ``` 代码块中提取
        pattern = r'```json\s*(\{[\s\S]*?\})\s*```'
        match = re.search(pattern, reply)
        if match:
            try:
                data = json.loads(match.group(1))
                return data.get("stocks", [])
            except json.JSONDecodeError:
                pass
        return []

    async def _save_message(self, user_id, user_msg, assistant_reply, tools_used, stocks):
        """持久化对话消息到 screening_conversations"""
        now = datetime.utcnow()
        user_entry = {"role": "user", "content": user_msg, "timestamp": now}
        assistant_entry = {
            "role": "assistant",
            "content": assistant_reply,
            "tools_used": tools_used,
            "stocks": stocks,
            "timestamp": now,
        }
        await self._db.screening_conversations.update_one(
            {"user_id": user_id},
            {
                "$push": {
                    "messages": {
                        "$each": [user_entry, assistant_entry],
                        "$slice": -self.SCREENING_CONVERSATION_LIMIT,
                    }
                },
                "$set": {"updated_at": now},
                "$setOnInsert": {"created_at": now},
            },
            upsert=True,
        )

    async def get_conversation(self, user_id: str) -> list:
        """获取完整对话历史（前端展示用）"""
        doc = await self._db.screening_conversations.find_one({"user_id": user_id})
        if not doc:
            return []
        return doc.get("messages", [])

    async def clear_conversation(self, user_id: str):
        """清空对话历史"""
        await self._db.screening_conversations.delete_one({"user_id": user_id})
```

### 3.2 系统提示词设计要点

| 要点 | 说明 |
|------|------|
| **角色定位** | 选股专家，不是通用助手 |
| **固定数量** | 每次恰好 5 只，LLM 倾向于多给或少给，需要在 prompt 中强调 |
| **结构化输出** | 要求 LLM 在回答末尾输出 JSON 代码块，便于前端解析 |
| **多轮记忆** | 提示词中说明"在之前推荐的基础上调整"，引导 LLM 利用上下文 |
| **数据驱动** | 强调"结合数据说话"，避免 LLM 编造数据 |
| **合规** | 不给买卖建议，只做选股分析 |

### 3.3 与智能助手的核心差异

> 详细的复用 vs 新建清单见 §3.0。这里仅列出运行时行为的关键区别。

| 维度 | 智能助手 | 智能筛选 |
|------|---------|---------|
| **对话历史** | `chat()` 不传历史给 LLM | 传最近 20 条历史 |
| **工具范围** | 加载全部 `fc_enabled` 工具 | 只加载 5 类选股工具 |
| **两阶段** | 无 | confirmation → result |
| **请求 Schema** | `ChatRequest` | **复用同一个** `ChatRequest` |

---

## 4. API 端点设计

### 4.1 路由

**文件**: `app/routers/intelligent_screening.py`
**前缀**: `/api/screening/intelligent`

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/chat` | 发送选股请求 |
| `GET` | `/conversation` | 获取对话历史 |
| `DELETE` | `/conversation` | 清空对话 |

### 4.2 请求/响应模型

**请求模型**：直接复用 `app/schemas/intelligent_assistant.py` 中的 `ChatRequest`（`message` + 可选 `conversation_id`），无需新建请求类。

**响应模型**：新建 `app/schemas/intelligent_screening.py`，仅包含响应类：

```python
from app.schemas.intelligent_assistant import ChatRequest  # 复用

class StockRecommendation(BaseModel):
    """单只推荐股票"""
    code: str = Field(..., description="股票代码")
    name: str = Field("", description="股票名称")
    industry: str = Field("", description="所属行业")
    price: Optional[float] = Field(None, description="当前价格")
    pe: Optional[float] = Field(None, description="市盈率")
    pb: Optional[float] = Field(None, description="市净率")
    pct_change: Optional[float] = Field(None, description="涨跌幅(%)")
    reason: str = Field("", description="推荐理由")

class ScreeningChatResponse(BaseModel):
    """智能筛选对话响应"""
    reply: str = Field(..., description="助手回复内容（Markdown）")
    tools_used: List[str] = Field(default_factory=list, description="使用的工具列表")
    stocks: List[StockRecommendation] = Field(default_factory=list, description="推荐的股票列表")
    phase: str = Field("result", description="当前阶段: confirmation=需求确认, result=筛选结果")

class ScreeningMessageItem(BaseModel):
    """筛选对话消息项"""
    role: str = Field(..., description="user 或 assistant")
    content: str = Field(..., description="消息内容")
    tools_used: Optional[List[str]] = Field(None, description="工具列表")
    stocks: Optional[List[StockRecommendation]] = Field(None, description="推荐股票")
    phase: Optional[str] = Field(None, description="阶段标记: confirmation / result")

class ScreeningConversationResponse(BaseModel):
    """筛选对话历史响应"""
    messages: List[ScreeningMessageItem] = Field(default_factory=list)
```

### 4.3 路由实现

```python
from app.schemas.intelligent_assistant import ChatRequest  # 复用请求模型
from app.schemas.intelligent_screening import ScreeningChatResponse, ScreeningConversationResponse

router = APIRouter(prefix="/api/screening/intelligent", tags=["intelligent-screening"])

@router.post("/chat", response_model=ScreeningChatResponse)
async def screening_chat(
    request: ChatRequest,  # 复用智能助手的 ChatRequest
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """智能筛选对话 — 自然语言选股"""
    user_id = str(current_user["id"])
    service = IntelligentScreeningService(db)
    result = await service.chat(user_id, request.message.strip())
    return ScreeningChatResponse(**result)

@router.get("/conversation", response_model=ScreeningConversationResponse)
async def get_screening_conversation(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """获取智能筛选对话历史"""
    user_id = str(current_user["id"])
    service = IntelligentScreeningService(db)
    messages = await service.get_conversation(user_id)
    return ScreeningConversationResponse(messages=messages)

@router.delete("/conversation")
async def clear_screening_conversation(
    current_user=Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_mongo_db),
):
    """清空智能筛选对话"""
    user_id = str(current_user["id"])
    service = IntelligentScreeningService(db)
    await service.clear_conversation(user_id)
    return {"success": True}
```

---

## 5. MongoDB Schema

### 5.1 集合: `screening_conversations`

```javascript
{
  "_id": ObjectId(),
  "user_id": "admin",                          // 用户 ID

  "messages": [
    {
      "role": "user",
      "content": "帮我找几只低估值的白酒股",
      "timestamp": ISODate("2026-03-03T10:00:00Z")
    },
    {
      "role": "assistant",
      "content": "根据您的需求，我为您筛选了以下 5 只低估值白酒股...",
      "tools_used": ["get_stock_market_data_unified", "get_income_analysis"],
      "stocks": [
        {
          "code": "600519",
          "name": "贵州茅台",
          "industry": "白酒",
          "price": 1680.00,
          "pe": 25.3,
          "pb": 8.5,
          "pct_change": 2.1,
          "reason": "行业龙头，业绩稳定，PE 处于近三年低位"
        }
        // ... 共 5 只
      ],
      "timestamp": ISODate("2026-03-03T10:00:05Z")
    },
    {
      "role": "user",
      "content": "PE 能再低一些吗？低于 20 的",
      "timestamp": ISODate("2026-03-03T10:01:00Z")
    },
    {
      "role": "assistant",
      "content": "好的，我重新筛选了 PE 低于 20 的白酒股...",
      "tools_used": ["get_income_analysis"],
      "stocks": [/* 调整后的 5 只 */],
      "timestamp": ISODate("2026-03-03T10:01:08Z")
    }
  ],

  "created_at": ISODate("2026-03-03T10:00:00Z"),
  "updated_at": ISODate("2026-03-03T10:01:08Z")
}
```

**索引设计：**
```javascript
db.screening_conversations.createIndex({"user_id": 1}, {unique: true})
```

**消息限制**: 使用 `$push` + `$slice: -50` 保留最近 50 条消息，防止无限增长。

---

## 6. 前端设计

### 6.1 页面结构

在现有 `Screening/index.vue` 顶部增加 Tab 切换：

```
┌──────────────────────────────────────────────────────────┐
│  📊 股票筛选                                              │
│                                                          │
│  ┌────────────┐  ┌────────────┐                          │
│  │ 传统筛选    │  │ 智能筛选 ✨ │                          │
│  └────────────┘  └────────────┘                          │
│                                                          │
│  ═══════════ 智能筛选 Tab 内容 ══════════                 │
│                                                          │
│  ┌─ 对话区域 ────────────────────────────────────┐       │
│  │                                               │       │
│  │  🤖 请描述您的选股需求，例如：                   │       │
│  │     "帮我找几只最近资金持续流入的低估值白马股"    │       │
│  │                                               │       │
│  │  👤 帮我找几只低估值的白酒股                     │       │
│  │                                               │       │
│  │  🤖 根据您的需求，筛选了以下 5 只低估值白酒股：  │       │
│  │     🔧 使用工具: get_stock_market_data, ...     │       │
│  │                                               │       │
│  │  ┌─ 推荐股票 ─────────────────────────────┐   │       │
│  │  │ ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐   │   │       │
│  │  │ │600519│ │000858│ │002304│ │603369│ ...│   │       │
│  │  │ │贵州茅│ │五粮液│ │洋河股│ │今世缘│   │   │       │
│  │  │ │PE:25 │ │PE:22 │ │PE:18 │ │PE:19 │   │   │       │
│  │  │ │+2.1% │ │+1.5% │ │-0.3% │ │+0.8% │   │   │       │
│  │  │ │[分析]│ │[分析]│ │[分析]│ │[分析]│   │   │       │
│  │  │ └──────┘ └──────┘ └──────┘ └──────┘   │   │       │
│  │  │         [批量分析] [加入自选]            │   │       │
│  │  └────────────────────────────────────────┘   │       │
│  │                                               │       │
│  │  👤 PE 能再低一些吗？低于 20 的                 │       │
│  │  🤖 ...                                       │       │
│  └───────────────────────────────────────────────┘       │
│                                                          │
│  ┌─ 输入区域 ────────────────────────────────────┐       │
│  │  描述您的选股需求...              [清空] [发送] │       │
│  └───────────────────────────────────────────────┘       │
└──────────────────────────────────────────────────────────┘
```

### 6.2 前端 API

**文件**: `frontend/src/api/screening.ts`（在现有文件中扩展）

```typescript
// === 智能筛选 API ===

export interface StockRecommendation {
  code: string
  name: string
  industry: string
  price?: number
  pe?: number
  pb?: number
  pct_change?: number
  reason: string
}

export interface ScreeningChatResponse {
  reply: string
  tools_used: string[]
  stocks: StockRecommendation[]
}

export interface ScreeningMessageItem {
  role: 'user' | 'assistant'
  content: string
  tools_used?: string[]
  stocks?: StockRecommendation[]
}

export interface ScreeningConversationResponse {
  messages: ScreeningMessageItem[]
}

// 在 screeningApi 对象中新增：
export const screeningApi = {
  // ... 现有方法 ...

  /** 智能筛选对话 */
  intelligentChat: (message: string) =>
    ApiClient.post<ScreeningChatResponse>(
      '/api/screening/intelligent/chat',
      { message }
    ),

  /** 获取智能筛选对话历史 */
  getIntelligentConversation: () =>
    ApiClient.get<ScreeningConversationResponse>(
      '/api/screening/intelligent/conversation'
    ),

  /** 清空智能筛选对话 */
  clearIntelligentConversation: () =>
    ApiClient.delete('/api/screening/intelligent/conversation'),
}
```

### 6.3 股票推荐卡片组件

每次 LLM 返回的 5 只股票，以卡片形式展示在对话消息中：

```vue
<!-- 股票推荐卡片（嵌入在 assistant 消息气泡中） -->
<div class="stock-cards">
  <div v-for="stock in msg.stocks" :key="stock.code" class="stock-card">
    <div class="stock-header">
      <span class="stock-code">{{ stock.code }}</span>
      <span class="stock-name">{{ stock.name }}</span>
      <el-tag size="small">{{ stock.industry }}</el-tag>
    </div>
    <div class="stock-metrics">
      <span>价格: {{ stock.price }}</span>
      <span>PE: {{ stock.pe }}</span>
      <span :class="stock.pct_change >= 0 ? 'up' : 'down'">
        {{ stock.pct_change > 0 ? '+' : '' }}{{ stock.pct_change }}%
      </span>
    </div>
    <div class="stock-reason">{{ stock.reason }}</div>
    <div class="stock-actions">
      <el-button size="small" @click="goAnalysis(stock.code)">分析</el-button>
      <el-button size="small" @click="addFavorite(stock.code)">加自选</el-button>
    </div>
  </div>
</div>
```

### 6.4 前端改动清单

| 文件 | 改动 |
|------|------|
| `frontend/src/views/Screening/index.vue` | 增加 `el-tabs` 切换传统/智能；智能筛选 Tab 内嵌对话 UI + 股票卡片 |
| `frontend/src/api/screening.ts` | 新增 `intelligentChat`、`getIntelligentConversation`、`clearIntelligentConversation` |

**不需要新建独立页面**，直接在现有筛选页面中通过 Tab 切换。

---

## 7. 工具选择策略

智能筛选可调用的工具与智能助手共用同一个 `ToolRegistry`，但会按类别筛选：

| 工具类别 | 用途 | 示例 |
|---------|------|------|
| `market` | 获取行情数据 | `get_stock_market_data_unified` |
| `fundamentals` | 获取财务指标 | `get_income_analysis`、`get_financial_summary` |
| `news` | 获取相关新闻 | `get_stock_news_unified` |
| `china` | A 股特色数据 | `get_stock_list_by_industry` |
| `technical` | 技术指标 | `get_technical_indicators` |

> 工具列表不是硬编码的，而是从 `ToolRegistry` 动态读取 `fc_enabled=True` 且类别匹配的工具。

---

## 8. 对话流程示例

### 示例 1：基础选股（完整两阶段流程）

```
👤 帮我找几只低估值的消费电子股

🤖 [phase: confirmation — 不调用工具，先分析需求]

   ## 📋 需求分析

   我理解您的选股需求如下：
   - **行业范围**：消费电子板块
   - **核心条件**：低估值（低 PE、低 PB）
   - **筛选风格**：价值导向

   ## 💡 改进建议

   基于专业分析，我建议您可以考虑：
   1. **增加盈利质量筛选**：加入 ROE > 10% 的条件，排除估值虽低但盈利能力差的公司
   2. **关注资金面**：近期主力资金净流入的个股往往更有上涨动力
   3. **排除 ST 和次新股**：降低风险，聚焦经营稳定的标的

   ## ⏳ 请确认

   请选择：
   - **按原需求筛选** — 直接按"消费电子 + 低估值"条件执行
   - **采纳建议后筛选** — 添加 ROE、资金面等改进条件后再执行

                                     [按原需求筛选] [采纳建议后筛选]  ← 前端按钮

👤 按原需求筛选

🤖 [phase: result — 调用工具，返回结果]
   [调用 get_stock_list_by_industry("消费电子")]
   [调用 get_income_analysis("多只候选股")]
   [调用 get_stock_market_data_unified("候选股行情")]

   根据您的需求，我为您筛选了以下 5 只低估值消费电子股：
   [股票卡片 x5]

   筛选逻辑：
   1. 从消费电子板块中选取市值前 30 的股票
   2. 按 PE（TTM）从低到高排序
   3. 排除 PE 为负（亏损）的公司
   4. 综合考虑 PB 等指标

👤 有没有做手机的？

🤖 [phase: result — 追问调整，直接执行，不再走确认流程]
   好的，我在消费电子中进一步筛选了手机产业链相关的个股：
   [调整后的股票卡片 x5]
```

### 示例 2：采纳改进建议

```
👤 帮我找几只最近资金持续流入的低估值白马股

🤖 [phase: confirmation]

   ## 📋 需求分析

   我理解您的选股需求如下：
   - **选股范围**：白马股（大市值、业绩稳定的龙头企业）
   - **估值条件**：低估值（PE、PB 处于合理或偏低水平）
   - **资金面**：近期主力资金持续净流入

   ## 💡 改进建议

   基于专业分析，我建议您可以考虑：
   1. **明确资金流入周期**：建议关注近 5 个交易日连续净流入的个股，而非单日
   2. **加入业绩增长筛选**：白马股中优先选择近一年净利润同比增长 > 15% 的
   3. **设置市值门槛**：总市值 > 500 亿，确保是真正的白马股

   ## ⏳ 请确认

   请选择：
   - **按原需求筛选** — 直接按您的条件执行
   - **采纳建议后筛选** — 添加以上改进条件后再执行

👤 采纳建议后筛选

🤖 [phase: result — 使用原需求 + 改进条件执行]
   [调用工具获取数据]
   好的，综合您的需求和改进条件，为您筛选了 5 只白马股：
   [股票卡片 x5]
```

### 示例 3：模糊需求（确认阶段主动追问）

```
👤 最近什么股票比较好

🤖 [phase: confirmation — 需求太模糊，确认阶段主动追问]

   ## 📋 需求分析

   您的选股需求比较宽泛，我需要进一步了解您的偏好：

   - **行业范围**：未指定（全市场？）
   - **筛选风格**：未指定

   ## 💡 建议您补充以下信息

   1. **行业偏好**：有倾向的行业吗？如科技、消费、医药、新能源等
   2. **投资风格**：偏好成长股还是价值股？大盘还是小盘？
   3. **持有周期**：关注短期热点还是中长期配置？

   请告诉我您的想法，我来帮您精准筛选。

👤 科技类的，中长期的

🤖 [phase: confirmation — 补充信息后，再次确认]

   ## 📋 需求分析

   我理解您的选股需求如下：
   - **行业范围**：科技板块（半导体、软件、AI、通信等）
   - **持有周期**：中长期配置
   - **隐含条件**：业绩稳健、有成长空间

   ## 💡 改进建议

   1. **聚焦细分赛道**：科技板块范围较广，建议聚焦 AI、半导体、信创等热门赛道
   2. **加入研发投入筛选**：研发费用占比 > 10% 的科技公司通常更具长期竞争力
   3. **关注机构持仓**：基金重仓的科技股通常基本面更扎实

   ## ⏳ 请确认

   请选择：
   - **按原需求筛选** — 科技板块 + 中长期
   - **采纳建议后筛选** — 添加细分赛道、研发投入等条件

👤 就按你的建议来吧

🤖 [phase: result]
   [调用工具获取数据]
   好的，为您筛选了 5 只适合中长期配置的科技股：
   [股票卡片 x5]
```

---

## 9. 路由注册

在 `app/main.py` 中注册新路由：

```python
from app.routers.intelligent_screening import router as intelligent_screening_router
app.include_router(intelligent_screening_router)
```

---

## 10. 实现计划

### Phase 1：核心闭环（2-3 天）

> 由于复用智能助手基础设施（见 §3.0），工作量显著减少。

1. **后端**
   - `app/schemas/intelligent_screening.py` — 仅响应模型（`ChatRequest` 复用自智能助手）
   - `app/services/intelligent_screening_service.py` — 核心服务（`_ensure_client()` 复用 LLM 配置解析，主要新增两阶段 `chat()` 和 `_is_new_screening_request()`）
   - `app/routers/intelligent_screening.py` — API 路由（结构与智能助手路由一致）
   - `app/main.py` — 注册路由

2. **前端**
   - `frontend/src/api/screening.ts` — 新增智能筛选 API
   - `frontend/src/views/Screening/index.vue` — Tab 切换 + 对话 UI + 股票卡片 + 确认按钮

3. **数据库**
   - `screening_conversations` 集合（自动创建）

### Phase 2：体验优化（2-3 天）

1. 股票卡片交互：点击跳转详情、一键分析、批量加自选
2. 对话历史持久化：下次进入恢复上次对话
3. 思考中动画 + 工具调用过程展示
4. 移动端响应式适配

### Phase 3：增强功能（后续）

1. 热门选股模板（快捷按钮：低估值白马、科技成长、高股息等）
2. 选股结果导出（Excel）
3. 选股结果直接发起批量分析工作流

---

## 11. 相关文档

- [智能助手](./intelligent-assistant.md) — 参考实现模式
- [Skill 生成系统](./skill-generation-system.md) — 会话管理参考
- [MCP 支持](./mcp-support.md) — 外部数据源工具

