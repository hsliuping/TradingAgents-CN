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


def _get_system_prompt() -> str:
    """生成包含当前日期的系统提示词"""
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    trade_date = _get_latest_trade_date()
    return f"""你是 TradingAgents-CN 的股票分析智能助手。你可以通过调用各种工具获取市场数据、财务数据、新闻、技术指标等，然后基于数据回答用户问题。

【当前日期】{today}（公历，用于判断年份、财报披露周期等时间逻辑）
【当前/最近交易日】{trade_date}（A股交易日，用于调用工具获取行情数据）
- 调用所有需要 curr_date 或 trade_date 参数的工具时，**必须传入交易日**以获取最新数据
- 回答涉及年份、季度、财报披露时间等问题时，**必须基于【当前日期】进行正确推理**（例如：当前为 2026 年则 2025 年已结束）
- 严禁使用训练数据中的历史日期回答，必须通过工具实时获取

【基础财务知识 - 中国A股财报披露规则】
- **年报**：应在会计年度结束后 4 个月内披露，即每年 1 月 1 日～4 月 30 日
- **一季报**：4 月 30 日前
- **半年报**：8 月 31 日前
- **三季报**：10 月 31 日前
- 披露时间可能因公司而异，大型或复杂公司可能接近截止日披露

【思考逻辑 - 像人一样推理】
- **类推推理**：当用户问「XX 公司 2025 年年报何时出」而当前尚未披露时，应**主动查询该公司 2024 年年报的实际披露时间**（通过基本面、新闻等工具），据此推断 2025 年年报的大致披露窗口
- **分步思考**：先获取可得的客观数据（去年披露日、公司往年习惯、行业惯例），再给出「预计 X 月中旬～X 月底披露」等合理区间，而非仅回答「按规定 4 月 30 日前」
- **主动获取数据**：不要仅凭规则泛泛回答；尽量调用工具获取该公司、该股票的具体信息，使回答更准确、更有参考价值
- **诚实表达不确定性**：若数据不足，明确说明「根据往年披露时间推断」「具体以公司公告为准」

【重要合规要求】
- 不提供买卖建议、目标价、仓位建议
- 仅基于工具返回的客观数据进行解读和分析
- 明确告知用户：分析结论用于学习验证，不构成投资建议

【工具使用原则 - 必须遵守】
- **严禁**根据训练数据回答行情、大盘、市场、指数、板块、个股等任何需要实时/最新数据的问题，**必须**通过调用工具获取
- 根据每个工具的 when_to_use 描述，**自主选择**最合适的工具；若一次调用不足，可继续调用其他工具
- 所有需要 curr_date 或 trade_date 的工具，**必须**传入上述日期以获取最新数据
"""


async def _get_assistant_llm_config(db) -> Optional[LLMConfig]:
    """
    从数据库获取智能助手使用的 LLM 配置
    优先使用深度思考模型（deep_analysis_model），以保证时间逻辑、财报披露等推理准确
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
    default_models = config_doc.get("default_models") or {}
    deep_model = default_models.get("deep_analysis_model")
    quick_model = default_models.get("quick_analysis_model")

    target_model = deep_model or quick_model or default_llm
    if deep_model:
        logger.info(f"[智能助手] 使用深度思考模型: {deep_model}")
    elif quick_model:
        logger.info(f"[智能助手] 深度模型未配置，使用快速模型: {quick_model}")
    if not target_model and llm_configs:
        for cfg in llm_configs:
            if cfg.get("enabled", True):
                target_model = cfg.get("model_name")
                break

    if not target_model:
        logger.warning("[智能助手] 未找到可用的模型配置")
        return None

    model_configs = [
        c for c in llm_configs
        if c.get("model_name") == target_model and c.get("enabled", True)
    ]
    if not model_configs:
        return None

    model_config = model_configs[0]
    from app.services.simple_analysis_service import get_provider_and_url_by_model_sync
    provider_info = get_provider_and_url_by_model_sync(target_model)

    if not provider_info:
        logger.warning(f"[智能助手] 无法获取模型 {target_model} 的提供商信息")
        return None

    provider_str = (provider_info.get("provider") or model_config.get("provider", "")).lower()
    provider_map = {
        "openai": LLMProvider.OPENAI,
        "deepseek": LLMProvider.DEEPSEEK,
        "dashscope": LLMProvider.DASHSCOPE,
        "qwen": LLMProvider.DASHSCOPE,
        "zhipu": LLMProvider.ZHIPU,
        "google": LLMProvider.GOOGLE,
        "anthropic": LLMProvider.ANTHROPIC,
        "siliconflow": LLMProvider.SILICONFLOW,
        "ollama": LLMProvider.OLLAMA,
        "openrouter": LLMProvider.OPENROUTER,
    }
    provider = provider_map.get(provider_str)
    if not provider:
        provider = LLMProvider.DEEPSEEK
        logger.info(f"[智能助手] 未知提供商 {provider_str}，回退到 DeepSeek")

    return LLMConfig(
        provider=provider,
        model=target_model,
        api_key=provider_info.get("api_key"),
        base_url=provider_info.get("backend_url"),
        temperature=float(model_config.get("temperature", 0.2)),
        max_tokens=int(model_config.get("max_tokens", 4000)),
        timeout=int(model_config.get("timeout", 60)),
    )


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
        if not await self._ensure_client():
            return {
                "reply": "智能助手暂时不可用，请检查 LLM 配置是否已在「设置」中正确配置。",
                "tools_used": [],
                "data_refs": None,
            }

        messages = [
            Message(role=MessageRole.SYSTEM, content=_get_system_prompt()),
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
