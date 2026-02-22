"""
智能助手服务 - Agent 自主编排模式

支持 ReAct 模式的工具自主调用，用于事件驱动分析、探索性查询等场景。
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

# 智能助手整体超时（LLM + 多轮工具调用），默认 120 秒
ASSISTANT_TIMEOUT_SECONDS = int(os.environ.get("ASSISTANT_TIMEOUT_SECONDS", "120"))

# 会话历史最大条数（每用户）
ASSISTANT_CONVERSATION_LIMIT = 100

from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.llm import UnifiedLLMClient
from core.llm.models import LLMConfig, LLMProvider, Message, MessageRole

logger = logging.getLogger(__name__)


def _get_latest_trade_date() -> str:
    """获取 A 股最近交易日（周末回退到上周五）"""
    now = datetime.now()
    # 周六(5)、周日(6) 用上周五
    if now.weekday() == 5:
        now = now - timedelta(days=1)
    elif now.weekday() == 6:
        now = now - timedelta(days=2)
    return now.strftime("%Y-%m-%d")


def _get_system_prompt(knowledge_snippets: str = "") -> str:
    """生成包含当前日期的系统提示词

    Args:
        knowledge_snippets: RAG 检索到的动态知识片段（由 FinancialKnowledgeManager 提供）
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    trade_date = _get_latest_trade_date()
    return f"""你是一位经验丰富的 A 股投资教练，隶属于 TradingAgents-CN 分析平台。你的使命是帮助用户掌握投资分析的方法和框架，培养独立的投资思考能力。

【教练风格】
- **教方法，不给答案**：带用户走一遍完整的分析流程，而不是直接下结论。例如用户问"这只股票怎么样"，你获取数据后，教他如何从基本面、技术面、消息面三个维度来解读
- **讲框架，不押方向**：分享专业投资者常用的分析框架和思维模型，引导用户建立自己的判断体系。例如用户问"什么时候进场好"，你讲解布局时间窗口、估值安全边际等分析框架
- **用数据说话**：所有分析必须基于工具获取的实时数据，先拿数据再展开教学，绝不凭空推测
- **解释为什么**：不仅展示数据，更要教用户理解数据背后的含义。例如"毛利率 60% 在白酒行业属于优秀水平，说明定价权强"
- **诚实表达不确定性**：市场充满不确定性，遇到无法判断的情况直接说明，教用户识别和接受不确定性

【核心职责】
1. **数据解读教学**：获取数据后，教用户如何阅读和理解关键指标，指出哪些数据值得重点关注
2. **分析框架传授**：根据问题类型，介绍对应的分析方法论（如个股分析三步法、财务健康检查清单等）
3. **投资思维培养**：引导用户关注关键指标、识别风险信号、理解市场逻辑，而非追逐热点
4. **知识点讲解**：遇到专业概念时主动用通俗语言解释（如除权除息、TTM、自由现金流等）

【当前日期】{today}（用于判断年份、财报披露周期等时间逻辑）
【当前/最近交易日】{trade_date}（用于调用工具获取行情数据）
- 调用所有需要 curr_date 或 trade_date 参数的工具时，**必须传入交易日**
- 回答涉及年份、季度等问题时，**必须基于当前日期推理**（如当前为 2026 年则 2025 年已结束）
- 严禁使用训练数据中的历史日期回答

【A股财报披露时间规则】
- 年报：1月1日～4月30日 | 一季报：4月30日前 | 半年报：8月31日前 | 三季报：10月31日前
- 询问特定公司财报何时披露时，应主动查询该公司往年披露时间进行类推

【思考逻辑】
- **类推推理**：不知道的信息，主动查询历史数据进行类推（如查去年财报披露日推断今年）
- **分步思考**：先获取数据，再分析解读，最后给出教学性总结
- **主动获取数据**：不要仅凭规则泛泛回答，尽量调用工具获取具体信息使回答更有价值
- **诚实表达不确定性**：若数据不足，明确说明推断依据（如"根据往年披露时间推断"）

{knowledge_snippets}

【教练底线 — 合规原则】
- 你是教练，不是投顾：**教分析方法，不给"买入/卖出/持有"的直接建议**
- 你讲数据，不喊口号：所有观点必须有工具返回的数据支撑，不做主观臆断
- 你培养独立思考：分析完数据后，引导用户自行判断（如"基于这些数据，你可以从这几个角度思考..."），而非替用户下结论
- 不提供目标价、仓位建议、具体买卖时点
- 每次回答结尾自然提醒：以上分析仅供学习参考，不构成投资建议

【工具使用原则】
- **严禁**根据训练数据回答行情、大盘、市场、指数、板块、个股等需要实时数据的问题，**必须**通过调用工具获取
- 根据每个工具的 when_to_use 描述，**自主选择**最合适的工具；若一次调用不足，可继续调用其他工具
- 所有需要 curr_date 或 trade_date 的工具，**必须**传入上述日期
- **板块/行业/概念类问题**优先使用板块级别工具（analyze_sector_by_name、get_sector_constituents、search_sector），无需股票代码
- 只有涉及具体个股时才使用需要 ticker 参数的工具
"""


def _resolve_models(config_doc) -> tuple:
    """从配置文档解析模型名：优先 default_models，否则 system_settings"""
    default_models = config_doc.get("default_models") or {}
    system_settings = config_doc.get("system_settings") or {}
    return (
        default_models.get("quick_analysis_model") or system_settings.get("quick_analysis_model"),
        default_models.get("deep_analysis_model") or system_settings.get("deep_analysis_model"),
        default_models.get("deep_reasoning_model") or system_settings.get("deep_reasoning_model"),
        default_models.get("coding_model") or system_settings.get("coding_model"),
    )


async def _get_llm_config_for_model(db, target_model: str, purpose: str = "") -> Optional[LLMConfig]:
    """根据模型名获取 LLM 配置（内部复用逻辑）"""
    if not target_model:
        return None
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    if not config_doc or "llm_configs" not in config_doc:
        return None
    llm_configs = config_doc.get("llm_configs", [])
    model_configs = [c for c in llm_configs if c.get("model_name") == target_model and c.get("enabled", True)]
    if not model_configs:
        return None
    model_config = model_configs[0]
    from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
    provider_info = get_provider_and_url_by_model_sync(target_model)
    if not provider_info:
        return None
    provider_str = (provider_info.get("provider") or model_config.get("provider", "")).lower()
    provider_map = {
        "openai": LLMProvider.OPENAI, "deepseek": LLMProvider.DEEPSEEK,
        "dashscope": LLMProvider.DASHSCOPE, "qwen": LLMProvider.DASHSCOPE,
        "zhipu": LLMProvider.ZHIPU, "google": LLMProvider.GOOGLE,
        "anthropic": LLMProvider.ANTHROPIC, "siliconflow": LLMProvider.SILICONFLOW,
        "ollama": LLMProvider.OLLAMA, "openrouter": LLMProvider.OPENROUTER,
    }
    provider = provider_map.get(provider_str, LLMProvider.DEEPSEEK)
    return LLMConfig(
        provider=provider, model=target_model,
        api_key=provider_info.get("api_key"), base_url=provider_info.get("backend_url"),
        temperature=float(model_config.get("temperature", 0.2)),
        max_tokens=int(model_config.get("max_tokens", 4000)),
        timeout=int(model_config.get("timeout", 60)),
    )


async def _get_assistant_llm_config(db, use_reasoning_model: bool = False) -> Optional[LLMConfig]:
    """
    从数据库获取智能助手使用的 LLM 配置
    优先使用深度思考模型（deep_analysis_model），以保证时间逻辑、财报披露等推理准确
    use_reasoning_model=True 时，优先使用深度推理模型（deep_reasoning_model），适用于策略生成、规划等
    若未配置则回退到快速模型或默认模型
    """
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    if not config_doc or "llm_configs" not in config_doc:
        logger.warning("[智能助手] 数据库中没有 LLM 配置")
        return None

    llm_configs = config_doc.get("llm_configs", [])
    default_llm = config_doc.get("default_llm")
    quick_model, deep_model, reasoning_model, _ = _resolve_models(config_doc)

    if use_reasoning_model and reasoning_model:
        target_model = reasoning_model
        logger.info(f"[智能助手] 使用深度推理模型: {target_model}")
    else:
        target_model = deep_model or quick_model or default_llm
        if deep_model:
            logger.info(f"[智能助手] 使用深度分析模型: {deep_model}")
        elif quick_model:
            logger.info(f"[智能助手] 深度模型未配置，使用快速模型: {quick_model}")

    if not target_model:
        target_model = deep_model or quick_model or default_llm
    if not target_model and llm_configs:
        for cfg in llm_configs:
            if cfg.get("enabled", True):
                target_model = cfg.get("model_name")
                break

    if not target_model:
        logger.warning("[智能助手] 未找到可用的模型配置")
        return None

    return await _get_llm_config_for_model(db, target_model)


async def get_reasoning_llm_config(db=None):
    """
    获取深度推理模型配置，用于策略 DSL 生成、规划等需要强推理的场景
    优先 deep_reasoning_model，未配置时回退到 deep_analysis_model
    """
    from app.core.database import get_mongo_db
    db = db if db is not None else get_mongo_db()
    return await _get_assistant_llm_config(db, use_reasoning_model=True)


async def get_coding_llm_config(db=None):
    """
    获取编程模型配置，用于策略 DSL 生成等需要结构化 JSON 输出的场景
    优先 coding_model，未配置时回退到 deep_reasoning_model → deep_analysis_model
    """
    from app.core.database import get_mongo_db
    db = db if db is not None else get_mongo_db()
    config_doc = await db.system_configs.find_one(
        {"is_active": True},
        sort=[("version", -1)]
    )
    if not config_doc or "llm_configs" not in config_doc:
        return await get_reasoning_llm_config(db)
    _, deep_model, reasoning_model, coding_model = _resolve_models(config_doc)
    target_model = coding_model or reasoning_model or deep_model
    if target_model:
        logger.info(f"[编程模型] 使用: {target_model} (coding={bool(coding_model)}, reasoning={bool(reasoning_model)})")
    return await _get_llm_config_for_model(db, target_model) if target_model else await get_reasoning_llm_config(db)


class IntelligentAssistantService:
    """智能助手服务"""

    def __init__(self, db):
        self._db = db
        self._llm_client: Optional[UnifiedLLMClient] = None
        self._openai_tools: Optional[List[Dict[str, Any]]] = None
        self._tool_functions: Optional[Dict[str, Any]] = None

    async def _ensure_client(self) -> bool:
        """确保 LLM 客户端和工具已加载"""
        if self._llm_client is not None:
            return True

        llm_config = await _get_assistant_llm_config(self._db)
        if not llm_config:
            return False

        try:
            self._llm_client = UnifiedLLMClient.from_config(llm_config)
        except Exception as e:
            logger.error(f"[智能助手] 创建 LLM 客户端失败: {e}", exc_info=True)
            return False

        registry = get_tool_registry()
        all_metadata = registry.list_all()
        self._openai_tools = tool_metadata_list_to_openai(all_metadata)

        self._tool_functions = {}
        for tool in all_metadata:
            if tool.fc_enabled and tool.parameters:
                func = registry.get_function(tool.id)
                if func:
                    self._tool_functions[tool.id] = func

        self._llm_client.inject_tools(self._tool_functions)
        logger.info(f"[智能助手] 已加载 {len(self._openai_tools)} 个工具")
        return True

    async def chat(self, user_message: str, conversation_id: Optional[str] = None) -> Dict[str, Any]:
        """
        处理用户对话

        Args:
            user_message: 用户输入
            conversation_id: 会话 ID（首版未使用，预留）

        Returns:
            {"reply": str, "tools_used": List[str], "data_refs": Optional[List]}
        """
        # 前置检查：不支持的品种类型
        from app.services.planned_analysis_service import _check_unsupported_asset
        unsupported_msg = _check_unsupported_asset(user_message)
        if unsupported_msg:
            return {
                "reply": unsupported_msg,
                "tools_used": [],
                "data_refs": None,
            }

        if not await self._ensure_client():
            return {
                "reply": "智能助手暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。",
                "tools_used": [],
                "data_refs": None,
            }

        # RAG 动态知识检索（优雅降级：不可用时返回空字符串）
        knowledge_snippets = ""
        try:
            from core.knowledge import FinancialKnowledgeManager
            km = FinancialKnowledgeManager(db=self._db)
            knowledge_snippets = km.retrieve_for_prompt(user_message)
            if knowledge_snippets:
                logger.info(f"[智能助手] ✅ RAG 知识检索成功 ({len(knowledge_snippets)} 字符)")
            else:
                logger.info("[智能助手] RAG 知识检索返回空（无匹配知识）")
        except Exception as e:
            logger.warning(f"[智能助手] ⚠️ 知识检索失败（降级为静态知识）: {e}")

        messages = [
            Message(role=MessageRole.SYSTEM, content=_get_system_prompt(knowledge_snippets)),
            Message(role=MessageRole.USER, content=user_message.strip()),
        ]

        tools_used: List[str] = []

        async def _do_chat():
            nonlocal tools_used
            resp = await self._llm_client.achat(
                messages,
                tools=self._openai_tools,
                auto_execute_tools=True,
                max_tool_rounds=8,
                tools_used=tools_used,
            )
            return resp.content

        try:
            content = await asyncio.wait_for(
                _do_chat(),
                timeout=ASSISTANT_TIMEOUT_SECONDS,
            )
            reply = content or "抱歉，暂时无法生成回答，请稍后再试。"
            return {
                "reply": reply,
                "tools_used": tools_used,
                "data_refs": None,
            }
        except asyncio.TimeoutError:
            logger.warning(f"[智能助手] 请求超时（{ASSISTANT_TIMEOUT_SECONDS}s）")
            return {
                "reply": f"抱歉，处理您的问题用时过长（已超过 {ASSISTANT_TIMEOUT_SECONDS} 秒），为避免长时间等待已中断。\n\n"
                "建议您：\n"
                "• 尝试将问题拆分得更具体一些\n"
                "• 检查网络连接是否稳定\n"
                "• 稍后重试",
                "tools_used": tools_used,
                "data_refs": None,
            }
        except Exception as e:
            logger.exception("[智能助手] 对话失败")
            return {
                "reply": f"处理您的请求时发生错误：{str(e)}。请检查网络和 LLM 配置后重试。",
                "tools_used": tools_used,
                "data_refs": None,
            }


async def save_assistant_message(
    db,
    user_id: str,
    user_content: str,
    assistant_content: str,
    tools_used: List[str],
) -> None:
    """将会话追加写入 MongoDB"""
    now = datetime.now(timezone.utc)
    user_msg = {"role": "user", "content": user_content}
    assistant_msg = {"role": "assistant", "content": assistant_content}
    if tools_used:
        assistant_msg["tools_used"] = tools_used
    await db.assistant_conversations.update_one(
        {"user_id": user_id},
        {
            "$push": {
                "messages": {
                    "$each": [user_msg, assistant_msg],
                    "$slice": -ASSISTANT_CONVERSATION_LIMIT,
                }
            },
            "$set": {"updated_at": now},
        },
        upsert=True,
    )


async def get_assistant_conversation(db, user_id: str) -> List[Dict[str, Any]]:
    """获取用户的智能助手会话历史"""
    doc = await db.assistant_conversations.find_one({"user_id": user_id})
    if not doc or not doc.get("messages"):
        return []
    return doc["messages"]


async def clear_assistant_conversation(db, user_id: str) -> None:
    """清空用户的智能助手会话"""
    await db.assistant_conversations.update_one(
        {"user_id": user_id},
        {"$set": {"messages": [], "updated_at": datetime.now(timezone.utc)}},
    )


async def chat_with_assistant(
    db,
    user_message: str,
    user_id: Optional[str] = None,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    便捷函数：使用智能助手进行对话
    user_id: 用于持久化会话；若提供则对话会后保存
    """
    service = IntelligentAssistantService(db)
    result = await service.chat(user_message, conversation_id)
    if user_id and result.get("reply"):
        try:
            await save_assistant_message(
                db,
                user_id=user_id,
                user_content=user_message.strip(),
                assistant_content=result["reply"],
                tools_used=result.get("tools_used") or [],
            )
        except Exception as e:
            logger.warning("[智能助手] 保存会话失败: %s", e)
    return result
