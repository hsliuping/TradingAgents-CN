"""
持久化工具
使用URL参数和session state结合的方式来持久化用户选择
"""

import streamlit as st
import logging
from urllib.parse import urlencode, parse_qs
import json

logger = logging.getLogger(__name__)

class ModelPersistence:
    """模型选择持久化管理器"""

    def __init__(self):
        self.storage_key = "model_config"

    def _get_default_embedding_model(self, provider: str | None) -> str:
        """根据提供商返回默认的记忆嵌入模型。
        若无特定默认，统一回退到 'text-embedding-v4'。
        """
        # 可按需扩展各厂商默认
        defaults = {
            "dashscope": "text-embedding-v4",
            "deepseek": "text-embedding-v1",
            "openai": "text-embedding-3-small",
            "google": "embedding-001",
            "openrouter": "text-embedding-3",
            "硅基流动": "BAAI/bge-m3",
        }
        return defaults.get((provider or "").lower(), "text-embedding-v4")

    def save_config(self, provider, category, model, memory_provider=None, memory_model=None):
        """保存配置到session state和URL"""
        config = {
            'provider': provider,
            'category': category,
            'model': model,
            # 这里只记录当前选择，避免成为“全局默认”，具体默认在load时按provider映射恢复
            'memory_provider': memory_provider,
            'memory_model': None  # 不把当前输入写成全局默认，恢复时从映射选择
        }

        # 保存到session state
        st.session_state[self.storage_key] = config

        # 同步维护每个提供商的记忆模型映射
        if memory_provider:
            key = 'memory_models_by_provider'
            if key not in st.session_state:
                st.session_state[key] = {}
            if memory_model:
                st.session_state[key][memory_provider] = memory_model

        # 准备URL参数，只包含非None的值
        query_params_to_set = {k: v for k, v in config.items() if v is not None}

        # 保存到URL参数（通过query_params）
        try:
            st.query_params.update(query_params_to_set)
            logger.debug(f"💾 [Persistence] 配置已保存: {config}")
        except Exception as e:
            logger.warning(f"⚠️ [Persistence] URL参数保存失败: {e}")

    def load_config(self):
        """从session state或URL加载配置"""
        # 首先尝试从URL参数加载
        try:
            query_params = st.query_params
            if 'provider' in query_params:
                config = {
                    'provider': query_params.get('provider', 'dashscope'),
                    'category': query_params.get('category', 'openai'),
                    'model': query_params.get('model', ''),
                    'memory_provider': query_params.get('memory_provider'),
                    'memory_model': query_params.get('memory_model')
                }
                # 若指定了记忆提供商但未提供模型名，则尝试从映射或默认值恢复
                mem_provider = config.get('memory_provider')
                if mem_provider and not config.get('memory_model'):
                    mapping = st.session_state.get('memory_models_by_provider', {})
                    restored = mapping.get(mem_provider)
                    if restored:
                        config['memory_model'] = restored
                    else:
                        config['memory_model'] = self._get_default_embedding_model(mem_provider)
                logger.debug(f"📥 [Persistence] 从URL加载配置: {config}")
                return config
        except Exception as e:
            logger.warning(f"⚠️ [Persistence] URL参数加载失败: {e}")

        # 然后尝试从session state加载
        if self.storage_key in st.session_state:
            config = dict(st.session_state[self.storage_key])
            # 同样处理记忆模型的恢复
            mem_provider = config.get('memory_provider')
            if mem_provider and not config.get('memory_model'):
                mapping = st.session_state.get('memory_models_by_provider', {})
                restored = mapping.get(mem_provider)
                if restored:
                    config['memory_model'] = restored
                else:
                    config['memory_model'] = self._get_default_embedding_model(mem_provider)
            logger.debug(f"📥 [Persistence] 从Session State加载配置: {config}")
            return config

        # 返回默认配置
        default_config = {
            'provider': 'dashscope',
            'category': 'openai',
            'model': '',
            'memory_provider': None,
            'memory_model': None
        }
        logger.debug(f"📥 [Persistence] 使用默认配置: {default_config}")
        return default_config
    
    def clear_config(self):
        """清除配置"""
        if self.storage_key in st.session_state:
            del st.session_state[self.storage_key]
        
        try:
            st.query_params.clear()
            logger.info("🗑️ [Persistence] 配置已清除")
        except Exception as e:
            logger.warning(f"⚠️ [Persistence] 清除失败: {e}")

# 全局实例
persistence = ModelPersistence()

def save_model_selection(provider, category="", model="", memory_provider=None, memory_model=None):
    """保存模型选择"""
    persistence.save_config(provider, category, model, memory_provider, memory_model)

def load_model_selection():
    """加载模型选择"""
    return persistence.load_config()

def clear_model_selection():
    """清除模型选择"""
    persistence.clear_config()
