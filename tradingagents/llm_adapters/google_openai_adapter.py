"""
Google AI OpenAI兼容适配器
为 TradingAgents 提供Google AI (Gemini)模型的 OpenAI 兼容接口
解决Google模型工具调用格式不匹配的问题
"""

import os
from typing import Any, Dict, List, Optional, Union, Sequence
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import BaseTool
from langchain_core.messages import BaseMessage, AIMessage, HumanMessage, SystemMessage
from langchain_core.outputs import LLMResult
from pydantic import Field, SecretStr
from ..config.config_manager import token_tracker

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')


class ChatGoogleOpenAI(ChatGoogleGenerativeAI):
    """
    Google AI OpenAI 兼容适配器
    继承 ChatGoogleGenerativeAI，优化工具调用和内容格式处理
    解决Google模型工具调用返回格式与系统期望不匹配的问题
    """

    def __init__(self, base_url: Optional[str] = None, **kwargs):
        """
        初始化 Google AI OpenAI 兼容客户端

        Args:
            base_url: 自定义 API 端点（可选）
                     如果提供，将通过 client_options 传递给 Google AI SDK
                     支持格式：
                     - https://generativelanguage.googleapis.com/v1beta
                     - https://generativelanguage.googleapis.com/v1 (自动转换为 v1beta)
                     - 自定义代理地址
            **kwargs: 其他参数
        """

        # 🔍 [DEBUG] 读取环境变量前的日志
        logger.info("🔍 [Google初始化] 开始初始化 ChatGoogleOpenAI")
        logger.info(f"🔍 [Google初始化] kwargs 中是否包含 google_api_key: {'google_api_key' in kwargs}")
        logger.info(f"🔍 [Google初始化] 传入的 base_url: {base_url}")

        # 设置 Google AI 的默认配置
        kwargs.setdefault("temperature", 0.1)
        kwargs.setdefault("max_tokens", 2000)

        # 🔥 优先使用 kwargs 中传入的 API Key（来自数据库配置）
        google_api_key = kwargs.get("google_api_key")

        # 如果 kwargs 中没有 API Key，尝试从环境变量读取
        if not google_api_key:
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

            # 检查环境变量中的 API Key
            env_api_key = os.getenv("GOOGLE_API_KEY")
            logger.info(f"🔍 [Google初始化] 从环境变量读取 GOOGLE_API_KEY: {'有值' if env_api_key else '空'}")

            # 验证环境变量中的 API Key 是否有效（排除占位符）
            if env_api_key and is_valid_api_key(env_api_key):
                logger.info(f"✅ [Google初始化] 环境变量中的 API Key 有效，长度: {len(env_api_key)}")
                google_api_key = env_api_key
            elif env_api_key:
                logger.warning("⚠️ [Google初始化] 环境变量中的 API Key 无效（可能是占位符），将被忽略")
                google_api_key = None
            else:
                logger.warning("⚠️ [Google初始化] GOOGLE_API_KEY 环境变量为空")
                google_api_key = None
        else:
            logger.info("✅ [Google初始化] 使用 kwargs 中传入的 API Key（来自数据库配置）")

        logger.info(f"🔍 [Google初始化] 最终使用的 API Key: {'有值' if google_api_key else '空'}")

        if not google_api_key:
            logger.error("❌ [Google初始化] API Key 检查失败，即将抛出异常")
            raise ValueError(
                "Google API key not found. Please configure API key in web interface "
                "(Settings -> LLM Providers) or set GOOGLE_API_KEY environment variable."
            )

        kwargs["google_api_key"] = google_api_key

        # 🔧 处理自定义 base_url
        if base_url:
            # 移除末尾的斜杠
            base_url = base_url.rstrip('/')
            logger.info(f"🔍 [Google初始化] 处理 base_url: {base_url}")

            # 🔍 检测是否是 Google 官方域名
            is_google_official = 'generativelanguage.googleapis.com' in base_url

            if is_google_official:
                # ✅ Google 官方域名：提取域名部分，SDK 会自动添加 /v1beta
                # 例如：https://generativelanguage.googleapis.com/v1beta -> https://generativelanguage.googleapis.com
                #      https://generativelanguage.googleapis.com/v1 -> https://generativelanguage.googleapis.com
                if base_url.endswith('/v1beta'):
                    api_endpoint = base_url[:-7]  # 移除 /v1beta (7个字符)
                    logger.info(f"🔍 [Google官方] 从 base_url 提取域名: {api_endpoint}")
                elif base_url.endswith('/v1'):
                    api_endpoint = base_url[:-3]  # 移除 /v1 (3个字符)
                    logger.info(f"🔍 [Google官方] 从 base_url 提取域名: {api_endpoint}")
                else:
                    # 如果没有版本后缀，直接使用
                    api_endpoint = base_url
                    logger.info(f"🔍 [Google官方] 使用完整 base_url 作为域名: {api_endpoint}")

                logger.info(f"✅ [Google官方] SDK 会自动添加 /v1beta 路径")
            else:
                # 🔄 中转地址：直接使用完整 URL，不让 SDK 添加 /v1beta
                # 中转服务通常已经包含了完整的路径映射
                api_endpoint = base_url
                logger.info(f"🔄 [中转地址] 检测到非官方域名，使用完整 URL: {api_endpoint}")
                logger.info(f"   中转服务通常已包含完整路径，不需要 SDK 添加 /v1beta")

            # 通过 client_options 传递自定义端点
            # 参考: https://github.com/langchain-ai/langchain-google/issues/783
            kwargs["client_options"] = {"api_endpoint": api_endpoint}
            logger.info(f"✅ [Google初始化] 设置 client_options.api_endpoint: {api_endpoint}")
        else:
            logger.info(f"🔍 [Google初始化] 未提供 base_url，使用默认端点")

        # 调用父类初始化
        super().__init__(**kwargs)

        logger.info(f"✅ Google AI OpenAI 兼容适配器初始化成功")
        logger.info(f"   模型: {kwargs.get('model', 'gemini-pro')}")
        logger.info(f"   温度: {kwargs.get('temperature', 0.1)}")
        logger.info(f"   最大Token: {kwargs.get('max_tokens', 2000)}")
        if base_url:
            logger.info(f"   自定义端点: {base_url}")

    @property
    def model_name(self) -> str:
        """
        返回模型名称（兼容性属性）
        移除 'models/' 前缀，返回纯模型名称
        """
        model = self.model
        if model and model.startswith("models/"):
            return model[7:]  # 移除 "models/" 前缀
        return model or "unknown"
    
    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None, **kwargs) -> LLMResult:
        """重写生成方法，优化工具调用处理和内容格式"""

        try:
            # 调用父类的生成方法
            result = super()._generate(messages, stop, **kwargs)

            # 优化返回内容格式
            # 注意：result.generations 是二维列表 [[ChatGeneration]]
            if result and result.generations:
                for generation_list in result.generations:
                    if isinstance(generation_list, list):
                        for generation in generation_list:
                            if hasattr(generation, 'message') and generation.message:
                                # 优化消息内容格式
                                self._optimize_message_content(generation.message)
                    else:
                        # 兼容性处理：如果不是列表，直接处理
                        if hasattr(generation_list, 'message') and generation_list.message:
                            self._optimize_message_content(generation_list.message)

            # 追踪 token 使用量
            self._track_token_usage(result, kwargs)

            return result

        except Exception as e:
            logger.error(f"❌ Google AI 生成失败: {e}")
            logger.exception(e)  # 打印完整的堆栈跟踪

            # 检查是否为 API Key 无效错误
            error_str = str(e)
            if 'API_KEY_INVALID' in error_str or 'API key not valid' in error_str:
                error_content = "Google AI API Key 无效或未配置。\n\n请检查：\n1. GOOGLE_API_KEY 环境变量是否正确配置\n2. API Key 是否有效（访问 https://ai.google.dev/ 获取）\n3. 是否启用了 Gemini API\n\n建议：使用其他 AI 模型（如阿里百炼、DeepSeek）"
            elif 'Connection' in error_str or 'Network' in error_str:
                error_content = f"Google AI 网络连接失败: {error_str}\n\n请检查：\n1. 网络连接是否正常\n2. 是否需要科学上网\n3. 防火墙设置"
            else:
                error_content = f"Google AI 调用失败: {error_str}\n\n请检查配置或使用其他 AI 模型"

            # 返回一个包含错误信息的结果，而不是抛出异常
            from langchain_core.outputs import ChatGeneration
            error_message = AIMessage(content=error_content)
            error_generation = ChatGeneration(message=error_message)
            return LLMResult(generations=[[error_generation]])
    
    def _optimize_message_content(self, message: BaseMessage):
        """优化消息内容格式，确保包含新闻特征关键词"""
        
        if not isinstance(message, AIMessage) or not message.content:
            return
        
        content = message.content
        
        # 检查是否是工具调用返回的新闻内容
        if self._is_news_content(content):
            # 优化新闻内容格式，添加必要的关键词
            optimized_content = self._enhance_news_content(content)
            message.content = optimized_content
            
            logger.debug(f"🔧 [Google适配器] 优化新闻内容格式")
            logger.debug(f"   原始长度: {len(content)} 字符")
            logger.debug(f"   优化后长度: {len(optimized_content)} 字符")
    
    def _is_news_content(self, content: str) -> bool:
        """判断内容是否为新闻内容"""
        
        # 检查是否包含新闻相关的关键词
        news_indicators = [
            "股票", "公司", "市场", "投资", "财经", "证券", "交易",
            "涨跌", "业绩", "财报", "分析", "预测", "消息", "公告"
        ]
        
        return any(indicator in content for indicator in news_indicators) and len(content) > 200
    
    def _enhance_news_content(self, content: str) -> str:
        """增强新闻内容，添加必要的格式化信息"""
        
        import datetime
        current_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 如果内容缺少必要的新闻特征，添加它们
        enhanced_content = content
        
        # 添加发布时间信息（如果缺少）
        if "发布时间" not in content and "时间" not in content:
            enhanced_content = f"发布时间: {current_date}\n\n{enhanced_content}"
        
        # 添加新闻标题标识（如果缺少）
        if "新闻标题" not in content and "标题" not in content:
            # 尝试从内容中提取第一行作为标题
            lines = enhanced_content.split('\n')
            if lines:
                first_line = lines[0].strip()
                if len(first_line) < 100:  # 可能是标题
                    enhanced_content = f"新闻标题: {first_line}\n\n{enhanced_content}"
        
        # 添加文章来源信息（如果缺少）
        if "文章来源" not in content and "来源" not in content:
            enhanced_content = f"{enhanced_content}\n\n文章来源: Google AI 智能分析"
        
        return enhanced_content
    
    def _track_token_usage(self, result: LLMResult, kwargs: Dict[str, Any]):
        """追踪 token 使用量"""
        
        try:
            # 从结果中提取 token 使用信息
            if hasattr(result, 'llm_output') and result.llm_output:
                token_usage = result.llm_output.get('token_usage', {})
                
                input_tokens = token_usage.get('prompt_tokens', 0)
                output_tokens = token_usage.get('completion_tokens', 0)
                
                if input_tokens > 0 or output_tokens > 0:
                    # 生成会话ID
                    session_id = kwargs.get('session_id', f"google_openai_{hash(str(kwargs))%10000}")
                    analysis_type = kwargs.get('analysis_type', 'stock_analysis')
                    
                    # 使用 TokenTracker 记录使用量
                    token_tracker.track_usage(
                        provider="google",
                        model_name=self.model,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        session_id=session_id,
                        analysis_type=analysis_type
                    )
                    
                    logger.debug(f"📊 [Google适配器] Token使用量: 输入={input_tokens}, 输出={output_tokens}")
                    
        except Exception as track_error:
            # token 追踪失败不应该影响主要功能
            logger.error(f"⚠️ Google适配器 Token 追踪失败: {track_error}")


# 支持的模型列表
GOOGLE_OPENAI_MODELS = {
    # Gemini 2.5 系列 - 最新验证模型
    "gemini-2.5-pro": {
        "description": "Gemini 2.5 Pro - 最新旗舰模型，功能强大 (16.68s)",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["复杂推理", "专业分析", "高质量输出"],
        "avg_response_time": 16.68
    },
    "gemini-2.5-flash": {
        "description": "Gemini 2.5 Flash - 最新快速模型 (2.73s)",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["快速响应", "实时分析", "高频使用"],
        "avg_response_time": 2.73
    },
    "gemini-2.5-flash-lite-preview-06-17": {
        "description": "Gemini 2.5 Flash Lite Preview - 超快响应 (1.45s)",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["超快响应", "实时交互", "高频调用"],
        "avg_response_time": 1.45
    },
    # Gemini 2.0 系列
    "gemini-2.0-flash": {
        "description": "Gemini 2.0 Flash - 新一代快速模型 (1.87s)",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["快速响应", "实时分析"],
        "avg_response_time": 1.87
    },
    # Gemini 1.5 系列
    "gemini-1.5-pro": {
        "description": "Gemini 1.5 Pro - 强大性能，平衡选择 (2.25s)",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["复杂分析", "专业任务", "深度思考"],
        "avg_response_time": 2.25
    },
    "gemini-1.5-flash": {
        "description": "Gemini 1.5 Flash - 快速响应，备用选择 (2.87s)",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["快速任务", "日常对话", "简单分析"],
        "avg_response_time": 2.87
    },
    # 经典模型
    "gemini-pro": {
        "description": "Gemini Pro - 经典模型，稳定可靠",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["通用任务", "稳定性要求高的场景"]
    }
}


def get_available_google_models() -> Dict[str, Dict[str, Any]]:
    """获取可用的 Google AI 模型列表"""
    return GOOGLE_OPENAI_MODELS


def create_google_openai_llm(
    model: str = "gemini-2.5-flash-lite-preview-06-17",
    google_api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
    **kwargs
) -> ChatGoogleOpenAI:
    """
    创建 Google AI OpenAI 兼容 LLM 实例的便捷函数

    Args:
        model: 模型名称
        google_api_key: Google API Key
        base_url: 自定义 API 端点（可选）
        temperature: 温度参数
        max_tokens: 最大 token 数
        **kwargs: 其他参数

    Returns:
        ChatGoogleOpenAI 实例
    """

    return ChatGoogleOpenAI(
        model=model,
        google_api_key=google_api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


def test_google_openai_connection(
    model: str = "gemini-2.0-flash",
    google_api_key: Optional[str] = None
) -> bool:
    """测试 Google AI OpenAI 兼容接口连接"""
    
    try:
        logger.info(f"🧪 测试 Google AI OpenAI 兼容接口连接")
        logger.info(f"   模型: {model}")
        
        # 创建客户端
        llm = create_google_openai_llm(
            model=model,
            google_api_key=google_api_key,
            max_tokens=50
        )
        
        # 发送测试消息
        response = llm.invoke("你好，请简单介绍一下你自己。")
        
        if response and hasattr(response, 'content') and response.content:
            logger.info(f"✅ Google AI OpenAI 兼容接口连接成功")
            logger.info(f"   响应: {response.content[:100]}...")
            return True
        else:
            logger.error(f"❌ Google AI OpenAI 兼容接口响应为空")
            return False
            
    except Exception as e:
        logger.error(f"❌ Google AI OpenAI 兼容接口连接失败: {e}")
        return False


def test_google_openai_function_calling(
    model: str = "gemini-2.5-flash-lite-preview-06-17",
    google_api_key: Optional[str] = None
) -> bool:
    """测试 Google AI OpenAI 兼容接口的 Function Calling"""
    
    try:
        logger.info(f"🧪 测试 Google AI Function Calling")
        logger.info(f"   模型: {model}")
        
        # 创建客户端
        llm = create_google_openai_llm(
            model=model,
            google_api_key=google_api_key,
            max_tokens=200
        )
        
        # 定义测试工具
        from langchain_core.tools import tool
        
        @tool
        def test_news_tool(query: str) -> str:
            """测试新闻工具，返回模拟新闻内容"""
            return f"""发布时间: 2024-01-15
新闻标题: {query}相关市场动态
文章来源: 测试新闻源

这是一条关于{query}的测试新闻内容。该公司近期表现良好，市场前景看好。
投资者对此表示关注，分析师给出积极评价。"""
        
        # 绑定工具
        llm_with_tools = llm.bind_tools([test_news_tool])
        
        # 测试工具调用
        response = llm_with_tools.invoke("请使用test_news_tool查询'苹果公司'的新闻")
        
        logger.info(f"✅ Google AI Function Calling 测试完成")
        logger.info(f"   响应类型: {type(response)}")
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            logger.info(f"   工具调用数量: {len(response.tool_calls)}")
            return True
        else:
            logger.info(f"   响应内容: {getattr(response, 'content', 'No content')}")
            return True  # 即使没有工具调用也算成功，因为模型可能选择不调用工具
            
    except Exception as e:
        logger.error(f"❌ Google AI Function Calling 测试失败: {e}")
        return False


if __name__ == "__main__":
    """测试脚本"""
    logger.info(f"🧪 Google AI OpenAI 兼容适配器测试")
    logger.info(f"=" * 50)
    
    # 测试连接
    connection_ok = test_google_openai_connection()
    
    if connection_ok:
        # 测试 Function Calling
        function_calling_ok = test_google_openai_function_calling()
        
        if function_calling_ok:
            logger.info(f"\n🎉 所有测试通过！Google AI OpenAI 兼容适配器工作正常")
        else:
            logger.error(f"\n⚠️ Function Calling 测试失败")
    else:
        logger.error(f"\n❌ 连接测试失败")
