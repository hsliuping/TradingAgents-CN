"""
提示词模板
"""

import re
from typing import Any, Dict, List, Optional, Set


class PromptTemplate:
    """
    提示词模板
    
    支持变量替换和条件渲染
    
    用法:
        template = PromptTemplate('''
        你是一个{role}。
        
        分析以下股票: {ticker}
        日期: {date}
        
        {#if include_history}
        历史数据:
        {history}
        {/if}
        ''')
        
        result = template.render(
            role="市场分析师",
            ticker="AAPL",
            date="2024-01-15",
            include_history=True,
            history="..."
        )
    """
    
    # 变量模式: {variable_name}
    VAR_PATTERN = re.compile(r'\{([a-zA-Z_][a-zA-Z0-9_]*)\}')
    
    # 条件模式: {#if condition}...{/if}
    IF_PATTERN = re.compile(
        r'\{#if\s+([a-zA-Z_][a-zA-Z0-9_]*)\}(.*?)\{/if\}',
        re.DOTALL
    )
    
    def __init__(
        self,
        template: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        language: str = "zh"
    ):
        self.template = template
        self.name = name
        self.description = description
        self.language = language
        self._variables: Optional[Set[str]] = None
    
    @property
    def variables(self) -> Set[str]:
        """获取模板中的所有变量"""
        if self._variables is None:
            self._variables = set(self.VAR_PATTERN.findall(self.template))
            # 添加条件变量
            for match in self.IF_PATTERN.finditer(self.template):
                self._variables.add(match.group(1))
        return self._variables
    
    def render(self, **kwargs) -> str:
        """
        渲染模板
        
        Args:
            **kwargs: 模板变量
            
        Returns:
            渲染后的字符串
        """
        result = self.template
        
        # 处理条件块
        result = self._process_conditions(result, kwargs)
        
        # 替换变量
        result = self._replace_variables(result, kwargs)
        
        return result.strip()
    
    def _process_conditions(self, text: str, variables: Dict[str, Any]) -> str:
        """处理条件块"""
        def replace_condition(match):
            condition_var = match.group(1)
            content = match.group(2)
            
            # 检查条件
            if variables.get(condition_var):
                return content
            return ""
        
        return self.IF_PATTERN.sub(replace_condition, text)
    
    def _replace_variables(self, text: str, variables: Dict[str, Any]) -> str:
        """替换变量"""
        def replace_var(match):
            var_name = match.group(1)
            value = variables.get(var_name, "")
            return str(value) if value is not None else ""
        
        return self.VAR_PATTERN.sub(replace_var, text)
    
    def validate(self, **kwargs) -> List[str]:
        """
        验证变量是否完整
        
        Returns:
            缺失的变量列表
        """
        missing = []
        for var in self.variables:
            if var not in kwargs:
                missing.append(var)
        return missing
    
    def __str__(self) -> str:
        return self.template
    
    def __repr__(self) -> str:
        return f"PromptTemplate(name={self.name!r}, variables={self.variables})"


class SystemPrompt(PromptTemplate):
    """系统提示词模板"""
    pass


class UserPrompt(PromptTemplate):
    """用户提示词模板"""
    pass


class AssistantPrompt(PromptTemplate):
    """助手提示词模板"""
    pass

