"""
DeepSeek LLM适配器，支持Token使用统计
"""

import os
import time
from typing import Any, Dict, List, Optional, Union
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.prompt_values import ChatPromptValue
from langchain_openai import ChatOpenAI
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

    def _process_messages_for_deepseek(self, messages) -> List[BaseMessage]:
        """
        处理消息格式以满足DeepSeek API要求
        主要处理工具调用时的reasoning_content字段
        """
        logger.debug(f"🔧 [DeepSeek] 开始处理消息，输入类型: {type(messages)}")

        # 🔥 关键修复：处理不同的输入类型
        if isinstance(messages, ChatPromptValue):
            # 如果是ChatPromptValue，提取消息列表
            message_list = messages.messages
            logger.debug(f"🔧 [DeepSeek] 从ChatPromptValue提取消息，数量: {len(message_list)}")
        elif isinstance(messages, list):
            # 如果是列表，直接使用
            message_list = messages
            logger.debug(f"🔧 [DeepSeek] 直接使用消息列表，数量: {len(message_list)}")
        else:
            logger.warning(f"🔧 [DeepSeek] 未知消息类型: {type(messages)}，尝试直接使用")
            message_list = [messages] if not isinstance(messages, list) else messages

        # 🔥 调试：打印原始消息信息
        logger.debug(f"🔧 [DeepSeek] ===== 原始消息调试信息 =====")
        for i, msg in enumerate(message_list):
            msg_type = type(msg).__name__
            has_additional = hasattr(msg, 'additional_kwargs') and msg.additional_kwargs
            reasoning_content = getattr(msg, 'additional_kwargs', {}).get('reasoning_content', 'None') if has_additional else 'None'
            logger.debug(f"🔧 [DeepSeek] 消息{i}: {msg_type}, has_additional_kwargs: {has_additional}, reasoning_content: {reasoning_content}")

        processed_messages = []

        for i, message in enumerate(message_list):
            logger.debug(f"🔧 [DeepSeek] 处理消息 {i}: 类型={type(message).__name__}")

            # 🔥 修复：更宽松的消息类型检查和处理
            if isinstance(message, dict):
                # 如果是字典，尝试确定消息类型并处理
                role = message.get('role', '')
                content = message.get('content', '')
                logger.debug(f"🔧 [DeepSeek] 字典消息 role={role}, content长度={len(str(content))}")

                # 对于字典消息，直接添加reasoning_content
                if role == 'assistant':
                    message['reasoning_content'] = f"助手响应推理：基于当前上下文生成响应。索引位置: {i}"
                processed_messages.append(message)
                logger.debug(f"🔧 [DeepSeek] 处理字典消息完成，索引: {i}")

            elif isinstance(message, (AIMessage, HumanMessage, SystemMessage, ToolMessage)):
                if isinstance(message, AIMessage):
                    # 检查是否有工具调用
                    if hasattr(message, 'tool_calls') and message.tool_calls:
                        # 🔥 修复：直接修改原消息的additional_kwargs，而不是创建新消息
                        if not hasattr(message, 'additional_kwargs'):
                            message.additional_kwargs = {}
                        message.additional_kwargs["reasoning_content"] = f"工具调用决策：基于当前分析需要，决定调用工具获取数据。索引位置: {i}"
                        processed_messages.append(message)
                        logger.debug(f"🔧 [DeepSeek] 为AIMessage添加reasoning_content字段，索引: {i}")
                    else:
                        # 没有工具调用的情况，直接添加reasoning_content到原消息
                        if not hasattr(message, 'additional_kwargs'):
                            message.additional_kwargs = {}
                        if "reasoning_content" not in message.additional_kwargs:
                            message.additional_kwargs["reasoning_content"] = f"分析推理：基于已有信息进行分析和判断。索引位置: {i}"
                        processed_messages.append(message)
                        logger.debug(f"🔧 [DeepSeek] 为AIMessage添加analysis reasoning_content字段，索引: {i}")
                elif isinstance(message, ToolMessage):
                    # 直接修改原ToolMessage的additional_kwargs
                    if not hasattr(message, 'additional_kwargs'):
                        message.additional_kwargs = {}
                    message.additional_kwargs["reasoning_content"] = f"工具返回结果处理：正在处理工具返回的数据。索引位置: {i}"
                    processed_messages.append(message)
                    logger.debug(f"🔧 [DeepSeek] 为ToolMessage添加reasoning_content字段，索引: {i}")
                else:
                    # HumanMessage和SystemMessage保持原样
                    processed_messages.append(message)
                    logger.debug(f"🔧 [DeepSeek] 保持{type(message).__name__}原样，索引: {i}")
            else:
                # 其他未知类型，保持原样但记录警告
                logger.warning(f"⚠️ [DeepSeek] 未知消息类型但保持原样: {type(message)}")
                processed_messages.append(message)

        # 🔥 调试：打印处理后消息信息
        logger.debug(f"🔧 [DeepSeek] ===== 处理后消息调试信息 =====")
        for i, msg in enumerate(processed_messages):
            msg_type = type(msg).__name__
            has_additional = hasattr(msg, 'additional_kwargs') and msg.additional_kwargs
            reasoning_content = getattr(msg, 'additional_kwargs', {}).get('reasoning_content', 'None') if has_additional else 'None'
            logger.debug(f"🔧 [DeepSeek] 处理后消息{i}: {msg_type}, has_additional_kwargs: {has_additional}, reasoning_content: {reasoning_content}")

        logger.debug(f"🔧 [DeepSeek] 消息处理完成，处理后消息数量: {len(processed_messages)}")
        return processed_messages

    def _get_request_payload(self, messages: List[BaseMessage], **kwargs: Any) -> dict:
        """
        重写请求payload生成，注入reasoning_content字段
        """
        # 先调用父类方法获取基础payload
        payload = super()._get_request_payload(messages, **kwargs)

        logger.debug(f"🔧 [DeepSeek] ===== OpenAI Payload 修改 =====")
        logger.debug(f"🔧 [DeepSeek] 原始消息数量: {len(messages)}")

        # 🔥 关键修复：直接修改payload中的messages格式
        if 'messages' in payload:
            for i, msg_data in enumerate(payload['messages']):
                # 找到对应的LangChain消息
                if i < len(messages):
                    original_msg = messages[i]

                    # 检查是否是AIMessage且需要reasoning_content
                    if (isinstance(original_msg, AIMessage) and
                        hasattr(original_msg, 'additional_kwargs') and
                        original_msg.additional_kwargs and
                        'reasoning_content' in original_msg.additional_kwargs):

                        # 直接注入reasoning_content字段到OpenAI API payload
                        msg_data['reasoning_content'] = original_msg.additional_kwargs['reasoning_content']
                        logger.debug(f"🔧 [DeepSeek] 注入reasoning_content到消息{i}: {msg_data['reasoning_content']}")

                    # 检查是否是字典消息且已经有reasoning_content
                    elif isinstance(original_msg, dict) and 'reasoning_content' in original_msg:
                        msg_data['reasoning_content'] = original_msg['reasoning_content']
                        logger.debug(f"🔧 [DeepSeek] 从字典消息注入reasoning_content到消息{i}: {msg_data['reasoning_content']}")

                logger.debug(f"🔧 [DeepSeek] Payload消息{i}字段: {list(msg_data.keys())}")

        logger.debug(f"🔧 [DeepSeek] ===== Payload 修改完成 =====")
        return payload

    
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

        # 🔥 DeepSeek修复：处理消息格式，添加reasoning_content字段
        processed_messages = self._process_messages_for_deepseek(messages)

        try:
            logger.debug(f"🔧 [DeepSeek] 使用处理后的消息，数量: {len(processed_messages)}")
            result = super()._generate(processed_messages, stop, run_manager, **kwargs)
            
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
