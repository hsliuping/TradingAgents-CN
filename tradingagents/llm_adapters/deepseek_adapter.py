"""
DeepSeek LLM适配器，支持Token使用统计
"""

import os
import time
from typing import Any, Dict, List, Optional, Union
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import _convert_message_to_dict
from langchain_core.callbacks import CallbackManagerForLLMRun

# 导入统一日志系统
from tradingagents.utils.logging_init import setup_llm_logging

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger, get_logger_manager
logger = get_logger('agents')
logger = setup_llm_logging()

# 导入token跟踪器
try:
    from tradingagents.config.config_manager import token_tracker
    TOKEN_TRACKING_ENABLED = True
    logger.info("✅ Token跟踪功能已启用")
except ImportError:
    TOKEN_TRACKING_ENABLED = False
    logger.warning("⚠️ Token跟踪功能未启用")


class ChatDeepSeek(ChatOpenAI):
    """
    DeepSeek聊天模型适配器，支持Token使用统计
    
    继承自ChatOpenAI，添加了Token使用量统计功能
    """

    @staticmethod
    def _supports_thinking_mode(model: str) -> bool:
        normalized = str(model or "").strip().lower()
        return (
            normalized.startswith("deepseek-v4")
            or "reasoner" in normalized
            or normalized.startswith("deepseek-r1")
        )

    @staticmethod
    def _build_thinking_kwargs(model: str, kwargs: Dict[str, Any]) -> Dict[str, Any]:
        updated_kwargs = dict(kwargs)
        thinking = updated_kwargs.pop("thinking", None)
        extra_body = dict(updated_kwargs.get("extra_body") or {})

        if thinking is not None:
            extra_body["thinking"] = thinking

        if ChatDeepSeek._supports_thinking_mode(model):
            extra_body.setdefault("thinking", {"type": "enabled"})
            updated_kwargs.setdefault("reasoning_effort", "high")

        if extra_body:
            updated_kwargs["extra_body"] = extra_body

        return updated_kwargs
    
    def __init__(
        self,
        model: str = "deepseek-chat",
        api_key: Optional[str] = None,
        base_url: str = "https://api.deepseek.com",
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        初始化DeepSeek适配器
        
        Args:
            model: 模型名称，默认为deepseek-chat
            api_key: API密钥，如果不提供则从环境变量DEEPSEEK_API_KEY获取
            base_url: API基础URL
            temperature: 温度参数
            max_tokens: 最大token数
            **kwargs: 其他参数
        """
        
        # 获取API密钥
        if api_key is None:
            # 导入 API Key 验证工具
            try:
                from app.utils.api_key_utils import is_valid_api_key
            except ImportError:
                def is_valid_api_key(key):
                    if not key or len(key) <= 10:
                        return False
                    if key.startswith('your_') or key.startswith('your-'):
                        return False
                    if key.endswith('_here') or key.endswith('-here'):
                        return False
                    if '...' in key:
                        return False
                    return True

            # 从环境变量读取 API Key
            env_api_key = os.getenv("DEEPSEEK_API_KEY")

            # 验证环境变量中的 API Key 是否有效（排除占位符）
            if env_api_key and is_valid_api_key(env_api_key):
                api_key = env_api_key
                logger.info("✅ [DeepSeek初始化] 使用环境变量中的有效 API Key")
            elif env_api_key:
                logger.warning("⚠️ [DeepSeek初始化] 环境变量中的 API Key 无效（可能是占位符），将被忽略")
                api_key = None
            else:
                api_key = None

            if not api_key:
                raise ValueError(
                    "DeepSeek API密钥未找到。请在 Web 界面配置 API Key "
                    "(设置 -> 大模型厂家) 或设置 DEEPSEEK_API_KEY 环境变量。"
                )

        kwargs = self._build_thinking_kwargs(model, kwargs)
        thinking_config = (kwargs.get("extra_body") or {}).get("thinking")
        reasoning_effort = kwargs.get("reasoning_effort")
        if thinking_config:
            logger.info(
                f"✅ [DeepSeek初始化] thinking={thinking_config}, reasoning_effort={reasoning_effort or 'default'}"
            )
        
        # 初始化父类
        super().__init__(
            model=model,
            openai_api_key=api_key,
            openai_api_base=base_url,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        
        self.model_name = model

    @staticmethod
    def _extract_reasoning_content_from_message(message: BaseMessage) -> Optional[str]:
        if not isinstance(message, AIMessage):
            return None

        additional_kwargs = getattr(message, "additional_kwargs", {}) or {}
        reasoning_content = additional_kwargs.get("reasoning_content")
        if reasoning_content:
            return str(reasoning_content)

        response_metadata = getattr(message, "response_metadata", {}) or {}
        if isinstance(response_metadata, dict):
            reasoning_content = response_metadata.get("reasoning_content")
            if reasoning_content:
                return str(reasoning_content)

        content = getattr(message, "content", None)
        if isinstance(content, list):
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") not in {"thinking", "reasoning", "reasoning_content"}:
                    continue
                reasoning_text = block.get("text") or block.get("content") or block.get("reasoning_content")
                if reasoning_text:
                    return str(reasoning_text)

        return None

    def _convert_message_to_deepseek_dict(self, message: BaseMessage) -> Dict[str, Any]:
        message_dict = _convert_message_to_dict(message)
        reasoning_content = self._extract_reasoning_content_from_message(message)
        if reasoning_content and message_dict.get("role") == "assistant":
            message_dict["reasoning_content"] = reasoning_content
        return message_dict

    @staticmethod
    def _extract_tool_call_ids(message: BaseMessage) -> List[str]:
        if not isinstance(message, AIMessage):
            return []

        tool_calls = getattr(message, "tool_calls", None) or []
        tool_call_ids: List[str] = []
        for tool_call in tool_calls:
            if not isinstance(tool_call, dict):
                continue
            tool_call_id = str(tool_call.get("id") or "").strip()
            if tool_call_id:
                tool_call_ids.append(tool_call_id)
        return tool_call_ids

    def _sanitize_messages_for_deepseek(self, messages: List[BaseMessage]) -> List[BaseMessage]:
        """移除 DeepSeek 严格校验下不合法的 tool_call 历史。"""
        sanitized: List[BaseMessage] = []
        index = 0

        while index < len(messages):
            message = messages[index]

            if isinstance(message, AIMessage):
                tool_call_ids = self._extract_tool_call_ids(message)
                if tool_call_ids:
                    contiguous_tool_messages: List[ToolMessage] = []
                    matched_tool_ids: List[str] = []
                    next_index = index + 1

                    while next_index < len(messages) and isinstance(messages[next_index], ToolMessage):
                        tool_message = messages[next_index]
                        tool_call_id = str(getattr(tool_message, "tool_call_id", "") or "").strip()
                        if tool_call_id and tool_call_id in tool_call_ids and tool_call_id not in matched_tool_ids:
                            contiguous_tool_messages.append(tool_message)
                            matched_tool_ids.append(tool_call_id)
                        else:
                            logger.warning(
                                "⚠️ [DeepSeek] 丢弃孤立或不匹配的 ToolMessage: tool_call_id=%s",
                                tool_call_id or "<empty>",
                            )
                        next_index += 1

                    missing_tool_ids = [tool_call_id for tool_call_id in tool_call_ids if tool_call_id not in matched_tool_ids]
                    if missing_tool_ids:
                        logger.warning(
                            "⚠️ [DeepSeek] 检测到未闭合的 assistant tool_calls，已丢弃该消息片段: missing_tool_call_ids=%s",
                            missing_tool_ids,
                        )
                        index = next_index
                        continue

                    sanitized.append(message)
                    sanitized.extend(contiguous_tool_messages)
                    index = next_index
                    continue

            if isinstance(message, ToolMessage):
                logger.warning(
                    "⚠️ [DeepSeek] 检测到没有前置 assistant tool_calls 的 ToolMessage，已丢弃: tool_call_id=%s",
                    str(getattr(message, "tool_call_id", "") or "<empty>"),
                )
                index += 1
                continue

            sanitized.append(message)
            index += 1

        return sanitized

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        messages = self._convert_input(input_).to_messages()
        messages = self._sanitize_messages_for_deepseek(messages)
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        if "messages" in payload:
            payload["messages"] = [self._convert_message_to_deepseek_dict(message) for message in messages]
        return payload

    def _create_chat_result(
        self,
        response: Any,
        generation_info: Optional[Dict[str, Any]] = None,
    ) -> ChatResult:
        result = super()._create_chat_result(response, generation_info)
        response_dict = response if isinstance(response, dict) else response.model_dump()
        choices = response_dict.get("choices") or []

        for generation, choice in zip(result.generations, choices):
            if not isinstance(generation.message, AIMessage):
                continue
            message_payload = choice.get("message") or {}
            reasoning_content = message_payload.get("reasoning_content")
            if reasoning_content:
                generation.message.additional_kwargs["reasoning_content"] = reasoning_content

        return result
        
    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        生成聊天响应，并记录token使用量
        """

        # 记录开始时间
        start_time = time.time()

        # 提取并移除自定义参数，避免传递给父类
        session_id = kwargs.pop('session_id', None)
        analysis_type = kwargs.pop('analysis_type', None)

        try:
            # 调用父类方法生成响应
            result = super()._generate(messages, stop, run_manager, **kwargs)
            
            # 提取token使用量
            input_tokens = 0
            output_tokens = 0
            
            # 尝试从响应中提取token使用量
            if hasattr(result, 'llm_output') and result.llm_output:
                token_usage = result.llm_output.get('token_usage', {})
                if token_usage:
                    input_tokens = token_usage.get('prompt_tokens', 0)
                    output_tokens = token_usage.get('completion_tokens', 0)
            
            # 如果没有获取到token使用量，进行估算
            if input_tokens == 0 and output_tokens == 0:
                input_tokens = self._estimate_input_tokens(messages)
                output_tokens = self._estimate_output_tokens(result)
                logger.debug(f"🔍 [DeepSeek] 使用估算token: 输入={input_tokens}, 输出={output_tokens}")
            else:
                logger.info(f"📊 [DeepSeek] 实际token使用: 输入={input_tokens}, 输出={output_tokens}")
            
            # 记录token使用量
            if TOKEN_TRACKING_ENABLED and (input_tokens > 0 or output_tokens > 0):
                try:
                    # 使用提取的参数或生成默认值
                    if session_id is None:
                        session_id = f"deepseek_{hash(str(messages))%10000}"
                    if analysis_type is None:
                        analysis_type = 'stock_analysis'

                    # 记录使用量
                    usage_record = token_tracker.track_usage(
                        provider="deepseek",
                        model_name=self.model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        session_id=session_id,
                        analysis_type=analysis_type
                    )

                    if usage_record:
                        if usage_record.cost == 0.0:
                            logger.warning(f"⚠️ [DeepSeek] 成本计算为0，可能配置有问题")
                        else:
                            logger.info(f"💰 [DeepSeek] 本次调用成本: ¥{usage_record.cost:.6f}")

                        # 使用统一日志管理器的Token记录方法
                        logger_manager = get_logger_manager()
                        logger_manager.log_token_usage(
                            logger, "deepseek", self.model_name,
                            input_tokens, output_tokens, usage_record.cost,
                            session_id
                        )
                    else:
                        logger.warning(f"⚠️ [DeepSeek] 未创建使用记录")

                except Exception as track_error:
                    logger.error(f"⚠️ [DeepSeek] Token统计失败: {track_error}", exc_info=True)
            
            return result
            
        except Exception as e:
            logger.error(f"❌ [DeepSeek] 调用失败: {e}", exc_info=True)
            raise
    
    def _estimate_input_tokens(self, messages: List[BaseMessage]) -> int:
        """
        估算输入token数量
        
        Args:
            messages: 输入消息列表
            
        Returns:
            估算的输入token数量
        """
        total_chars = 0
        for message in messages:
            if hasattr(message, 'content'):
                total_chars += len(str(message.content))
        
        # 粗略估算：中文约1.5字符/token，英文约4字符/token
        # 这里使用保守估算：2字符/token
        estimated_tokens = max(1, total_chars // 2)
        return estimated_tokens
    
    def _estimate_output_tokens(self, result: ChatResult) -> int:
        """
        估算输出token数量
        
        Args:
            result: 聊天结果
            
        Returns:
            估算的输出token数量
        """
        total_chars = 0
        for generation in result.generations:
            if hasattr(generation, 'message') and hasattr(generation.message, 'content'):
                total_chars += len(str(generation.message.content))
        
        # 粗略估算：2字符/token
        estimated_tokens = max(1, total_chars // 2)
        return estimated_tokens
    
    def invoke(
        self,
        input: Union[str, List[BaseMessage]],
        config: Optional[Dict] = None,
        **kwargs: Any,
    ) -> AIMessage:
        """
        调用模型生成响应
        
        Args:
            input: 输入消息
            config: 配置参数
            **kwargs: 其他参数（包括session_id和analysis_type）
            
        Returns:
            AI消息响应
        """
        
        # 处理输入
        if isinstance(input, str):
            messages = [HumanMessage(content=input)]
        else:
            messages = input
        
        # 调用生成方法
        result = self._generate(messages, **kwargs)
        
        # 返回第一个生成结果的消息
        if result.generations:
            return result.generations[0].message
        else:
            return AIMessage(content="")


def create_deepseek_llm(
    model: str = "deepseek-chat",
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    **kwargs
) -> ChatDeepSeek:
    """
    创建DeepSeek LLM实例的便捷函数
    
    Args:
        model: 模型名称
        temperature: 温度参数
        max_tokens: 最大token数
        **kwargs: 其他参数
        
    Returns:
        ChatDeepSeek实例
    """
    return ChatDeepSeek(
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


# 为了向后兼容，提供别名
DeepSeekLLM = ChatDeepSeek
