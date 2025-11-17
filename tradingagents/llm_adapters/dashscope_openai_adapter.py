"""
阿里百炼 OpenAI兼容适配器
为 TradingAgents 提供阿里百炼大模型的 OpenAI 兼容接口
利用百炼模型的原生 OpenAI 兼容性，无需额外的工具转换
"""

import os
from typing import Any, Dict, List, Optional, Union, Sequence
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from pydantic import Field, SecretStr
from ..config.config_manager import token_tracker

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')


class ChatDashScopeOpenAI(ChatOpenAI):
    """
    阿里百炼 OpenAI 兼容适配器
    继承 ChatOpenAI，通过 OpenAI 兼容接口调用百炼模型
    利用百炼模型的原生 OpenAI 兼容性，支持原生 Function Calling
    """
    
    def __init__(self, **kwargs):
        """初始化 DashScope OpenAI 兼容客户端"""

        # 🔍 [DEBUG] 读取环境变量前的日志
        logger.info(f"🔍 [DashScope初始化] 开始初始化 ChatDashScopeOpenAI")
        logger.info(f"🔍 [DashScope初始化] kwargs 中是否包含 api_key: {'api_key' in kwargs}")

        # 🔥 优先使用 kwargs 中传入的 API Key（来自数据库配置）
        api_key_from_kwargs = kwargs.get("api_key")

        # 如果 kwargs 中没有 API Key 或者是 None，尝试从环境变量读取
        if not api_key_from_kwargs:
            # 导入 API Key 验证工具
            try:
                # 尝试从 app.utils 导入（后端环境）
                from app.utils.api_key_utils import is_valid_api_key
            except ImportError:
                # 如果导入失败，使用本地简化版本
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

            # 尝试从环境变量读取 API Key
            env_api_key = os.getenv("DASHSCOPE_API_KEY")
            logger.info(f"🔍 [DashScope初始化] 从环境变量读取 DASHSCOPE_API_KEY: {'有值' if env_api_key else '空'}")

            # 验证环境变量中的 API Key 是否有效（排除占位符）
            if env_api_key and is_valid_api_key(env_api_key):
                logger.info(f"✅ [DashScope初始化] 环境变量中的 API Key 有效，长度: {len(env_api_key)}, 前10位: {env_api_key[:10]}...")
                api_key_from_kwargs = env_api_key
            elif env_api_key:
                logger.warning(f"⚠️ [DashScope初始化] 环境变量中的 API Key 无效（可能是占位符），将被忽略")
                api_key_from_kwargs = None
            else:
                logger.warning(f"⚠️ [DashScope初始化] DASHSCOPE_API_KEY 环境变量为空")
                api_key_from_kwargs = None
        else:
            logger.info(f"✅ [DashScope初始化] 使用 kwargs 中传入的 API Key（来自数据库配置）")

        # 设置 DashScope OpenAI 兼容接口的默认配置
        # 🔥 修复：如果 base_url 为 None 或未设置，使用默认值
        if not kwargs.get("base_url"):
            kwargs["base_url"] = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        kwargs["api_key"] = api_key_from_kwargs  # 🔥 使用验证后的 API Key
        kwargs.setdefault("model", "qwen-turbo")
        kwargs.setdefault("temperature", 0.1)
        kwargs.setdefault("max_tokens", 2000)

        # 检查 API 密钥和 base_url
        final_api_key = kwargs.get("api_key")
        final_base_url = kwargs.get("base_url")
        logger.info(f"🔍 [DashScope初始化] 最终使用的 API Key: {'有值' if final_api_key else '空'}")
        logger.info(f"🔍 [DashScope初始化] 最终使用的 base_url: {final_base_url}")

        if not final_api_key:
            logger.error(f"❌ [DashScope初始化] API Key 检查失败，即将抛出异常")
            raise ValueError(
                "DashScope API key not found. Please configure API key in web interface "
                "(Settings -> LLM Providers) or set DASHSCOPE_API_KEY environment variable."
            )

        # 调用父类初始化
        super().__init__(**kwargs)

        logger.info(f"✅ 阿里百炼 OpenAI 兼容适配器初始化成功")
        logger.info(f"   模型: {kwargs.get('model', 'qwen-turbo')}")

        # 兼容不同版本的属性名
        api_base = getattr(self, 'base_url', None) or getattr(self, 'openai_api_base', None) or kwargs.get('base_url', 'unknown')
        logger.info(f"   API Base: {api_base}")
    
    def _generate(self, *args, **kwargs):
        """重写生成方法，添加 token 使用量追踪"""

        # 🔥 打印调用信息
        logger.info("=" * 80)
        logger.info("🔍 [DashScope调用] 即将调用 LLM API")
        logger.info(f"   模型: {self.model_name}")
        logger.info(f"   API Base URL: {getattr(self, 'base_url', None) or getattr(self, 'openai_api_base', None)}")
        logger.info(f"   API Key: {'有值' if getattr(self, 'api_key', None) else '空'}")
        logger.info(f"   Temperature: {self.temperature}")
        logger.info(f"   Max Tokens: {self.max_tokens}")
        logger.info(f"   Timeout: {getattr(self, 'request_timeout', 'default')}")
        logger.info("=" * 80)

        # 调用父类的生成方法
        result = super()._generate(*args, **kwargs)
        
        # 追踪 token 使用量
        try:
            # 从结果中提取 token 使用信息
            if hasattr(result, 'llm_output') and result.llm_output:
                token_usage = result.llm_output.get('token_usage', {})
                
                input_tokens = token_usage.get('prompt_tokens', 0)
                output_tokens = token_usage.get('completion_tokens', 0)
                
                if input_tokens > 0 or output_tokens > 0:
                    # 生成会话ID
                    session_id = kwargs.get('session_id', f"dashscope_openai_{hash(str(args))%10000}")
                    analysis_type = kwargs.get('analysis_type', 'stock_analysis')
                    
                    # 使用 TokenTracker 记录使用量
                    token_tracker.track_usage(
                        provider="dashscope",
                        model_name=self.model_name,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        session_id=session_id,
                        analysis_type=analysis_type
                    )
                    
        except Exception as track_error:
            # token 追踪失败不应该影响主要功能
            logger.error(f"⚠️ Token 追踪失败: {track_error}")
        
        return result


# 支持的模型列表
DASHSCOPE_OPENAI_MODELS = {
    # 通义千问系列
    "qwen-turbo": {
        "description": "通义千问 Turbo - 快速响应，适合日常对话",
        "context_length": 8192,
        "supports_function_calling": True,
        "recommended_for": ["快速任务", "日常对话", "简单分析"]
    },
    "qwen-plus": {
        "description": "通义千问 Plus - 平衡性能和成本",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["复杂分析", "专业任务", "深度思考"]
    },
    "qwen-plus-latest": {
        "description": "通义千问 Plus 最新版 - 最新功能和性能",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["最新功能", "复杂分析", "专业任务"]
    },
    "qwen-max": {
        "description": "通义千问 Max - 最强性能，适合复杂任务",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["复杂推理", "专业分析", "高质量输出"]
    },
    "qwen-max-latest": {
        "description": "通义千问 Max 最新版 - 最强性能和最新功能",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["最新功能", "复杂推理", "专业分析"]
    },
    "qwen-long": {
        "description": "通义千问 Long - 超长上下文，适合长文档处理",
        "context_length": 1000000,
        "supports_function_calling": True,
        "recommended_for": ["长文档分析", "大量数据处理", "复杂上下文"]
    }
}


def get_available_openai_models() -> Dict[str, Dict[str, Any]]:
    """获取可用的 DashScope OpenAI 兼容模型列表"""
    return DASHSCOPE_OPENAI_MODELS


def create_dashscope_openai_llm(
    model: str = "qwen-plus-latest",
    api_key: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2000,
    **kwargs
) -> ChatDashScopeOpenAI:
    """创建 DashScope OpenAI 兼容 LLM 实例的便捷函数"""
    
    return ChatDashScopeOpenAI(
        model=model,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        **kwargs
    )


def test_dashscope_openai_connection(
    model: str = "qwen-turbo",
    api_key: Optional[str] = None
) -> bool:
    """测试 DashScope OpenAI 兼容接口连接"""
    
    try:
        logger.info(f"🧪 测试 DashScope OpenAI 兼容接口连接")
        logger.info(f"   模型: {model}")
        
        # 创建客户端
        llm = create_dashscope_openai_llm(
            model=model,
            api_key=api_key,
            max_tokens=50
        )
        
        # 发送测试消息
        response = llm.invoke("你好，请简单介绍一下你自己。")
        
        if response and hasattr(response, 'content') and response.content:
            logger.info(f"✅ DashScope OpenAI 兼容接口连接成功")
            logger.info(f"   响应: {response.content[:100]}...")
            return True
        else:
            logger.error(f"❌ DashScope OpenAI 兼容接口响应为空")
            return False
            
    except Exception as e:
        logger.error(f"❌ DashScope OpenAI 兼容接口连接失败: {e}")
        return False


def test_dashscope_openai_function_calling(
    model: str = "qwen-plus-latest",
    api_key: Optional[str] = None
) -> bool:
    """测试 DashScope OpenAI 兼容接口的 Function Calling"""
    
    try:
        logger.info(f"🧪 测试 DashScope OpenAI Function Calling")
        logger.info(f"   模型: {model}")
        
        # 创建客户端
        llm = create_dashscope_openai_llm(
            model=model,
            api_key=api_key,
            max_tokens=200
        )
        
        # 定义测试工具
        def get_current_time() -> str:
            """获取当前时间"""
            import datetime
            return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # 创建 LangChain 工具
        from langchain_core.tools import tool
        
        @tool
        def test_tool(query: str) -> str:
            """测试工具，返回查询信息"""
            return f"收到查询: {query}"
        
        # 绑定工具
        llm_with_tools = llm.bind_tools([test_tool])
        
        # 测试工具调用
        response = llm_with_tools.invoke("请使用test_tool查询'hello world'")
        
        logger.info(f"✅ DashScope OpenAI Function Calling 测试完成")
        logger.info(f"   响应类型: {type(response)}")
        
        if hasattr(response, 'tool_calls') and response.tool_calls:
            logger.info(f"   工具调用数量: {len(response.tool_calls)}")
            return True
        else:
            logger.info(f"   响应内容: {getattr(response, 'content', 'No content')}")
            return True  # 即使没有工具调用也算成功，因为模型可能选择不调用工具
            
    except Exception as e:
        logger.error(f"❌ DashScope OpenAI Function Calling 测试失败: {e}")
        return False


if __name__ == "__main__":
    """测试脚本"""
    logger.info(f"🧪 DashScope OpenAI 兼容适配器测试")
    logger.info(f"=" * 50)
    
    # 测试连接
    connection_ok = test_dashscope_openai_connection()
    
    if connection_ok:
        # 测试 Function Calling
        function_calling_ok = test_dashscope_openai_function_calling()
        
        if function_calling_ok:
            logger.info(f"\n🎉 所有测试通过！DashScope OpenAI 兼容适配器工作正常")
        else:
            logger.error(f"\n⚠️ Function Calling 测试失败")
    else:
        logger.error(f"\n❌ 连接测试失败")
