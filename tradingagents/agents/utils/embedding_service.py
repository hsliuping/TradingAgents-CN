"""
Embedding 服务管理模块

支持多种 Embedding 服务，按优先级自动选择：
1. Ollama (本地) - 完全离线，推荐
2. 通义千问 DashScope - 免费额度大
3. OpenAI - 效果好但需要翻墙
4. 禁用 - 优雅降级

使用方法：
    from tradingagents.agents.utils.embedding_service import get_embedding_service
    
    service = get_embedding_service(config)
    vector = service.get_embedding("要嵌入的文本")
"""

import os
import requests
from typing import Optional, List
from abc import ABC, abstractmethod

from tradingagents.utils.logging_init import get_logger
logger = get_logger("agents.utils.embedding")


class EmbeddingService(ABC):
    """Embedding 服务基类"""
    
    @abstractmethod
    def get_embedding(self, text: str) -> List[float]:
        """获取文本的向量嵌入"""
        pass
    
    @abstractmethod
    def get_service_name(self) -> str:
        """获取服务名称"""
        pass
    
    def is_available(self) -> bool:
        """检查服务是否可用"""
        return True


class OllamaEmbeddingService(EmbeddingService):
    """Ollama 本地 Embedding 服务"""
    
    def __init__(self, base_url: str = "http://localhost:11434", model: str = "nomic-embed-text"):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self._available = None
    
    def is_available(self) -> bool:
        """检测 Ollama 是否运行且模型可用"""
        if self._available is not None:
            return self._available
        
        try:
            # 检查 Ollama 服务是否运行
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            if response.status_code != 200:
                self._available = False
                return False
            
            # 检查模型是否已下载
            models = response.json().get("models", [])
            model_names = [m.get("name", "").split(":")[0] for m in models]
            
            if self.model not in model_names and f"{self.model}:latest" not in [m.get("name", "") for m in models]:
                logger.warning(f"⚠️ Ollama 运行中但未找到 {self.model} 模型")
                logger.info(f"💡 请运行: ollama pull {self.model}")
                self._available = False
                return False
            
            self._available = True
            logger.info(f"✅ Ollama Embedding 服务可用: {self.model}")
            return True
            
        except requests.exceptions.ConnectionError:
            logger.debug(f"Ollama 服务未运行 ({self.base_url})")
            self._available = False
            return False
        except Exception as e:
            logger.debug(f"Ollama 检测失败: {e}")
            self._available = False
            return False
    
    def get_embedding(self, text: str) -> List[float]:
        """通过 Ollama API 获取嵌入向量"""
        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={"model": self.model, "prompt": text},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("embedding", [])
            else:
                logger.error(f"Ollama embedding 失败: {response.status_code}")
                return [0.0] * 768  # nomic-embed-text 输出维度
        except Exception as e:
            logger.error(f"Ollama embedding 异常: {e}")
            return [0.0] * 768
    
    def get_service_name(self) -> str:
        return f"Ollama ({self.model})"


class DashScopeEmbeddingService(EmbeddingService):
    """通义千问 DashScope Embedding 服务"""
    
    def __init__(self):
        self.api_key = os.getenv('DASHSCOPE_API_KEY')
        self.model = "text-embedding-v3"
    
    def is_available(self) -> bool:
        if not self.api_key:
            return False
        try:
            import dashscope
            dashscope.api_key = self.api_key
            return True
        except ImportError:
            logger.debug("dashscope 包未安装")
            return False
    
    def get_embedding(self, text: str) -> List[float]:
        try:
            from dashscope import TextEmbedding
            response = TextEmbedding.call(
                model=self.model,
                input=text
            )
            if response.status_code == 200:
                return response.output['embeddings'][0]['embedding']
            else:
                logger.error(f"DashScope embedding 失败: {response.message}")
                return [0.0] * 1536
        except Exception as e:
            logger.error(f"DashScope embedding 异常: {e}")
            return [0.0] * 1536
    
    def get_service_name(self) -> str:
        return f"DashScope ({self.model})"

