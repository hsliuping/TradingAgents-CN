"""
提示词管理器

统一管理提示词的加载、缓存和渲染
"""

import os
import threading
from typing import Dict, Optional

from .template import PromptTemplate
from .loader import PromptLoader


class PromptManager:
    """
    提示词管理器 (单例模式)
    
    用法:
        manager = PromptManager()
        
        # 获取提示词
        prompt = manager.get("market_analyst", category="analysts")
        
        # 渲染提示词
        text = manager.render(
            "market_analyst",
            category="analysts",
            ticker="AAPL",
            date="2024-01-15"
        )
        
        # 切换语言
        manager.set_language("en")
    """
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(PromptManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self._language = os.getenv("PROMPT_LANGUAGE", "zh")
            self._loader = PromptLoader()
            self._custom_templates: Dict[str, PromptTemplate] = {}
            self._initialized = True
    
    @property
    def language(self) -> str:
        """当前语言"""
        return self._language
    
    def set_language(self, language: str) -> None:
        """设置语言"""
        self._language = language
        self._loader.clear_cache()
    
    def get(
        self,
        name: str,
        category: Optional[str] = None,
        language: Optional[str] = None
    ) -> Optional[PromptTemplate]:
        """
        获取提示词模板
        
        Args:
            name: 模板名称
            category: 类别
            language: 语言 (默认使用当前语言)
            
        Returns:
            提示词模板
        """
        lang = language or self._language
        
        # 先检查自定义模板
        custom_key = f"{lang}/{category}/{name}" if category else f"{lang}/{name}"
        if custom_key in self._custom_templates:
            return self._custom_templates[custom_key]
        
        # 从文件加载
        return self._loader.load(name, lang, category)
    
    def render(
        self,
        name: str,
        category: Optional[str] = None,
        language: Optional[str] = None,
        **variables
    ) -> str:
        """
        渲染提示词
        
        Args:
            name: 模板名称
            category: 类别
            language: 语言
            **variables: 模板变量
            
        Returns:
            渲染后的文本
        """
        template = self.get(name, category, language)
        
        if template is None:
            return f"[提示词 '{name}' 未找到]"
        
        return template.render(**variables)
    
    def register(
        self,
        name: str,
        template: str,
        category: Optional[str] = None,
        language: Optional[str] = None
    ) -> PromptTemplate:
        """
        注册自定义提示词模板
        
        Args:
            name: 模板名称
            template: 模板内容
            category: 类别
            language: 语言
            
        Returns:
            创建的模板对象
        """
        lang = language or self._language
        key = f"{lang}/{category}/{name}" if category else f"{lang}/{name}"
        
        prompt_template = PromptTemplate(
            template=template,
            name=name,
            language=lang
        )
        
        self._custom_templates[key] = prompt_template
        return prompt_template
    
    def list_available(
        self,
        category: Optional[str] = None,
        language: Optional[str] = None
    ) -> Dict[str, PromptTemplate]:
        """列出可用的提示词"""
        lang = language or self._language
        return self._loader.load_all(lang, category)
    
    def exists(
        self,
        name: str,
        category: Optional[str] = None,
        language: Optional[str] = None
    ) -> bool:
        """检查提示词是否存在"""
        lang = language or self._language
        
        # 检查自定义模板
        custom_key = f"{lang}/{category}/{name}" if category else f"{lang}/{name}"
        if custom_key in self._custom_templates:
            return True
        
        # 检查文件
        return self._loader.exists(name, lang, category)


# 便捷函数
def get_prompt(
    name: str,
    category: Optional[str] = None,
    **variables
) -> str:
    """
    便捷函数: 获取并渲染提示词
    
    用法:
        from core.prompts import get_prompt
        
        prompt = get_prompt("market_analyst", category="analysts", ticker="AAPL")
    """
    manager = PromptManager()
    return manager.render(name, category, **variables)

