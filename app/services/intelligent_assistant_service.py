"""
智能助手服务 - Agent 自主编排模式

支持 ReAct 模式的工具自主调用，用于事件驱动分析、探索性查询等场景。
"""

import logging
from typing import Any, Dict, List, Optional

from core.tools import get_tool_registry, tool_metadata_list_to_openai
from core.llm import UnifiedLLMClient
from core.llm.models import LLMConfig, LLMProvider, Message, MessageRole

logger = logging.getLogger(__name__)

# 系统提示词：角色 + 合规 + 工具使用说明
SYSTEM_PROMPT = """你是 TradingAgents-CN 的股票分析智能助手。你可以通过调用各种工具获取市场数据、财务数据、新闻、技术指标等，然后基于数据回答用户问题。

【重要合规要求】
- 不提供买卖建议、目标价、仓位建议
- 仅基于工具返回的客观数据进行解读和分析
- 明确告知用户：分析结论用于学习验证，不构成投资建议

【工具使用原则】
- 优先使用工具获取真实数据，再基于数据回答
- 根据用户问题选择最相关的工具（如问估值用财务工具、问走势用技术指标）
- 若一次调用数据不足，可继续调用其他工具补充
"""


async def _get_assistant_llm_config(db) -> Optional[LLMConfig]:
    """
    从数据库获取智能助手使用的 LLM 配置
    优先使用 quick 模型（快速响应），若未配置则使用第一个启用的模型
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
    quick_model = default_models.get("quick_analysis_model")

    target_model = quick_model or default_llm
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
            Message(role=MessageRole.SYSTEM, content=SYSTEM_PROMPT),
            Message(role=MessageRole.USER, content=user_message.strip()),
        ]

        tools_used: List[str] = []

        try:
            response = await self._llm_client.achat(
                messages,
                tools=self._openai_tools,
                auto_execute_tools=True,
                max_tool_rounds=8,
            )

            for tc in (response.tool_calls or []):
                tools_used.append(tc.name)

            reply = response.content or "抱歉，暂时无法生成回答，请稍后再试。"
            return {
                "reply": reply,
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


async def chat_with_assistant(
    db,
    user_message: str,
    conversation_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    便捷函数：使用智能助手进行对话
    """
    service = IntelligentAssistantService(db)
    return await service.chat(user_message, conversation_id)
