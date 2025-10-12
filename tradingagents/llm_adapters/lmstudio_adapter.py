"""
LM Studio本地AI模型适配器
为LM Studio本地运行的AI模型提供完整的适配器支持
"""

import os
import requests
import time
from typing import Any, Dict, List, Optional, Union
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import CallbackManagerForLLMRun

# 导入统一日志系统
from tradingagents.utils.logging_init import setup_llm_logging
from tradingagents.utils.logging_manager import get_logger

# 导入OpenAI兼容基类
from .openai_compatible_base import OpenAICompatibleBase, TOKEN_TRACKING_ENABLED

# 导入token跟踪器
try:
    from tradingagents.config.config_manager import token_tracker
    TOKEN_TRACKING_ENABLED = True
except ImportError:
    TOKEN_TRACKING_ENABLED = False

logger = get_logger('agents')
logger = setup_llm_logging()


class ChatLMStudio(OpenAICompatibleBase):
    """
    LM Studio本地模型适配器

    支持通过OpenAI兼容接口与本地运行的LM Studio模型进行交互
    """

    def __init__(
        self,
        model: str = "llama-3.1-8b-instruct",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = None,
        timeout: int = 30,
        **kwargs
    ):
        """
        初始化LM Studio适配器

        Args:
            model: 模型名称，默认为 llama-3.1-8b-instruct
            api_key: API密钥，LM Studio通常使用 "lm-studio-local"
            base_url: LM Studio服务地址，默认为 http://localhost:1234/v1
            temperature: 温度参数
            max_tokens: 最大token数
            timeout: 请求超时时间（秒）
            **kwargs: 其他参数
        """

        # 获取配置参数
        self.base_url = base_url or os.getenv("LM_STUDIO_BASE_URL", "http://localhost:1234/v1")
        self.api_key = api_key or os.getenv("LM_STUDIO_API_KEY", "lm-studio-local")
        self.timeout = timeout

        # 验证LM Studio服务可用性
        self._validate_lmstudio_service()

        super().__init__(
            provider_name="lmstudio",
            model=model,
            api_key_env_var="LM_STUDIO_API_KEY",
            base_url=self.base_url,
            api_key=self.api_key,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
            **kwargs
        )

        logger.info(f"🏠 LM Studio适配器初始化成功")
        logger.info(f"   模型: {model}")
        logger.info(f"   服务地址: {self.base_url}")
        logger.info(f"   超时设置: {timeout}秒")

    def _validate_lmstudio_service(self):
        """验证LM Studio服务是否可用"""
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # 测试连接
            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=5  # 短超时，用于快速验证
            )

            if response.status_code == 200:
                models_data = response.json()
                available_models = [model.get("id", "unknown") for model in models_data.get("data", [])]
                logger.info(f"✅ LM Studio服务连接成功，可用模型: {available_models}")
            else:
                logger.warning(f"⚠️ LM Studio服务响应异常: {response.status_code}")

        except requests.exceptions.ConnectionError:
            logger.warning(f"⚠️ 无法连接到LM Studio服务: {self.base_url}")
            logger.warning("   请确保LM Studio正在运行并已启动服务器")
        except requests.exceptions.Timeout:
            logger.warning(f"⚠️ LM Studio服务连接超时: {self.base_url}")
        except Exception as e:
            logger.warning(f"⚠️ LM Studio服务验证失败: {e}")

    def get_available_models(self) -> List[str]:
        """
        获取LM Studio中可用的模型列表

        Returns:
            可用模型ID列表
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                models_data = response.json()
                models = [model.get("id", "unknown") for model in models_data.get("data", [])]
                logger.info(f"✅ 获取到 {len(models)} 个可用模型: {models}")
                return models
            else:
                logger.error(f"❌ 获取模型列表失败: HTTP {response.status_code}")
                return []

        except Exception as e:
            logger.error(f"❌ 获取LM Studio模型列表失败: {e}")
            return []

    def test_connection(self) -> bool:
        """
        测试LM Studio连接状态

        Returns:
            连接是否成功
        """
        try:
            models = self.get_available_models()
            return len(models) > 0
        except Exception as e:
            logger.error(f"❌ LM Studio连接测试失败: {e}")
            return False

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        """
        生成聊天响应，包含LM Studio特有的错误处理和重试逻辑
        """

        start_time = time.time()
        max_retries = 2
        retry_count = 0

        while retry_count <= max_retries:
            try:
                # 调用父类生成方法
                result = super()._generate(messages, stop, run_manager, **kwargs)

                # 记录token使用
                self._track_token_usage(result, kwargs, start_time)

                return result

            except Exception as e:
                retry_count += 1

                # 分析错误类型
                error_msg = str(e).lower()

                if "connection" in error_msg or "timeout" in error_msg:
                    if retry_count <= max_retries:
                        logger.warning(f"⚠️ LM Studio连接问题，第 {retry_count} 次重试: {e}")
                        time.sleep(1)  # 等待1秒后重试
                        continue
                    else:
                        logger.error(f"❌ LM Studio连接失败，已达最大重试次数: {e}")
                        raise Exception(f"LM Studio连接失败: {e}")

                elif "model" in error_msg and "not found" in error_msg:
                    logger.error(f"❌ LM Studio模型未找到，请检查模型是否已加载: {e}")
                    raise Exception(f"模型未找到，请确保在LM Studio中已加载模型: {e}")

                else:
                    logger.error(f"❌ LM Studio生成响应失败: {e}")
                    raise

        # 如果所有重试都失败
        raise Exception(f"LM Studio请求失败，已达最大重试次数 {max_retries}")

    def _track_token_usage(self, result: ChatResult, kwargs: Dict, start_time: float):
        """记录token使用量并输出日志（LM Studio专用）"""
        if not TOKEN_TRACKING_ENABLED:
            return

        try:
            # 统计token信息
            usage = getattr(result, "usage_metadata", None)
            total_tokens = usage.get("total_tokens") if usage else None
            prompt_tokens = usage.get("input_tokens") if usage else None
            completion_tokens = usage.get("output_tokens") if usage else None

            elapsed = time.time() - start_time

            # LM Studio特殊日志格式
            logger.info(
                f"🏠 LM Studio Token使用 - Model: {getattr(self, 'model_name', 'unknown')}, "
                f"总tokens: {total_tokens}, 提示: {prompt_tokens}, 补全: {completion_tokens}, "
                f"用时: {elapsed:.2f}s (本地推理)"
            )

            # 本地模型性能提示
            if elapsed > 30:
                logger.warning("💡 本地模型响应较慢，建议优化硬件配置或使用更小的模型")
            elif elapsed < 5:
                logger.info("⚡ 本地模型响应快速，性能良好")

        except Exception as e:
            logger.warning(f"⚠️ LM Studio Token跟踪记录失败: {e}")

    def get_model_info(self) -> Dict[str, Any]:
        """
        获取当前模型的详细信息

        Returns:
            模型信息字典
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            # 获取所有模型信息
            response = requests.get(
                f"{self.base_url}/models",
                headers=headers,
                timeout=self.timeout
            )

            if response.status_code == 200:
                models_data = response.json()
                all_models = models_data.get("data", [])

                # 查找当前模型
                current_model_name = getattr(self, 'model_name', None)
                for model in all_models:
                    if model.get("id") == current_model_name:
                        return {
                            "id": model.get("id"),
                            "object": model.get("object"),
                            "created": model.get("created"),
                            "owned_by": model.get("owned_by"),
                            "permission": model.get("permission"),
                            "root": model.get("root"),
                            "parent": model.get("parent"),
                            "is_local": True,
                            "provider": "LM Studio"
                        }

            # 如果没找到当前模型，返回基本信息
            return {
                "id": current_model_name or "unknown",
                "object": "model",
                "is_local": True,
                "provider": "LM Studio",
                "note": "模型信息获取失败，使用默认信息"
            }

        except Exception as e:
            logger.warning(f"⚠️ 获取LM Studio模型信息失败: {e}")
            return {
                "id": getattr(self, 'model_name', 'unknown'),
                "object": "model",
                "is_local": True,
                "provider": "LM Studio",
                "error": str(e)
            }


# LM Studio适配器注册信息
LM_STUDIO_CONFIG = {
    "adapter_class": ChatLMStudio,
    "base_url": "http://localhost:1234/v1",
    "api_key_env": "LM_STUDIO_API_KEY",
    "supports_local_models": True,
    "default_models": [
        "llama-3.1-8b-instruct"
    ],
    "models": {
        "llama-3.1-8b-instruct": {
            "context_length": 128000,
            "supports_function_calling": True,
            "description": "Llama 3.1 8B Instruct",
            "recommended_for": ["复杂推理", "专业分析", "高质量输出"]
        }
    }
}


def create_lmstudio_llm(
    model: str = "llama-3.1-8b-instruct",
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    timeout: int = 30,
    **kwargs
) -> ChatLMStudio:
    """
    创建LM Studio LLM实例的工厂函数

    Args:
        model: 模型名称
        api_key: API密钥
        base_url: 服务地址
        temperature: 温度参数
        max_tokens: 最大token数
        timeout: 超时时间
        **kwargs: 其他参数

    Returns:
        LM Studio适配器实例
    """
    return ChatLMStudio(
        model=model,
        api_key=api_key,
        base_url=base_url,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
        **kwargs
    )


def test_lmstudio_adapter():
    """测试LM Studio适配器是否能被正确实例化"""
    try:
        adapter = ChatLMStudio(
            model="llama-3.1-8b-instruct",
            api_key="lm-studio-local",
            base_url="http://localhost:1234/v1"
        )
        logger.info("✅ LM Studio适配器实例化成功")
        return True
    except Exception as e:
        logger.info(f"ℹ️ LM Studio适配器实例化失败（预期，因为服务未运行）: {e}")
        return False


if __name__ == "__main__":
    test_lmstudio_adapter()