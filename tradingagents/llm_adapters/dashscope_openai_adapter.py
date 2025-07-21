"""
阿里百炼 OpenAI兼容适配器
为 TradingAgents 提供阿里百炼大模型的 OpenAI 兼容接口
支持原生 Function Calling 和完整的 LangChain 集成
"""

import os
from typing import Any, Dict, List, Optional, Union, Sequence
from langchain_openai import ChatOpenAI
from langchain_core.tools import BaseTool
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field, SecretStr
from ..config.config_manager import token_tracker

# 导入日志模块
from tradingagents.utils.logging_manager import get_logger
logger = get_logger('agents')


class ChatDashScopeOpenAI(ChatOpenAI):
    """
    阿里百炼 OpenAI 兼容适配器
    继承 ChatOpenAI，通过 OpenAI 兼容接口调用百炼模型
    支持原生 Function Calling 和工具调用
    """
    
    def __init__(self, **kwargs):
        """初始化 DashScope OpenAI 兼容客户端"""
        
        # 设置 DashScope OpenAI 兼容接口的默认配置
        kwargs.setdefault("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
        kwargs.setdefault("api_key", os.getenv("DASHSCOPE_API_KEY"))
        kwargs.setdefault("model", "qwen-turbo")
        kwargs.setdefault("temperature", 0.1)
        kwargs.setdefault("max_tokens", 2000)
        
        # 检查 API 密钥
        if not kwargs.get("api_key"):
            raise ValueError(
                "DashScope API key not found. Please set DASHSCOPE_API_KEY environment variable "
                "or pass api_key parameter."
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
        
        # 调用父类的生成方法
        result = super()._generate(*args, **kwargs)
        
        # 尝试追踪 token 使用量
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
    
    def bind_tools(
        self,
        tools: Sequence[Union[Dict[str, Any], type, BaseTool]],
        **kwargs: Any,
    ) -> "ChatDashScopeOpenAI":
        """
        绑定工具到模型
        使用 OpenAI 兼容的 Function Calling 格式
        """
        
        # 转换工具为 OpenAI 格式
        formatted_tools = []
        for tool in tools:
            if hasattr(tool, "name") and hasattr(tool, "description"):
                # 这是一个 BaseTool 实例
                try:
                    openai_tool = convert_to_openai_tool(tool)
                    formatted_tools.append(openai_tool)
                except Exception as e:
                    logger.error(f"⚠️ 工具转换失败: {tool.name} - {e}")
                    continue
            elif isinstance(tool, dict):
                formatted_tools.append(tool)
            else:
                # 尝试转换为 OpenAI 工具格式
                try:
                    formatted_tools.append(convert_to_openai_tool(tool))
                except Exception as e:
                    logger.error(f"⚠️ 工具转换失败: {tool} - {e}")
                    continue
        
        logger.info(f"🔧 绑定 {len(formatted_tools)} 个工具到阿里百炼模型")
        
        # 调用父类的 bind_tools 方法
        return super().bind_tools(formatted_tools, **kwargs)


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
        "description": "通义千问 Max - 最强性能",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["最复杂任务", "专业分析", "高质量输出"]
    },
    "qwen-max-latest": {
        "description": "通义千问 Max 最新版 - 最强性能最新版",
        "context_length": 32768,
        "supports_function_calling": True,
        "recommended_for": ["最复杂任务", "最新功能", "顶级性能"]
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
        from langchain_core.messages import HumanMessage
        
        llm = create_dashscope_openai_llm(
            model=model,
            api_key=api_key,
            max_tokens=50
        )
        
        # 测试简单调用
        response = llm.invoke([HumanMessage(content="请回复'连接测试成功'")])
        
        if "成功" in response.content:
            logger.info(f"✅ DashScope OpenAI 兼容接口连接测试成功")
            logger.info(f"   模型: {model}")
            logger.info(f"   响应: {response.content}")
            return True
        else:
            logger.warning(f"⚠️ DashScope OpenAI 兼容接口响应异常: {response.content}")
            return False
            
    except Exception as e:
        logger.error(f"❌ DashScope OpenAI 兼容接口连接测试失败: {e}")
        return False


def test_dashscope_openai_function_calling(
    model: str = "qwen-plus-latest",
    api_key: Optional[str] = None
) -> bool:
    """测试 DashScope OpenAI 兼容接口的 Function Calling"""
    
    try:
        from langchain_core.messages import HumanMessage
        from langchain_core.tools import tool

        
        # 定义测试工具
        @tool
        def get_test_data(query: str) -> str:
            """获取测试数据的工具"""
            return f"测试数据: {query}"
        
        # 创建 LLM 并绑定工具
        llm = create_dashscope_openai_llm(
            model=model,
            api_key=api_key,
            max_tokens=200
        )
        
        llm_with_tools = llm.bind_tools([get_test_data])
        
        # 测试工具调用
        response = llm_with_tools.invoke([
            HumanMessage(content="请调用get_test_data工具，参数为'function calling test'")
        ])
        
        if hasattr(response, 'tool_calls') and len(response.tool_calls) > 0:
            logger.info(f"✅ DashScope OpenAI Function Calling 测试成功")
            logger.info(f"   工具调用数量: {len(response.tool_calls)}")
            logger.info(f"   工具调用: {response.tool_calls[0]['name']}")
            return True
        else:
            logger.warning(f"⚠️ DashScope OpenAI Function Calling 未触发")
            logger.info(f"   响应内容: {response.content}")
            return False
            
    except Exception as e:
        logger.error(f"❌ DashScope OpenAI Function Calling 测试失败: {e}")
        return False


if __name__ == "__main__":
    """测试脚本"""
    logger.info(f"🧪 DashScope OpenAI 兼容适配器测试")
    logger.info(f"=")
    
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
