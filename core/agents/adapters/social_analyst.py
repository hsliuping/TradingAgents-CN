"""
社交媒体分析师智能体

基于 BaseAgent 的社交媒体分析师实现
"""

from typing import Any, Dict, Optional

from ..base import BaseAgent
from ..config import AgentConfig, BUILTIN_AGENTS
from ..registry import register_agent


@register_agent
class SocialMediaAnalystAgent(BaseAgent):
    """
    社交媒体分析师智能体
    
    分析社交媒体上的舆情、情绪等
    """
    
    metadata = BUILTIN_AGENTS["social_analyst"]
    
    def __init__(self, config: Optional[AgentConfig] = None):
        super().__init__(config)
        self._legacy_node = None
        self._llm = None
        self._toolkit = None
    
    def set_dependencies(self, llm: Any, toolkit: Any) -> "SocialMediaAnalystAgent":
        """设置依赖项"""
        self._llm = llm
        self._toolkit = toolkit
        return self
    
    def initialize(self) -> None:
        """初始化智能体"""
        if self._llm is None or self._toolkit is None:
            raise ValueError("必须先调用 set_dependencies() 设置 LLM 和 toolkit")
        
        from tradingagents.agents.analysts.social_media_analyst import create_social_media_analyst
        self._legacy_node = create_social_media_analyst(self._llm, self._toolkit)
    
    def execute(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行社交媒体分析
        
        Args:
            state: 包含以下键的状态字典:
                - company_of_interest: 股票代码
                - trade_date: 交易日期
                - messages: 消息历史
                
        Returns:
            更新后的状态，包含:
                - sentiment_report: 社交媒体情绪分析报告
                - messages: 更新的消息历史
        """
        if self._legacy_node is None:
            self.initialize()
        
        return self._legacy_node(state)

