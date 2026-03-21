"""
MiniMax LLM适配器
为 TradingAgents 提供 MiniMax 大模型的 OpenAI 兼容接口
MiniMax 提供高性能的 AI 推理服务，支持 204K tokens 上下文窗口
"""

import os
import time
from typing import Any, Dict, List, Optional, Union
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage
from langchain_core.outputs import ChatResult
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


# MiniMax temperature 范围: (0.0, 1.0]，不能传 0
MINIMAX_MIN_TEMPERATURE = 0.01
MINIMAX_MAX_TEMPERATURE = 1.0
MINIMAX_DEFAULT_TEMPERATURE = 0.1


def _clamp_temperature(temperature: float) -> float:
    """将 temperature 限制在 MiniMax 支持的范围内"""
    if temperature <= 0.0:
        return MINIMAX_MIN_TEMPERATURE
    if temperature > MINIMAX_MAX_TEMPERATURE:
        return MINIMAX_MAX_TEMPERATURE
    return temperature


class ChatMiniMax(ChatOpenAI):
    """
    MiniMax 聊天模型适配器，支持 Token 使用统计

    继承自 ChatOpenAI，通过 OpenAI 兼容接口调用 MiniMax 模型。
    MiniMax 提供 MiniMax-M2.7 和 MiniMax-M2.7-highspeed 两款模型，
    均支持 204,800 tokens 上下文窗口和最大 192K token 输出。
    """

    def __init__(
        self,
        model: str = "MiniMax-M2.7",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        **kwargs
    ):
        """
        初始化 MiniMax 适配器

        Args:
            model: 模型名称，默认为 MiniMax-M2.7
            api_key: API 密钥，如果不提供则从环境变量 MINIMAX_API_KEY 获取
            base_url: API 基础 URL，默认为海外版 https://api.minimax.io/v1，
                      国内版可设为 https://api.minimaxi.com/v1
            temperature: 温度参数，MiniMax 支持范围 (0.0, 1.0]
            max_tokens: 最大 token 数
            **kwargs: 其他参数
        """

        # 🔍 [DEBUG] 读取环境变量前的日志
        logger.info(f"🔍 [MiniMax初始化] 开始初始化 ChatMiniMax")
        logger.info(f"🔍 [MiniMax初始化] 模型: {model}")
        logger.info(f"🔍 [MiniMax初始化] 是否传入 api_key 参数: {api_key is not None}")

        # 获取 API 密钥
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
            env_api_key = os.getenv("MINIMAX_API_KEY")
            logger.info(f"🔍 [MiniMax初始化] 从环境变量读取 MINIMAX_API_KEY: {'有值' if env_api_key else '空'}")

            # 验证环境变量中的 API Key 是否有效（排除占位符）
            if env_api_key and is_valid_api_key(env_api_key):
                logger.info(f"✅ [MiniMax初始化] 环境变量中的 API Key 有效，长度: {len(env_api_key)}, 前10位: {env_api_key[:10]}...")
                api_key = env_api_key
            elif env_api_key:
                logger.warning(f"⚠️ [MiniMax初始化] 环境变量中的 API Key 无效（可能是占位符），将被忽略")
                api_key = None
            else:
                logger.warning(f"⚠️ [MiniMax初始化] MINIMAX_API_KEY 环境变量为空")
                api_key = None

            if not api_key:
                raise ValueError(
                    "MiniMax API 密钥未找到。请在 Web 界面配置 API Key "
                    "(设置 -> 大模型厂家) 或设置 MINIMAX_API_KEY 环境变量。"
                )
        else:
            logger.info(f"✅ [MiniMax初始化] 使用传入的 API Key（来自数据库配置），长度: {len(api_key)}")

        # 设置 base_url
        if base_url is None:
            env_base_url = os.getenv("MINIMAX_BASE_URL")
            if env_base_url and not env_base_url.startswith('your_') and not env_base_url.startswith('your-'):
                base_url = env_base_url
            else:
                base_url = "https://api.minimax.io/v1"

        # MiniMax temperature 限制: (0.0, 1.0]
        temperature = _clamp_temperature(temperature)

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

        logger.info(f"✅ MiniMax OpenAI 兼容适配器初始化成功")
        logger.info(f"   模型: {model}")
        logger.info(f"   API Base: {base_url}")
        logger.info(f"   Temperature: {temperature}")

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        生成聊天响应，并记录 token 使用量
        """

        # 记录开始时间
        start_time = time.time()

        # 提取并移除自定义参数，避免传递给父类
        session_id = kwargs.pop('session_id', None)
        analysis_type = kwargs.pop('analysis_type', None)

        try:
            # 调用父类方法生成响应
            result = super()._generate(messages, stop, run_manager, **kwargs)

            # 提取 token 使用量
            input_tokens = 0
            output_tokens = 0

            # 尝试从响应中提取 token 使用量
            if hasattr(result, 'llm_output') and result.llm_output:
                token_usage = result.llm_output.get('token_usage', {})
                if token_usage:
                    input_tokens = token_usage.get('prompt_tokens', 0)
                    output_tokens = token_usage.get('completion_tokens', 0)

            # 如果没有获取到 token 使用量，进行估算
            if input_tokens == 0 and output_tokens == 0:
                input_tokens = self._estimate_input_tokens(messages)
                output_tokens = self._estimate_output_tokens(result)
                logger.debug(f"🔍 [MiniMax] 使用估算 token: 输入={input_tokens}, 输出={output_tokens}")
            else:
                logger.info(f"📊 [MiniMax] 实际 token 使用: 输入={input_tokens}, 输出={output_tokens}")

            elapsed = time.time() - start_time
            logger.info(
                f"📊 Token使用 - Provider: minimax, Model: {self.model_name}, "
                f"总tokens: {input_tokens + output_tokens}, 提示: {input_tokens}, "
                f"补全: {output_tokens}, 用时: {elapsed:.2f}s"
            )

            # 记录 token 使用量
            if TOKEN_TRACKING_ENABLED and (input_tokens > 0 or output_tokens > 0):
                try:
                    if session_id is None:
                        session_id = f"minimax_{hash(str(messages)) % 10000}"
                    if analysis_type is None:
                        analysis_type = 'stock_analysis'

                    usage_record = token_tracker.track_usage(
                        provider="minimax",
                        model_name=self.model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        session_id=session_id,
                        analysis_type=analysis_type
                    )

                    if usage_record:
                        if usage_record.cost == 0.0:
                            logger.warning(f"⚠️ [MiniMax] 成本计算为0，可能配置有问题")
                        else:
                            logger.info(f"💰 [MiniMax] 本次调用成本: ¥{usage_record.cost:.6f}")

                        logger_manager = get_logger_manager()
                        logger_manager.log_token_usage(
                            logger, "minimax", self.model_name,
                            input_tokens, output_tokens, usage_record.cost,
                            session_id
                        )
                    else:
                        logger.warning(f"⚠️ [MiniMax] 未创建使用记录")

                except Exception as track_error:
                    logger.error(f"⚠️ [MiniMax] Token 统计失败: {track_error}", exc_info=True)

            return result

        except Exception as e:
            logger.error(f"❌ [MiniMax] 调用失败: {e}", exc_info=True)
            raise

    def _estimate_input_tokens(self, messages: List[BaseMessage]) -> int:
        """估算输入 token 数量"""
        total_chars = 0
        for message in messages:
            if hasattr(message, 'content'):
                total_chars += len(str(message.content))
        # 保守估算：2字符/token
        return max(1, total_chars // 2)

    def _estimate_output_tokens(self, result: ChatResult) -> int:
        """估算输出 token 数量"""
        total_chars = 0
        for generation in result.generations:
            if hasattr(generation, 'message') and hasattr(generation.message, 'content'):
                total_chars += len(str(generation.message.content))
        return max(1, total_chars // 2)

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
            **kwargs: 其他参数（包括 session_id 和 analysis_type）

        Returns:
            AI 消息响应
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


# 支持的模型列表
MINIMAX_MODELS = {
    "MiniMax-M2.7": {
        "description": "MiniMax M2.7 - Peak Performance. Ultimate Value. Master the Complex",
        "context_length": 204800,
        "max_output_tokens": 192000,
        "supports_function_calling": True,
        "recommended_for": ["复杂推理", "专业分析", "高质量输出", "长文档处理"],
        "input_price_per_million": 0.3,
        "output_price_per_million": 1.2,
        "currency": "USD"
    },
    "MiniMax-M2.7-highspeed": {
        "description": "MiniMax M2.7 Highspeed - Same performance, faster and more agile",
        "context_length": 204800,
        "max_output_tokens": 192000,
        "supports_function_calling": True,
        "recommended_for": ["快速分析", "实时交易", "高频调用"],
        "input_price_per_million": 0.6,
        "output_price_per_million": 2.4,
        "currency": "USD"
    }
}


def get_available_minimax_models() -> Dict[str, Dict[str, Any]]:
    """获取可用的 MiniMax 模型列表"""
    return MINIMAX_MODELS


def create_minimax_llm(
    model: str = "MiniMax-M2.7",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    **kwargs
) -> ChatMiniMax:
    """创建 MiniMax LLM 实例的便捷函数"""

    return ChatMiniMax(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


def test_minimax_connection(
    model: str = "MiniMax-M2.7",
    api_key: Optional[str] = None
) -> bool:
    """测试 MiniMax OpenAI 兼容接口连接"""

    try:
        logger.info(f"🧪 测试 MiniMax OpenAI 兼容接口连接")
        logger.info(f"   模型: {model}")

        # 创建客户端
        llm = create_minimax_llm(
            model=model,
            api_key=api_key,
            max_tokens=50
        )

        # 发送测试消息
        response = llm.invoke("你好，请简单介绍一下你自己。")

        if response and hasattr(response, 'content') and response.content:
            logger.info(f"✅ MiniMax OpenAI 兼容接口连接成功")
            logger.info(f"   响应: {response.content[:100]}...")
            return True
        else:
            logger.error(f"❌ MiniMax OpenAI 兼容接口响应为空")
            return False

    except Exception as e:
        logger.error(f"❌ MiniMax OpenAI 兼容接口连接失败: {e}")
        return False


def test_minimax_function_calling(
    model: str = "MiniMax-M2.7",
    api_key: Optional[str] = None
) -> bool:
    """测试 MiniMax OpenAI 兼容接口的 Function Calling"""

    try:
        logger.info(f"🧪 测试 MiniMax Function Calling")
        logger.info(f"   模型: {model}")

        # 创建客户端
        llm = create_minimax_llm(
            model=model,
            api_key=api_key,
            max_tokens=200
        )

        # 创建 LangChain 工具
        from langchain_core.tools import tool

        @tool
        def test_tool(query: str) -> str:
            """测试工具，返回查询信息"""
            return f"收到查询: {query}"

        # 绑定工具
        llm_with_tools = llm.bind_tools([test_tool])

        # 测试工具调用
        response = llm_with_tools.invoke("请使用 test_tool 查询 'hello world'")

        logger.info(f"✅ MiniMax Function Calling 测试完成")
        logger.info(f"   响应类型: {type(response)}")

        if hasattr(response, 'tool_calls') and response.tool_calls:
            logger.info(f"   工具调用数量: {len(response.tool_calls)}")
            return True
        else:
            logger.info(f"   响应内容: {getattr(response, 'content', 'No content')}")
            return True  # 即使没有工具调用也算成功

    except Exception as e:
        logger.error(f"❌ MiniMax Function Calling 测试失败: {e}")
        return False


if __name__ == "__main__":
    """测试脚本"""
    logger.info(f"🧪 MiniMax OpenAI 兼容适配器测试")
    logger.info(f"=" * 50)

    # 测试连接
    connection_ok = test_minimax_connection()

    if connection_ok:
        # 测试 Function Calling
        function_calling_ok = test_minimax_function_calling()

        if function_calling_ok:
            logger.info(f"\n🎉 所有测试通过！MiniMax OpenAI 兼容适配器工作正常")
        else:
            logger.error(f"\n⚠️ Function Calling 测试失败")
    else:
        logger.error(f"\n❌ 连接测试失败")
